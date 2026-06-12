# Ferramenta de Busca Baseada em Text-to-SQL

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
llm_client.py monta um prompt com:
  - schema do banco (tabelas e colunas)
  - pergunta do usuário
        ↓
Ollama processa e retorna a query SQL
        ↓
db_connector.py executa a query no banco
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
- O modelo `qwen2.5-coder:7b` é especializado em código (incluindo SQL) e segue bem as instruções de dialeto do prompt; modelos antigos fine-tunados só em PostgreSQL (como o `sqlcoder`) tendem a gerar sintaxe inválida para MySQL
- A qualidade das queries geradas depende da clareza da pergunta e da estrutura do banco
