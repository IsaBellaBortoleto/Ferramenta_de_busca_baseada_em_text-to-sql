## <h1 align="center">Ferramenta de Busca Baseada em Text-to-SQL</h1>

<img src="https://github.com/IsaBellaBortoleto/Ferramenta_de_busca_baseada_em_text-to-sql/blob/main/images/resultado_consulta.png" width="750">
<br/>
Figura 1. 
Ferramenta desktop que permite realizar consultas em bancos de dados relacionais usando **linguagem natural**. O usuário digita uma pergunta em português, e a ferramenta converte automaticamente para SQL utilizando um modelo de linguagem local via Ollama.

---

## Tecnologias utilizadas

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.10+ |
| Interface gráfica | Tkinter |
| LLM local | Ollama + modelo `qwen2.5-coder:7b` |
| Banco de dados | MySQL e PostgreSQL |

---

## Pré-requisitos

### Em todas as máquinas

1. **Python 3.10 ou superior**
   - Verificar versão: `python --version`
   - Download: https://python.org

2. **Ollama instalado e rodando**
   - Download: https://ollama.com
   - Após instalar, baixar o modelo:
     ```bash
     ollama pull qwen2.5-coder:7b
     ```
   - **Em máquinas com pouca RAM ou sem GPU** (notebooks antigos), use a versão menor, que responde muito mais rápido:
     ```bash
     ollama pull qwen2.5-coder:1.5b
     ```
     e digite `qwen2.5-coder:1.5b` no campo **Modelo** da interface.
   - Iniciar o servidor (se não iniciar automaticamente):
     ```bash
     ollama serve
     ```

3. **MySQL ou PostgreSQL acessível** (local ou remoto)

### Somente no Ubuntu

```bash
sudo apt install python3-tk
```

---

## Instalação

```bash
# 1. Clone ou copie a pasta do projeto
cd text-to-sql

# 2. Instale as dependências Python
pip install -r requirements.txt
```

---

## Como executar

```bash
python main.py
```

---

## Como usar

1. Preencha os dados de conexão (host, porta, usuário, senha, banco, tipo)
2. Clique em **Conectar** — as tabelas do banco serão carregadas automaticamente
3. Digite sua pergunta em linguagem natural no campo de consulta
   - Exemplo: *"Quais clientes fizeram pedidos acima de R$ 500 este mês?"*
4. Clique em **Consultar** — o SQL gerado será exibido, seguido dos resultados

---

## Funcionalidades

- **Conexão com MySQL e PostgreSQL** através de uma interface única (a aplicação não muda conforme o banco).
- **Carregamento automático do esquema** (tabelas e colunas) a partir do `information_schema`.
- **Geração de SQL por LLM local** via Ollama, com regras de dialeto específicas para cada banco.
- **Value linking:** o esquema enviado ao modelo inclui exemplos de valores reais das colunas de texto com poucos valores distintos (ex: `dept_name → 'Music', 'Physics'`), para o modelo usar o literal correto em vez de traduzi-lo.
- **Validação de segurança:** apenas consultas `SELECT` são executadas; comandos como `DROP`, `DELETE`, `UPDATE` e múltiplos statements são bloqueados antes de chegar ao banco (defesa contra *prompt injection*).
- **Correção automática de dialeto** (ex: `ILIKE` → `LIKE` no MySQL) e **auto-retry:** se a query falhar, o erro do banco é reenviado ao modelo para uma segunda tentativa corrigida.
- **Interface em modo escuro**, com SQL gerado redimensionável e barra de progresso durante o processamento.

---

## Estrutura do projeto

```
text-to-sql/
│
├── main.py            # Ponto de entrada da aplicação
├── db_connector.py    # Conexão com MySQL/PostgreSQL e leitura de schema
├── llm_client.py      # Integração com Ollama (conversão NL → SQL)
├── gui.py             # Interface gráfica (Tkinter)
└── requirements.txt   # Dependências Python
```

---

## Como funciona

```
Usuário digita pergunta
        ↓
db_connector.py lê o schema (tabelas, colunas e exemplos de valores)
        ↓
llm_client.py monta um prompt com:
  - schema do banco + regras de dialeto
  - pergunta do usuário
        ↓
Ollama processa e retorna a query SQL
        ↓
llm_client.py limpa e valida o SQL (corrige dialeto, garante que é SELECT)
        ↓
db_connector.py valida (só SELECT) e executa a query no banco
        ↓
  └─ se a query falhar, o erro é reenviado ao modelo (auto-retry)
        ↓
gui.py exibe os resultados em tabela
```

---

## Compatibilidade

| Sistema Operacional | Suportado |
|---|---|
| Windows 10 | ✓ |
| Windows 11 | ✓ |
| Ubuntu 22.04 | ✓ (requer `python3-tk`) |

---

## Dependências Python

| Biblioteca | Versão | Finalidade |
|---|---|---|
| mysql-connector-python | 8.3.0 | Conexão com MySQL |
| psycopg2-binary | 2.9.9 | Conexão com PostgreSQL |
| requests | 2.31.0 | Chamadas HTTP para a API do Ollama |
| tkinter | (built-in) | Interface gráfica |

---

## Observações

- O Ollama precisa estar rodando **antes** de iniciar a aplicação
- O modelo `qwen2.5-coder` é especializado em código (incluindo SQL) e segue bem as instruções de dialeto do prompt; modelos antigos fine-tunados só em PostgreSQL (como o `sqlcoder`) tendem a gerar sintaxe inválida para MySQL
- A qualidade das queries geradas depende da clareza da pergunta e da estrutura do banco
- **Desempenho:** a **primeira** consulta é mais lenta porque o modelo é carregado na memória; as seguintes são rápidas. A aplicação mantém o modelo carregado por 30 minutos entre consultas (`keep_alive`). Em máquinas sem GPU, prefira o modelo `1.5b` e mantenha apenas o necessário aberto para liberar RAM
- Apenas consultas de **leitura** (`SELECT`) são suportadas — por design, por segurança. Recomenda-se ainda conectar com um usuário de banco que tenha somente privilégio de leitura
