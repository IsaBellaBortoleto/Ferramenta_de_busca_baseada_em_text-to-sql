"""
main.py
-------
Ponto de entrada da aplicação Text-to-SQL.

Como executar:
    python main.py

Pré-requisitos:
    1. Dependências instaladas:  pip install -r requirements.txt
    2. Ollama rodando:           ollama serve
    3. Modelo disponível:        ollama pull qwen2.5-coder:7b
    4. Banco de dados acessível (MySQL ou PostgreSQL)
"""

from gui import App


if __name__ == "__main__":
    app = App()
    app.mainloop()  # inicia o loop de eventos do Tkinter
                    # o programa fica aqui até a janela ser fechada
