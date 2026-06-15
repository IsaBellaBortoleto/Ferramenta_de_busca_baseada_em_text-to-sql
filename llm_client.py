"""
llm_client.py
-------------
Responsável pela integração com o Ollama.
Recebe uma pergunta em linguagem natural + o schema do banco,
monta o prompt, envia ao modelo e retorna a query SQL gerada.

Pré-requisito:
    - Ollama instalado e rodando (ollama serve)
    - Modelo baixado (ex: ollama pull qwen2.5-coder:7b)
"""

import requests
import re


class OllamaClient:
    """
    Cliente HTTP para a API do Ollama.
    Converte perguntas em linguagem natural para queries SQL.
    """

    def __init__(self, host="localhost", port=11434, model="qwen2.5-coder:7b"):
        """
        Parâmetros:
            host  (str): endereço do servidor Ollama (padrão: localhost)
            port  (int): porta do servidor Ollama (padrão: 11434)
            model (str): nome do modelo a usar (padrão: qwen2.5-coder:7b)
        """
        self.base_url = f"http://{host}:{port}"
        self.model = model

    # ------------------------------------------------------------------
    # Método principal
    # ------------------------------------------------------------------

    def generate_sql(self, question, schema_text, db_type="mysql"):
        """
        Converte uma pergunta em linguagem natural para SQL.

        Parâmetros:
            question    (str): pergunta do usuário em linguagem natural
            schema_text (str): schema do banco formatado como texto
                               (obtido via DatabaseConnector.get_schema_text())
            db_type     (str): dialeto SQL a usar — "mysql" ou "postgresql"

        Retorna:
            str: query SQL pronta para execução

        Lança:
            ConnectionError se o Ollama não estiver acessível
            Exception para outros erros de comunicação
        """
        prompt = self._build_prompt(question, schema_text, db_type)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,       # recebe a resposta completa de uma vez
            "keep_alive": "30m",   # mantém o modelo na RAM entre consultas
            "options": {
                "temperature": 0,  # 0 = determinístico, sem criatividade
                                   # ideal para geração de SQL preciso
            }
        }

        try:
            response = requests.post(
                url=f"{self.base_url}/api/generate",
                json=payload,
                timeout=300  # em máquinas sem GPU, a primeira consulta
                             # inclui o tempo de carregar o modelo na RAM
            )
            response.raise_for_status()

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Não foi possível conectar ao Ollama em {self.base_url}.\n"
                "Verifique se o Ollama está rodando (execute: ollama serve)"
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                "O modelo demorou demais para responder.\n"
                "Tente novamente ou verifique os recursos da máquina."
            )
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Erro na API do Ollama: {e}")

        # A resposta é um JSON com o campo "response" contendo o texto gerado
        raw_output = response.json().get("response", "")

        if not raw_output.strip():
            raise Exception(
                f"O modelo '{self.model}' retornou uma resposta vazia.\n"
                "Verifique se o modelo está corretamente instalado."
            )

        sql = self._clean_sql(raw_output)
        return self._fix_dialect(sql, db_type)

    def fix_sql(self, question, schema_text, broken_sql, error_message, db_type="mysql"):
        """
        Pede ao modelo que corrija uma query que falhou na execução.

        Usado como segunda tentativa: quando o banco rejeita o SQL gerado,
        enviamos a query quebrada + a mensagem de erro do banco de volta
        ao modelo, que costuma conseguir se corrigir com esse contexto.

        Parâmetros:
            question      (str): pergunta original do usuário
            schema_text   (str): schema do banco em formato texto
            broken_sql    (str): query que falhou
            error_message (str): mensagem de erro retornada pelo banco
            db_type       (str): dialeto SQL ("mysql" ou "postgresql")

        Retorna:
            str: query SQL corrigida
        """
        dialect_name = "MySQL" if db_type.lower() == "mysql" else "PostgreSQL"

        prompt = f"""Você é um especialista em SQL. A query abaixo foi gerada para responder a uma pergunta, mas falhou ao ser executada no {dialect_name}.

Schema do banco de dados:
{schema_text}

Pergunta original: {question}

Query que falhou:
{broken_sql}

Erro retornado pelo banco:
{error_message}

Corrija a query para que execute corretamente no {dialect_name}. Retorne APENAS a query SQL corrigida, sem explicações ou markdown.

SQL:"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0},
        }

        response = requests.post(
            url=f"{self.base_url}/api/generate",
            json=payload,
            timeout=300
        )
        response.raise_for_status()

        raw_output = response.json().get("response", "")
        sql = self._clean_sql(raw_output)
        return self._fix_dialect(sql, db_type)

    # ------------------------------------------------------------------
    # Construção do prompt
    # ------------------------------------------------------------------

    def _build_prompt(self, question, schema_text, db_type="mysql"):
        """
        Monta o prompt que será enviado ao modelo.

        A estrutura é importante: o modelo precisa do schema para saber
        quais tabelas e colunas existem, e da pergunta para saber o que
        o usuário quer consultar.

        Parâmetros:
            question    (str): pergunta do usuário
            schema_text (str): schema do banco em formato texto
            db_type     (str): dialeto SQL ("mysql" ou "postgresql")

        Retorna:
            str: prompt completo formatado
        """
        dialect_rules = {
            "mysql": (
                "MySQL",
                "- Use LIKE (não ILIKE) para comparações de texto\n"
                "- Use YEAR(CURDATE()) para obter o ano atual\n"
                "- Use aspas simples para strings: WHERE col = 'valor'\n"
                "- Não use ILIKE, EXTRACT ou sintaxe exclusiva do PostgreSQL"
            ),
            "postgresql": (
                "PostgreSQL",
                "- Use ILIKE para comparações de texto sem distinção de maiúsculas\n"
                "- Use EXTRACT(YEAR FROM CURRENT_DATE) para obter o ano atual\n"
                "- Use aspas simples para strings: WHERE col = 'valor'\n"
                "- Não use sintaxe exclusiva do MySQL"
            ),
        }
        dialect_name, dialect_specific = dialect_rules.get(
            db_type.lower(), dialect_rules["mysql"]
        )

        return f"""Você é um especialista em SQL. Sua tarefa é converter perguntas em linguagem natural para queries SQL válidas para {dialect_name}.

Regras gerais:
- Retorne APENAS a query SQL, sem explicações, comentários ou formatação markdown
- Use apenas as tabelas e colunas presentes no schema fornecido
- Sempre use JOIN explícito quando precisar de dados de mais de uma tabela
- Nunca referencie uma tabela no WHERE sem incluí-la no FROM ou em um JOIN
- Use aspas simples para valores de string, nunca aspas duplas
- Ao filtrar por texto, use EXATAMENTE um dos "valores possíveis" listados no schema para aquela coluna, respeitando idioma e grafia originais (ex: se a coluna lista 'Music', use 'Music', não traduza para 'Música')
- Se a pergunta não puder ser respondida com o schema fornecido, retorne: SELECT 'Não foi possível gerar uma query para esta pergunta'

Regras específicas para {dialect_name}:
{dialect_specific}

Schema do banco de dados:
{schema_text}

Pergunta: {question}

SQL:"""

    # ------------------------------------------------------------------
    # Limpeza da saída
    # ------------------------------------------------------------------

    def _clean_sql(self, raw_text):
        """
        Remove formatação indesejada do texto retornado pelo modelo.

        Modelos de linguagem frequentemente retornam SQL envolvido em
        blocos de código markdown (```sql ... ```). Este método extrai
        apenas o SQL puro.

        Parâmetros:
            raw_text (str): texto bruto retornado pelo modelo

        Retorna:
            str: SQL limpo e pronto para execução
        """
        text = raw_text.strip()

        # Remove blocos markdown: ```sql ... ``` ou ``` ... ```
        # re.DOTALL faz o ponto (.) capturar quebras de linha também
        match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()

        # Remove prefixos comuns que o modelo pode adicionar
        # Ex: "SQL: SELECT ..." ou "Query: SELECT ..."
        text = re.sub(r"^(sql|query)\s*:\s*", "", text, flags=re.IGNORECASE)

        # Remove linhas de comentário SQL (--) e linhas em branco no início.
        # Alguns modelos respondem só com comentários explicativos, o que
        # faria o banco executar "nada" e falhar com "No result set to fetch".
        lines = text.splitlines()
        while lines and (not lines[0].strip() or lines[0].strip().startswith("--")):
            lines.pop(0)
        text = "\n".join(lines).strip()

        # Se o modelo retornou mais de uma instrução (ou repetiu o prompt
        # depois de um ';'), mantém apenas a primeira instrução
        if ";" in text:
            text = text.split(";")[0].strip()

        # Garante que o resultado é uma consulta de leitura. Se o modelo
        # devolveu texto explicativo ou nada utilizável, falha com uma
        # mensagem clara em vez de mandar lixo para o banco.
        if not text or not re.match(r"^\s*(SELECT|WITH)\b", text, re.IGNORECASE):
            raise Exception(
                "O modelo não retornou uma consulta SELECT válida.\n"
                f"Resposta recebida:\n{raw_text.strip()[:500]}\n\n"
                "Tente reformular a pergunta ou usar outro modelo."
            )

        return text

    def _fix_dialect(self, sql, db_type):
        """
        Corrige construções de dialeto errado que o modelo insiste em gerar.

        Modelos fine-tunados para SQL (como o sqlcoder) foram treinados
        majoritariamente com PostgreSQL e podem gerar sintaxe exclusiva
        desse dialeto mesmo quando o prompt pede MySQL. Este método faz
        traduções seguras após a geração.

        Parâmetros:
            sql     (str): query gerada pelo modelo
            db_type (str): dialeto alvo ("mysql" ou "postgresql")

        Retorna:
            str: query ajustada ao dialeto
        """
        if db_type.lower() == "mysql":
            # ILIKE não existe no MySQL; LIKE já é case-insensitive
            # nas collations padrão (ex: utf8mb4_general_ci)
            sql = re.sub(r"\bILIKE\b", "LIKE", sql, flags=re.IGNORECASE)

            # Cast estilo PostgreSQL: coluna::tipo → remove o cast
            sql = re.sub(r"::\s*\w+", "", sql)

        return sql

    # ------------------------------------------------------------------
    # Utilitário
    # ------------------------------------------------------------------

    def list_models(self):
        """
        Lista os modelos disponíveis no Ollama local.
        Útil para verificar se o modelo configurado está instalado.

        Retorna:
            list[str]: nomes dos modelos instalados

        Lança:
            ConnectionError se o Ollama não estiver acessível
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            models = response.json().get("models", [])
            return [m["name"] for m in models]

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Não foi possível conectar ao Ollama em {self.base_url}.\n"
                "Verifique se o Ollama está rodando (execute: ollama serve)"
            )

    def is_model_available(self):
        """
        Verifica se o modelo configurado está instalado no Ollama.

        Retorna:
            bool: True se disponível, False caso contrário
        """
        try:
            models = self.list_models()
            # Verifica se o nome do modelo está na lista (parcial ou completo)
            return any(self.model in m for m in models)
        except Exception:
            return False
