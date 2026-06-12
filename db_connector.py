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
                lines.append(f"  - {column_name} ({data_type})")
            lines.append("")  # linha em branco entre tabelas

        return "\n".join(lines)

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

    def execute_query(self, sql):
        """
        Executa uma query SQL e retorna os resultados.

        Parâmetros:
            sql (str): query SQL gerada pelo LLM

        Retorna:
            tuple: (columns, rows)
                - columns: lista de strings com nomes das colunas
                - rows: lista de tuplas com os dados

        Lança:
            RuntimeError se não houver conexão ativa
            Exception com a mensagem de erro do banco se a query falhar
        """
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
