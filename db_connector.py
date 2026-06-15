"""
db_connector.py
---------------
Responsável por toda a comunicação com o banco de dados.
Suporta MySQL e PostgreSQL.

Fluxo de uso:
    1. Instanciar DatabaseConnector com as credenciais
    2. Chamar connect() para abrir a conexão
    3. Chamar get_schema_text() para obter o schema (usado pelo LLM)
    4. Chamar execute_query(sql) para executar queries
    5. Chamar disconnect() ao encerrar
"""


class DatabaseConnector:
    """
    Gerencia a conexão com MySQL ou PostgreSQL e fornece
    utilitários para introspecção de schema e execução de queries.
    """

    def __init__(self, host, port, user, password, database, db_type):
        """
        Parâmetros:
            host     (str): endereço do servidor (ex: "localhost")
            port     (int): porta (MySQL padrão: 3306 | PostgreSQL padrão: 5432)
            user     (str): nome do usuário
            password (str): senha
            database (str): nome do banco de dados
            db_type  (str): "mysql" ou "postgresql"
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.db_type = db_type.lower()
        self.connection = None  # será preenchido pelo connect()

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------

    def connect(self):
        """
        Abre a conexão com o banco de dados.
        Lança uma exceção com mensagem clara se a conexão falhar.
        """
        try:
            if self.db_type == "mysql":
                import mysql.connector
                self.connection = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database
                )

            elif self.db_type == "postgresql":
                import psycopg2
                self.connection = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    dbname=self.database
                )

            else:
                raise ValueError(f"Tipo de banco não suportado: '{self.db_type}'. Use 'mysql' ou 'postgresql'.")

        except Exception as e:
            raise ConnectionError(f"Falha ao conectar ao banco '{self.database}' em {self.host}:{self.port}\n→ {e}")

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def get_schema(self):
        """
        Consulta o information_schema para obter todas as tabelas
        e suas colunas (nome + tipo de dado).

        Retorna:
            dict: { "nome_tabela": [("coluna1", "tipo1"), ("coluna2", "tipo2"), ...], ... }
        """
        if self.connection is None:
            raise RuntimeError("Não há conexão ativa. Chame connect() primeiro.")

        cursor = self.connection.cursor()

        # information_schema.columns existe tanto no MySQL quanto no PostgreSQL.
        # A diferença é o filtro: MySQL usa table_schema, PostgreSQL usa table_catalog.
        if self.db_type == "mysql":
            query = """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, ordinal_position
            """
        else:  # postgresql
            query = """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_catalog = %s
                  AND table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """

        cursor.execute(query, (self.database,))
        rows = cursor.fetchall()
        cursor.close()

        # Organiza o resultado num dicionário: tabela → lista de (coluna, tipo)
        schema = {}
        for table_name, column_name, data_type in rows:
            if table_name not in schema:
                schema[table_name] = []
            schema[table_name].append((column_name, data_type))

        return schema

    def get_schema_text(self):
        """
        Formata o schema como texto legível para o LLM.

        Exemplo de saída:
            Tabela: clientes
              - id (int)
              - nome (varchar)
              - email (varchar)

            Tabela: pedidos
              - id (int)
              - cliente_id (int)
              - valor (decimal)

        Retorna:
            str: schema formatado como texto
        """
        schema = self.get_schema()

        if not schema:
            return "Nenhuma tabela encontrada no banco de dados."

        lines = []
        for table_name, columns in schema.items():
            lines.append(f"Tabela: {table_name}")
            for column_name, data_type in columns:
                line = f"  - {column_name} ({data_type})"

                # Para colunas de texto com poucos valores distintos,
                # inclui exemplos dos valores reais. Isso ensina o modelo
                # a usar o literal correto (ex: 'Music', e não 'Música'),
                # técnica conhecida como "value linking".
                if self._is_text_type(data_type):
                    samples = self._get_distinct_values(table_name, column_name)
                    if samples:
                        shown = ", ".join(f"'{v}'" for v in samples)
                        line += f" — valores possíveis: {shown}"

                lines.append(line)
            lines.append("")  # linha em branco entre tabelas

        return "\n".join(lines)

    @staticmethod
    def _is_text_type(data_type):
        """Indica se o tipo de dado é textual (candidato a ter valores de exemplo)."""
        t = data_type.lower()
        return any(k in t for k in ("char", "text", "enum"))

    def _get_distinct_values(self, table, column, limit=15):
        """
        Retorna os valores distintos de uma coluna, até um limite.

        Usado para enriquecer o esquema com exemplos de valores reais.
        Colunas com muitos valores distintos (ex: nomes de pessoas) são
        ignoradas, pois não ajudam o modelo e aumentariam o prompt.

        Parâmetros:
            table  (str): nome da tabela
            column (str): nome da coluna
            limit  (int): nº máximo de valores; acima disso, a coluna é ignorada

        Retorna:
            list | None: lista de valores, ou None se houver valores demais
                         (alta cardinalidade) ou se a consulta falhar
        """
        # Identificadores vêm do próprio catálogo do banco (confiáveis),
        # mas são citados para suportar nomes especiais. MySQL usa crase,
        # PostgreSQL usa aspas duplas.
        q = "`" if self.db_type == "mysql" else '"'
        qtable, qcol = f"{q}{table}{q}", f"{q}{column}{q}"

        # Busca limit+1 valores: se vier mais que 'limit', é alta cardinalidade
        sql = (
            f"SELECT DISTINCT {qcol} FROM {qtable} "
            f"WHERE {qcol} IS NOT NULL LIMIT {limit + 1}"
        )

        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            values = [row[0] for row in cursor.fetchall()]
        except Exception:
            return None  # em caso de erro, simplesmente não inclui exemplos
        finally:
            cursor.close()

        if not values or len(values) > limit:
            return None
        return values

    def get_table_names(self):
        """
        Retorna apenas os nomes das tabelas (para exibir na GUI).

        Retorna:
            list[str]: lista de nomes de tabelas
        """
        schema = self.get_schema()
        return list(schema.keys())

    # ------------------------------------------------------------------
    # Execução de queries
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_sql(sql):
        """
        Valida o SQL gerado pelo LLM antes de executá-lo.

        Proteção contra prompt injection → SQL injection:
        só permite queries SELECT e bloqueia comandos destrutivos
        ou de manipulação de dados (DDL/DML).

        Parâmetros:
            sql (str): query SQL a validar

        Lança:
            ValueError se o SQL não for um SELECT ou contiver
            palavras-chave perigosas
        """
        # Palavras-chave que nunca devem aparecer num SELECT de leitura
        FORBIDDEN = [
            "drop", "delete", "truncate", "insert", "update",
            "alter", "create", "replace", "grant", "revoke",
            "exec", "execute", "xp_", "sp_",           # procedimentos
            "load_file", "into outfile", "into dumpfile",  # exfiltração de arquivos
            "sleep(", "benchmark(",                     # ataques de tempo
        ]

        sql_lower = sql.lower().strip()

        # A query deve começar com SELECT (ignora comentários iniciais)
        # Remove comentários de linha (--) antes de checar
        sql_clean = "\n".join(
            line for line in sql_lower.splitlines()
            if not line.strip().startswith("--")
        ).strip()

        if not sql_clean.startswith("select"):
            raise ValueError(
                f"Segurança: apenas queries SELECT são permitidas.\n"
                f"O modelo gerou uma instrução não autorizada:\n{sql[:200]}"
            )

        # Verifica palavras-chave proibidas no corpo da query
        for keyword in FORBIDDEN:
            if keyword in sql_lower:
                raise ValueError(
                    f"Segurança: a query contém a palavra-chave proibida '{keyword}'.\n"
                    f"Query bloqueada:\n{sql[:200]}"
                )

        # Bloqueia múltiplos statements (ex: SELECT 1; DROP TABLE x)
        # Remove strings entre aspas simples antes de checar o ponto-e-vírgula
        # para evitar falsos positivos com valores que contenham ";"
        import re
        sql_no_strings = re.sub(r"'[^']*'", "''", sql_lower)
        statements = [s.strip() for s in sql_no_strings.split(";") if s.strip()]
        if len(statements) > 1:
            raise ValueError(
                "Segurança: múltiplos statements detectados. "
                "Apenas uma query por vez é permitida."
            )

    def execute_query(self, sql):
        """
        Valida e executa uma query SQL, retornando os resultados.

        Parâmetros:
            sql (str): query SQL gerada pelo LLM

        Retorna:
            tuple: (columns, rows)
                - columns: lista de strings com nomes das colunas
                - rows: lista de tuplas com os dados

        Lança:
            ValueError  se o SQL não passar na validação de segurança
            RuntimeError se não houver conexão ativa
            Exception com a mensagem de erro do banco se a query falhar
        """
        # Valida antes de qualquer interação com o banco
        self._validate_sql(sql)

        if self.connection is None:
            raise RuntimeError("Não há conexão ativa. Chame connect() primeiro.")

        cursor = self.connection.cursor()

        try:
            cursor.execute(sql)

            # cursor.description contém metadados das colunas retornadas.
            # Se for None, a instrução não produziu um conjunto de resultados
            # (não era um SELECT) — chamar fetchall() aqui lançaria
            # "No result set to fetch from" no mysql-connector.
            if cursor.description is None:
                raise Exception(
                    "A instrução executou mas não retornou resultados. "
                    "Apenas consultas SELECT são suportadas por esta ferramenta."
                )

            rows = cursor.fetchall()

            # Cada item de cursor.description é uma tupla;
            # o índice 0 é o nome da coluna
            columns = [desc[0] for desc in cursor.description]

            return columns, rows

        except Exception as e:
            raise Exception(f"Erro ao executar a query:\n{sql}\n\n→ {e}")

        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Encerramento
    # ------------------------------------------------------------------

    def disconnect(self):
        """
        Fecha a conexão com o banco de dados, liberando os recursos.
        Pode ser chamado com segurança mesmo se não houver conexão ativa.
        """
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass  # ignora erros ao fechar
            finally:
                self.connection = None

    # ------------------------------------------------------------------
    # Utilitário
    # ------------------------------------------------------------------

    def is_connected(self):
        """
        Verifica se há uma conexão ativa.

        Retorna:
            bool: True se conectado, False caso contrário
        """
        return self.connection is not None
