"""
gui.py
------
Interface gráfica da ferramenta Text-to-SQL usando Tkinter.

Layout:
    - Painel superior: configurações de conexão com o banco
    - Painel esquerdo: lista de tabelas (schema)
    - Painel direito: campo de consulta, SQL gerado e tabela de resultados
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

from db_connector import DatabaseConnector
from llm_client import OllamaClient


class App(tk.Tk):
    """
    Janela principal da aplicação.
    Herda de tk.Tk para ser ela mesma a janela raiz.
    """

    def __init__(self):
        super().__init__()

        self.title("Ferramenta Text-to-SQL")
        self.geometry("1400x700")
        self.minsize(1000, 600)

        # Objetos de negócio (preenchidos ao conectar)
        self.db: DatabaseConnector = None
        self.llm: OllamaClient = None

        self._setup_style()
        self._build_ui()

    # ------------------------------------------------------------------
    # Tema visual
    # ------------------------------------------------------------------

    def _setup_style(self):
        """
        Configura o tema visual da aplicação (cores, fontes e estilos ttk).
        Centralizar tudo aqui permite ajustar o visual em um único lugar.
        Tema atual: dark mode em tons de azul-ardósia (slate).
        """
        # Paleta de cores da aplicação (dark mode)
        self.COLOR_BG = "#191a1b"         # fundo geral
        self.COLOR_FIELD_BG = "#121314"   # fundo de campos, listas e tabela
        self.COLOR_BORDER = "#334155"     # bordas, botões secundários
        self.COLOR_TEXT = "#e2e8f0"       # texto principal (claro)
        self.COLOR_TEXT_MUTED = "#94a3b8" # texto secundário (status)
        self.COLOR_ACCENT = "#3b82f6"     # azul dos botões principais
        self.COLOR_ACCENT_DARK = "#2563eb"
        self.COLOR_SQL_BG = "#121314"     # fundo do campo SQL
        self.COLOR_SQL_FG = "#7dd3fc"     # texto azul-claro, estilo editor
        self.COLOR_ROW_ALT = "#27374d"    # linhas alternadas da tabela

        self.configure(background=self.COLOR_BG)

        style = ttk.Style(self)
        style.theme_use("clam")  # tema base mais moderno que o padrão do Tk

        default_font = ("Segoe UI", 10)
        style.configure(
            ".", font=default_font,
            background=self.COLOR_BG, foreground=self.COLOR_TEXT
        )

        # Painéis com título (LabelFrame)
        # lightcolor/darkcolor são as linhas do relevo 3D do tema clam;
        # por padrão são claras, então recebem as cores do tema escuro
        style.configure(
            "TLabelframe", background=self.COLOR_BG,
            bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_BG, darkcolor=self.COLOR_BG
        )
        style.configure(
            "TLabelframe.Label", background=self.COLOR_BG,
            font=("Segoe UI", 10, "bold"), foreground=self.COLOR_TEXT
        )

        # Campos de entrada (Entry e Combobox)
        style.configure(
            "TEntry", fieldbackground=self.COLOR_FIELD_BG,
            foreground=self.COLOR_TEXT, insertcolor=self.COLOR_TEXT,
            bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_FIELD_BG, darkcolor=self.COLOR_FIELD_BG
        )
        style.configure(
            "TCombobox", fieldbackground=self.COLOR_FIELD_BG,
            foreground=self.COLOR_TEXT, arrowcolor=self.COLOR_TEXT,
            background=self.COLOR_BORDER, bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_FIELD_BG, darkcolor=self.COLOR_FIELD_BG
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.COLOR_FIELD_BG)],
            foreground=[("readonly", self.COLOR_TEXT)]
        )
        # A lista suspensa do Combobox é um Listbox clássico do Tk,
        # então é configurada via option_add (não via ttk.Style)
        self.option_add("*TCombobox*Listbox*Background", self.COLOR_FIELD_BG)
        self.option_add("*TCombobox*Listbox*Foreground", self.COLOR_TEXT)
        self.option_add("*TCombobox*Listbox*selectBackground", self.COLOR_ACCENT)

        # Botões comuns (Limpar)
        style.configure(
            "TButton", background=self.COLOR_BORDER,
            foreground=self.COLOR_TEXT, padding=(10, 5),
            bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_BORDER, darkcolor=self.COLOR_BORDER
        )
        style.map("TButton", background=[("active", "#475569")])

        # Botões de destaque (Conectar / Consultar)
        style.configure(
            "Accent.TButton",
            background=self.COLOR_ACCENT, foreground="white",
            font=("Segoe UI", 10, "bold"), padding=(10, 5),
            bordercolor=self.COLOR_ACCENT,
            lightcolor=self.COLOR_ACCENT, darkcolor=self.COLOR_ACCENT
        )
        style.map(
            "Accent.TButton",
            background=[("active", self.COLOR_ACCENT_DARK),
                        ("disabled", "#475569")],
            foreground=[("disabled", self.COLOR_TEXT_MUTED)]
        )

        # Barras de rolagem — estilo minimalista (sem setas, polegar fino)
        # Redefinir o layout remove os botões de seta das pontas,
        # deixando apenas o trilho e o polegar
        style.layout("Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
            ]})
        ])
        style.layout("Horizontal.TScrollbar", [
            ("Horizontal.Scrollbar.trough", {"sticky": "ew", "children": [
                ("Horizontal.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
            ]})
        ])
        scrollbar_thumb = "#3a3d40"   # polegar discreto, um tom acima do fundo
        style.configure(
            "TScrollbar",
            background=scrollbar_thumb,
            troughcolor=self.COLOR_FIELD_BG,   # trilho se funde com o campo
            bordercolor=self.COLOR_FIELD_BG,
            lightcolor=scrollbar_thumb, darkcolor=scrollbar_thumb,
            gripcount=0,  # remove os "risquinhos" do polegar no tema clam
            width=10      # barra mais fina que o padrão
        )
        # Clareia o polegar ao passar o mouse / arrastar
        style.map("TScrollbar", background=[("active", "#54585c")])
        style.configure(
            "Horizontal.TProgressbar",
            background=self.COLOR_ACCENT, troughcolor=self.COLOR_FIELD_BG,
            bordercolor=self.COLOR_FIELD_BG,
            lightcolor=self.COLOR_ACCENT, darkcolor=self.COLOR_ACCENT
        )

        # Tabela de resultados
        style.configure(
            "Treeview", rowheight=26, font=default_font,
            background=self.COLOR_FIELD_BG, foreground=self.COLOR_TEXT,
            fieldbackground=self.COLOR_FIELD_BG, bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_FIELD_BG, darkcolor=self.COLOR_FIELD_BG
        )
        style.configure(
            "Treeview.Heading", font=("Segoe UI", 10, "bold"),
            background=self.COLOR_BORDER, foreground=self.COLOR_TEXT, padding=4,
            bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_BORDER, darkcolor=self.COLOR_BORDER
        )
        style.map(
            "Treeview",
            background=[("selected", self.COLOR_ACCENT)],
            foreground=[("selected", "white")]
        )
        style.map("Treeview.Heading", background=[("active", "#475569")])

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Monta todos os widgets da janela."""
        self._build_connection_panel()
        self._build_main_panel()

    def _build_connection_panel(self):
        """
        Painel superior com os campos de conexão ao banco de dados
        e ao servidor Ollama.
        """
        frame = ttk.LabelFrame(self, text="Conexão", padding=10)
        frame.pack(fill=tk.X, padx=12, pady=(12, 0))

        # ── Linha 0: banco de dados ─────────────────────────────────────

        ttk.Label(frame, text="Tipo:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.var_db_type = tk.StringVar(value="mysql")
        cb_type = ttk.Combobox(
            frame, textvariable=self.var_db_type,
            values=["mysql", "postgresql"], width=12, state="readonly"
        )
        cb_type.grid(row=0, column=1, padx=(4, 18), sticky=tk.W)

        ttk.Label(frame, text="Host:").grid(row=0, column=2, sticky=tk.W)
        self.entry_host = ttk.Entry(frame, width=16)
        self.entry_host.insert(0, "localhost")
        self.entry_host.grid(row=0, column=3, padx=(4, 18))

        ttk.Label(frame, text="Porta:").grid(row=0, column=4, sticky=tk.W)
        self.entry_port = ttk.Entry(frame, width=7)
        self.entry_port.insert(0, "3306")
        self.entry_port.grid(row=0, column=5, padx=(4, 18))

        ttk.Label(frame, text="Usuário:").grid(row=0, column=6, sticky=tk.W)
        self.entry_user = ttk.Entry(frame, width=14)
        self.entry_user.grid(row=0, column=7, padx=(4, 18))

        ttk.Label(frame, text="Senha:").grid(row=0, column=8, sticky=tk.W)
        self.entry_password = ttk.Entry(frame, width=14, show="*")
        self.entry_password.grid(row=0, column=9, padx=(4, 18))

        ttk.Label(frame, text="Banco:").grid(row=0, column=10, sticky=tk.W)
        self.entry_database = ttk.Entry(frame, width=16)
        self.entry_database.grid(row=0, column=11, padx=(4, 0))

        # ── Linha 1: Ollama + botão conectar ────────────────────────────

        ttk.Label(frame, text="Ollama Host:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.entry_ollama_host = ttk.Entry(frame, width=16)
        self.entry_ollama_host.insert(0, "localhost")
        self.entry_ollama_host.grid(row=1, column=1, padx=(4, 18), sticky=tk.W)

        ttk.Label(frame, text="Modelo:").grid(row=1, column=2, sticky=tk.W)
        self.entry_model = ttk.Entry(frame, width=20)
        self.entry_model.insert(0, "qwen2.5-coder:7b")
        self.entry_model.grid(row=1, column=3, columnspan=3, padx=(4, 18), sticky=tk.W)

        self.btn_connect = ttk.Button(
            frame, text="Conectar", style="Accent.TButton",
            command=self._on_connect
        )
        self.btn_connect.grid(row=1, column=11, padx=(4, 0), sticky=tk.E)

        # Atualiza a porta padrão ao mudar o tipo de banco
        self.var_db_type.trace_add("write", self._on_db_type_change)

    def _build_main_panel(self):
        """
        Área principal dividida em dois painéis:
        esquerdo (schema) e direito (consulta + resultados).
        """
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self._build_schema_panel(paned)
        self._build_query_panel(paned)

    def _build_schema_panel(self, parent):
        """
        Painel esquerdo: exibe as tabelas do banco conectado.
        """
        frame = ttk.LabelFrame(parent, text="Schema", padding=5)
        parent.add(frame, weight=1)

        self.listbox_tables = tk.Listbox(
            frame, selectmode=tk.SINGLE,
            font=("Segoe UI", 10),
            borderwidth=0, highlightthickness=0,  # remove a borda "afundada"
            background=self.COLOR_FIELD_BG, foreground=self.COLOR_TEXT,
            activestyle="none",
            selectbackground=self.COLOR_ACCENT, selectforeground="white"
        )
        scrollbar = ttk.Scrollbar(
            frame, orient=tk.VERTICAL, command=self.listbox_tables.yview
        )
        self.listbox_tables.configure(yscrollcommand=scrollbar.set)

        self.listbox_tables.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Ao clicar em uma tabela, mostra suas colunas na área de consulta
        self.listbox_tables.bind("<<ListboxSelect>>", self._on_table_select)

    def _build_query_panel(self, parent):
        """
        Painel direito com três seções empilhadas:
        1. Campo de pergunta em linguagem natural
        2. SQL gerado
        3. Tabela de resultados
        """
        frame = ttk.Frame(parent)
        parent.add(frame, weight=4)

        # ── 1. Pergunta em linguagem natural ────────────────────────────

        lf_query = ttk.LabelFrame(frame, text="Consulta em linguagem natural", padding=5)
        lf_query.pack(fill=tk.X, pady=(0, 5))

        self.text_question = tk.Text(
            lf_query, height=3, wrap=tk.WORD,
            font=("Segoe UI", 11),
            relief=tk.FLAT, highlightthickness=0,  # sem anel de foco claro
            background=self.COLOR_FIELD_BG, foreground=self.COLOR_TEXT,
            insertbackground=self.COLOR_TEXT,  # cor do cursor de texto
            padx=8, pady=6
        )
        self.text_question.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.text_question.bind("<Return>", self._on_enter_key)

        btn_frame = ttk.Frame(lf_query)
        btn_frame.pack(side=tk.RIGHT, padx=(5, 0))

        self.btn_query = ttk.Button(
            btn_frame, text="Consultar", style="Accent.TButton",
            command=self._on_query, state=tk.DISABLED
        )
        self.btn_query.pack()

        self.btn_clear = ttk.Button(
            btn_frame, text="Limpar", command=self._on_clear
        )
        self.btn_clear.pack(pady=(5, 0))

        # ── Barra de progresso (visível apenas durante o processamento) ──

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 5))
        self.progress.pack_forget()  # começa oculta

        # ── Painel vertical redimensionável: SQL gerado ⇕ Resultados ─────
        # O usuário pode arrastar a divisória entre as duas seções para
        # dar mais espaço ao SQL ou aos resultados.

        self.paned_right = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        self.paned_right.pack(fill=tk.BOTH, expand=True)

        # ── 2. SQL gerado ────────────────────────────────────────────────

        lf_sql = ttk.LabelFrame(self.paned_right, text="SQL gerado", padding=5)
        self.paned_right.add(lf_sql, weight=1)

        # Visual de editor de código: fundo escuro + fonte monoespaçada
        self.text_sql = tk.Text(
            lf_sql, height=4, wrap=tk.WORD,
            state=tk.DISABLED,  # somente leitura
            font=("Consolas", 10),
            background=self.COLOR_SQL_BG, foreground=self.COLOR_SQL_FG,
            relief=tk.FLAT, highlightthickness=0,  # sem anel de foco claro
            padx=8, pady=6
        )
        self.text_sql.pack(fill=tk.BOTH, expand=True)

        # ── 3. Resultados ────────────────────────────────────────────────

        lf_results = ttk.LabelFrame(self.paned_right, text="Resultados", padding=5)
        self.paned_right.add(lf_results, weight=3)

        # Treeview com scrollbars horizontal e vertical
        self.tree = ttk.Treeview(lf_results, show="headings")

        scroll_y = ttk.Scrollbar(lf_results, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(lf_results, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # ── Barra de status ──────────────────────────────────────────────

        self.var_status = tk.StringVar(value="Aguardando conexão...")
        ttk.Label(
            frame, textvariable=self.var_status, anchor=tk.W,
            foreground=self.COLOR_TEXT_MUTED
        ).pack(fill=tk.X, pady=(6, 0))

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def _on_db_type_change(self, *args):
        """Atualiza a porta padrão ao trocar o tipo de banco."""
        defaults = {"mysql": "3306", "postgresql": "5432"}
        db_type = self.var_db_type.get()
        self.entry_port.delete(0, tk.END)
        self.entry_port.insert(0, defaults.get(db_type, ""))

    def _on_connect(self):
        """
        Tenta conectar ao banco de dados com as credenciais informadas.
        Em caso de sucesso, carrega as tabelas no painel de schema
        e habilita o botão de consulta.
        """
        # Lê os valores dos campos
        host = self.entry_host.get().strip()
        port = self.entry_port.get().strip()
        user = self.entry_user.get().strip()
        password = self.entry_password.get()
        database = self.entry_database.get().strip()
        db_type = self.var_db_type.get()
        ollama_host = self.entry_ollama_host.get().strip()
        model = self.entry_model.get().strip()

        # Validação básica dos campos obrigatórios
        if not all([host, port, user, database]):
            messagebox.showerror("Erro", "Preencha todos os campos de conexão.")
            return

        try:
            port = int(port)
        except ValueError:
            messagebox.showerror("Erro", "A porta deve ser um número inteiro.")
            return

        # Desconecta qualquer conexão anterior
        if self.db:
            self.db.disconnect()

        # Sinaliza o processo e conecta em thread separada,
        # para a interface não congelar enquanto o banco responde
        self._set_busy(True, f"Conectando a '{database}'...")
        thread = threading.Thread(
            target=self._run_connect,
            args=(host, port, user, password, database, db_type, ollama_host, model),
            daemon=True
        )
        thread.start()

    def _run_connect(self, host, port, user, password, database, db_type,
                     ollama_host, model):
        """
        Executado em thread separada: conecta ao banco e carrega as tabelas.
        A GUI é atualizada de volta na thread principal via after().
        """
        try:
            db = DatabaseConnector(host, port, user, password, database, db_type)
            db.connect()
            llm = OllamaClient(host=ollama_host, model=model)
            tables = db.get_table_names()

            def on_success():
                self.db = db
                self.llm = llm
                self.listbox_tables.delete(0, tk.END)
                for table in tables:
                    self.listbox_tables.insert(tk.END, table)
                self.var_status.set(
                    f"Conectado a '{database}' ({db_type}) — {len(tables)} tabela(s) encontrada(s)"
                )

            self.after(0, on_success)

        except Exception as e:
            error_msg = str(e)  # captura antes, pois 'e' não existe fora do except

            def on_error():
                messagebox.showerror("Erro de conexão", error_msg)
                self.var_status.set("Falha na conexão.")

            self.after(0, on_error)

        finally:
            # Reabilita os botões (o de consulta só se a conexão deu certo)
            self.after(0, self._set_busy, False)

    def _on_table_select(self, event):
        """
        Ao clicar em uma tabela na listbox, exibe suas colunas
        na área de SQL gerado como referência para o usuário.
        """
        selection = self.listbox_tables.curselection()
        if not selection or not self.db:
            return

        table_name = self.listbox_tables.get(selection[0])
        schema = self.db.get_schema()
        columns = schema.get(table_name, [])

        info = f"-- Tabela: {table_name}\n"
        info += "\n".join(f"--   {col} ({dtype})" for col, dtype in columns)

        self._set_sql_text(info)

    def _on_enter_key(self, event):
        """Permite acionar a consulta com Ctrl+Enter."""
        if event.state & 0x4:  # Ctrl pressionado
            self._on_query()
            return "break"  # impede que o Enter adicione linha no campo

    def _on_query(self):
        """
        Lê a pergunta do usuário e inicia o processo de geração SQL
        em uma thread separada para não travar a interface.
        """
        if not self.db or not self.llm:
            messagebox.showwarning("Aviso", "Conecte-se ao banco primeiro.")
            return

        question = self.text_question.get("1.0", tk.END).strip()
        if not question:
            messagebox.showwarning("Aviso", "Digite uma pergunta.")
            return

        # Sinaliza o processamento (cursor, botões e barra de progresso)
        self._clear_results()
        self._set_busy(True, "Gerando SQL...")

        # Executa em thread separada para não travar a GUI
        thread = threading.Thread(target=self._run_query, args=(question,), daemon=True)
        thread.start()

    def _run_query(self, question):
        """
        Executado em thread separada:
        1. Obtém o schema do banco
        2. Envia ao Ollama para gerar o SQL
        3. Executa o SQL no banco
        4. Se a query falhar, envia o erro de volta ao modelo e tenta
           uma vez mais com a versão corrigida (auto-correção)
        5. Atualiza a GUI com os resultados (via after, thread-safe)
        """
        try:
            schema_text = self.db.get_schema_text()
            sql = self.llm.generate_sql(question, schema_text, db_type=self.db.db_type)

            # Exibe o SQL gerado
            self.after(0, self._set_sql_text, sql)
            self.after(0, self.var_status.set, "Executando query...")

            # Executa a query no banco; se falhar, dá ao modelo a chance
            # de se corrigir usando a mensagem de erro do próprio banco
            try:
                columns, rows = self.db.execute_query(sql)
            except Exception as db_error:
                self.after(0, self.var_status.set,
                           "Query falhou — pedindo correção ao modelo...")
                sql = self.llm.fix_sql(
                    question, schema_text, sql, str(db_error),
                    db_type=self.db.db_type
                )
                self.after(0, self._set_sql_text, sql)
                self.after(0, self.var_status.set, "Executando query corrigida...")
                columns, rows = self.db.execute_query(sql)

            # Atualiza a tabela de resultados na thread principal
            self.after(0, self._populate_results, columns, rows)
            self.after(0, self.var_status.set,
                       f"Consulta concluída — {len(rows)} registro(s) retornado(s)")

        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", str(e))
            self.after(0, self.var_status.set, "Erro ao processar a consulta.")

        finally:
            # Sempre encerra a sinalização de processamento
            self.after(0, self._set_busy, False)

    # ------------------------------------------------------------------
    # Manipulação dos widgets de resultado
    # ------------------------------------------------------------------

    def _set_sql_text(self, sql):
        """Exibe o SQL gerado no campo somente-leitura."""
        self.text_sql.config(state=tk.NORMAL)
        self.text_sql.delete("1.0", tk.END)
        self.text_sql.insert("1.0", sql)
        self.text_sql.config(state=tk.DISABLED)

    def _populate_results(self, columns, rows):
        """
        Preenche o Treeview com os resultados da query.

        Parâmetros:
            columns (list[str]): nomes das colunas
            rows    (list[tuple]): linhas de dados
        """
        # Limpa resultados anteriores
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = columns

        # Configura cabeçalhos
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140, anchor=tk.W)

        # Linhas alternadas (zebra) para facilitar a leitura
        self.tree.tag_configure("alt", background=self.COLOR_ROW_ALT)

        # Insere as linhas
        for i, row in enumerate(rows):
            self.tree.insert(
                "", tk.END,
                values=[str(v) if v is not None else "NULL" for v in row],
                tags=("alt",) if i % 2 else ()
            )

    def _on_clear(self):
        """
        Botão Limpar: apaga a pergunta em linguagem natural,
        o SQL gerado e a tabela de resultados.
        """
        self.text_question.delete("1.0", tk.END)
        self._clear_results()

    def _clear_results(self):
        """
        Limpa o campo SQL e a tabela de resultados.
        (Não apaga a pergunta — é chamado também ao iniciar uma consulta.)
        """
        self._set_sql_text("")
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = []

    def _set_busy(self, busy, message=None):
        """
        Sinaliza visualmente que há um processo em andamento:
        cursor de espera, botões desabilitados e barra de progresso animada.

        Parâmetros:
            busy    (bool): True ao iniciar o processo, False ao terminar
            message (str): texto opcional para a barra de status
        """
        if message is not None:
            self.var_status.set(message)

        if busy:
            self.config(cursor="watch")  # cursor de espera na janela toda
            self.btn_connect.config(state=tk.DISABLED)
            self.btn_query.config(state=tk.DISABLED)
            # 'before' garante que a barra apareça sempre na mesma posição
            self.progress.pack(fill=tk.X, pady=(0, 5), before=self.paned_right)
            self.progress.start(10)
        else:
            self.config(cursor="")
            self.btn_connect.config(state=tk.NORMAL)
            # O botão de consulta só é habilitado se houver conexão ativa
            connected = self.db is not None and self.db.is_connected()
            self.btn_query.config(state=tk.NORMAL if connected else tk.DISABLED)
            self.progress.stop()
            self.progress.pack_forget()
