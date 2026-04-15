import customtkinter as ctk
from tkinter import messagebox
from database import init_db, export_to_dict, save_all_from_dict

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def carregar():
	dados = export_to_dict()

	if "meses" not in dados:
		dados["meses"] = {}

	mes_atual = dados.get("mes_atual", "2026-04")

	if mes_atual not in dados["meses"]:
		dados["meses"][mes_atual] = {"despesas": {}}

	return dados

def guardar(dados):
	save_all_from_dict(dados)

class App(ctk.CTk):
	def __init__(self):
		super().__init__()

		self.title("Finanças 💰")
		self.geometry("1024x768")
		self.resizable(False, False)

		init_db()
		self.dados = carregar()

		# estado visual
		self.active_button = None
		self.sidebar_buttons = []
		self.active_card = None

		# ===== LAYOUT =====
		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=1)

		# ===== SIDEBAR =====
		self.sidebar = ctk.CTkFrame(self, width=220)
		self.sidebar.grid(row=0, column=0, sticky="ns")
		self.sidebar.grid_propagate(False)
		self.sidebar.grid_rowconfigure(0, weight=1)

		self.sidebar_top = ctk.CTkFrame(self.sidebar, fg_color="transparent")
		self.sidebar_top.grid(row=0, column=0, sticky="nw", padx=0, pady=10)

		self.sidebar_bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
		self.sidebar_bottom.grid(row=1, column=0, sticky="sew", padx=0, pady=10)

		# ===== MAIN =====
		self.main = ctk.CTkFrame(self)
		self.main.grid(row=0, column=1, sticky="nsew")

		# ===== MENU =====
		self.criar_botao("🏠 Dashboard", self.mostrar_resumo, parent=self.sidebar_top)

		self.criar_dropdown("💸 Despesas", [
			("Ver despesas", self.mostrar_despesas),
			("Categorias", self.mostrar_categorias),
		], parent=self.sidebar_top)

		self.criar_dropdown("💼 Valores", [
			("Rendimentos", self.mostrar_rendimentos),
			("Dívidas", self.mostrar_dividas),
			("Pendentes", self.mostrar_pendentes),
			("Progresso", self.mostrar_progresso_dividas),
		], parent=self.sidebar_top)

		self.criar_dropdown("📅 Planeamento", [
			("Visão geral", self.mostrar_planeamento),
			("Timeline", self.timeline_divida),
			("Simulação", self.modo_dividas),
			("Análise", self.analise_financeira),
			("Histórico", self.mostrar_historico),
			("Metas", self.mostrar_metas),
		], parent=self.sidebar_top)

		self.criar_dropdown("⚙️ Sistema", [
			("Meses", self.mostrar_meses),
			("Despesas fixas", self.mostrar_despesas_fixas),
			("Contribuições", self.mostrar_contribuicoes),
			("Saldo inicial", self.mostrar_saldo_inicial),
		], parent=self.sidebar_top)

		self.btn_sair = ctk.CTkButton(
			self.sidebar_bottom,
			text="🚪 Sair",
			width=200,
			anchor="w",
			fg_color="#8B0000",
			hover_color="#A00000",
			command=self.sair
		)
		self.btn_sair.pack(padx=10, pady=(0, 10))

		self.protocol("WM_DELETE_WINDOW", self.sair)

		self.mostrar_resumo()

	def set_active_button(self, button):
		if self.active_button is not None:
			self.active_button.configure(fg_color="#1f6aa5")

		self.active_button = button
		self.active_button.configure(fg_color="#144870")

	def bind_clickable_frame(self, frame, widgets, comando):
		def set_active(f):
			# reset anterior
			if self.active_card is not None:
				try:
					if self.active_card.winfo_exists():
						self.active_card.configure(fg_color="transparent")
				except:
					pass

			self.active_card = f
			f.configure(fg_color="#2a2a2a")

		def on_click(event=None):
			set_active(frame)
			comando()

		def on_enter(event=None):
			try:
				if not frame.winfo_exists():
					return

				if frame == self.active_card:
					frame.configure(fg_color="#353535")  # hover ativo
				else:
					frame.configure(fg_color="#3a3a3a")  # hover normal
			except:
				pass

		def on_leave(event=None):
			try:
				if not frame.winfo_exists():
					return

				if frame == self.active_card:
					frame.configure(fg_color="#2a2a2a")  # volta ativo
				else:
					frame.configure(fg_color="transparent")
			except:
				pass

		frame.bind("<Button-1>", on_click)
		frame.bind("<Enter>", on_enter)
		frame.bind("<Leave>", on_leave)

		for w in widgets:
			w.bind("<Button-1>", on_click)
			w.bind("<Enter>", on_enter)
			w.bind("<Leave>", on_leave)

	def criar_botao(self, texto, comando, parent=None):
		if parent is None:
			parent = self.sidebar_top

		btn = ctk.CTkButton(
			parent,
			text=texto,
			width=200,
			anchor="w",
			fg_color="#1f6aa5",
			hover_color="#2a7dc4"
		)

		def on_click():
			self.set_active_button(btn)
			comando()

		btn.configure(command=on_click)
		btn.pack(pady=(4, 0), padx=10)

		self.sidebar_buttons.append(btn)
		return btn

	def mostrar_historico(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="📚 Histórico Mensal", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		meses = sorted(self.dados["meses"].keys(), reverse=True)

		if not meses:
			ctk.CTkLabel(self.main, text="Ainda não tens meses registados.").pack(pady=20)
			return

		container = ctk.CTkScrollableFrame(self.main)
		container.pack(fill="both", expand=True, padx=20, pady=10)
		saldos = self.calcular_saldos_acumulados()

		salarios = self.total_entradas_mensais()
		prestacoes = sum(d["prestacao"] for d in self.dados["dividas"].values())

		for mes in meses:
			frame = ctk.CTkFrame(container)
			frame.pack(fill="x", pady=8)

			despesas_dict = self.dados["meses"][mes]["despesas"]
			total_despesas = 0
			categorias = {}

			for d in despesas_dict.values():
				if isinstance(d, dict):
					valor = d["valor"]
					cat = d["categoria"]
				else:
					valor = d
					cat = "Sem categoria"

				total_despesas += valor
				categorias[cat] = categorias.get(cat, 0) + valor

			disponivel = salarios - total_despesas - prestacoes
			saldo_acumulado = saldos.get(mes, {}).get("saldo", disponivel)
			score = self.calcular_score_mes(mes)
			total_itens = len(despesas_dict)

			if categorias:
				maior_categoria = max(categorias, key=categorias.get)
				maior_texto = f"{maior_categoria} ({categorias[maior_categoria]:.2f} CHF)"
			else:
				maior_texto = "Sem despesas"

			top = ctk.CTkFrame(frame, fg_color="transparent")
			top.pack(fill="x", padx=12, pady=(10, 5))

			ctk.CTkLabel(top, text=mes, font=("Arial", 16, "bold")).pack(side="left")

			cor = "green" if saldo_acumulado >= 0 else "red"
			ctk.CTkLabel(top, text=f"Saldo acumulado: {saldo_acumulado:.2f} CHF", text_color=cor).pack(side="right")

			body = ctk.CTkFrame(frame, fg_color="transparent")
			body.pack(fill="x", padx=12, pady=(0, 10))
			cor_sobra = "green" if disponivel >= 0 else "red"

			ctk.CTkLabel(body, text=f"💰 Sobra do mês: {disponivel:.2f} CHF", text_color=cor_sobra).pack(anchor="w")
			ctk.CTkLabel(body, text=f"💸 Despesas: {total_despesas:.2f} CHF").pack(anchor="w")
			ctk.CTkLabel(body, text=f"🧾 Nº de despesas: {total_itens}").pack(anchor="w")
			ctk.CTkLabel(body, text=f"🏷️ Maior categoria: {maior_texto}").pack(anchor="w")
			ctk.CTkLabel(body, text=f"📊 Score financeiro: {score}/100").pack(anchor="w")

	def calcular_score_mes(self, mes):
		dados = self.dados

		score = 0

		salarios = sum(dados["salarios"].values())

		despesas = 0
		for d in dados["meses"][mes]["despesas"].values():
			despesas += d["valor"] if isinstance(d, dict) else d

		dividas = dados["dividas"]
		total_divida = sum(d["total"] for d in dividas.values())
		prestacoes = sum(d["prestacao"] for d in dividas.values())

		sobra = salarios - despesas - prestacoes

		# sobra
		if sobra > 1000:
			score += 40
		elif sobra > 500:
			score += 30
		elif sobra > 0:
			score += 15

		# despesas
		if salarios > 0:
			ratio = despesas / salarios
			if ratio < 0.5:
				score += 20
			elif ratio < 0.7:
				score += 10

		# dívida
		if salarios > 0:
			ratio_div = total_divida / (salarios * 12)
			if ratio_div < 1:
				score += 20
			elif ratio_div < 2:
				score += 10

		# juros
		if dividas:
			max_taxa = max(d["taxa"] for d in dividas.values())
			if max_taxa < 5:
				score += 20
			elif max_taxa < 10:
				score += 10

		return score

	def criar_dropdown(self, titulo, opcoes, parent=None):
		if parent is None:
			parent = self.sidebar_top

		frame = ctk.CTkFrame(parent, fg_color="transparent")
		frame.pack(fill="x", pady=(4, 0), padx=10)

		estado = {"aberto": False}
		botoes = []

		main_btn = ctk.CTkButton(
			frame,
			text=f"{titulo} ▼",
			width=200,
			anchor="w",
			fg_color="#1f6aa5",
			hover_color="#2a7dc4"
		)
		main_btn.pack(fill="x")

		def toggle():
			estado["aberto"] = not estado["aberto"]

			if estado["aberto"]:
				main_btn.configure(text=f"{titulo} ▲")
				for btn in botoes:
					btn.pack(fill="x", pady=2)
			else:
				main_btn.configure(text=f"{titulo} ▼")
				for btn in botoes:
					btn.pack_forget()

		main_btn.configure(command=toggle)

		for nome, comando in opcoes:
			btn = ctk.CTkButton(
				frame,
				text=f"   {nome}",
				width=200,
				anchor="w",
				fg_color="#163d5c",
				hover_color="#2a7dc4"
			)

			def on_click(c=comando, b=btn):
				self.set_active_button(b)
				c()

			btn.configure(command=on_click)
			botoes.append(btn)
			self.sidebar_buttons.append(btn)

		return frame

	def limpar_main(self):
		for widget in self.main.winfo_children():
			widget.destroy()

	# =====================
	# RESUMO
	# =====================
	def mostrar_resumo(self):
		self.limpar_main()

		mes = self.dados["mes_atual"]

		salarios = self.total_entradas_mensais()
		pendentes = self.total_pendentes()

		self.garantir_saldo_inicial()
		saldo_inicial = float(self.dados["saldo_inicial"])

		despesas = 0
		despesas_pagas = 0
		despesas_por_pagar = 0

		for d in self.dados["meses"][mes]["despesas"].values():
			if isinstance(d, dict):
				valor = d["valor"]
				pago = d.get("pago", False)
			else:
				valor = d
				pago = False

			despesas += valor

			if pago:
				despesas_pagas += valor
			else:
				despesas_por_pagar += valor

		dividas = sum(d["prestacao"] for d in self.dados["dividas"].values())

		sobra = salarios - despesas - dividas
		saldo_real = saldo_inicial + sobra
		disponivel = sobra

		# =====================
		# CARDS (TOPO)
		# =====================
		top = ctk.CTkFrame(self.main)
		top.pack(pady=20, padx=20, fill="x")

		def criar_card(parent, titulo, valor, comando=None, cor=None):
			def on_click(event=None):
				# reset anterior
				def limpar_main(self):
					if self.active_card is not None:
						try:
							if self.active_card.winfo_exists():
								self.active_card.configure(fg_color="transparent")
						except:
							pass
						self.active_card = None

					for widget in self.main.winfo_children():
						widget.destroy()

				comando()

			frame = ctk.CTkFrame(parent, corner_radius=10)
			frame.pack(side="left", expand=True, fill="x", padx=10)

			lbl_titulo = ctk.CTkLabel(frame, text=titulo, font=("Arial", 12))
			lbl_titulo.pack(pady=5)

			lbl_valor = ctk.CTkLabel(
				frame,
				text=f"{valor:.2f} CHF",
				font=("Arial", 16, "bold")
			)

			if cor:
				lbl_valor.configure(text_color=cor)

			lbl_valor.pack(pady=5)

			if comando:
				def on_enter(event=None):
					if frame != self.active_card:
						frame.configure(fg_color="#3a3a3a")

				def on_leave(event=None):
					if frame != self.active_card:
						frame.configure(fg_color="transparent")

				frame.bind("<Button-1>", on_click)
				lbl_titulo.bind("<Button-1>", on_click)
				lbl_valor.bind("<Button-1>", on_click)

				frame.bind("<Enter>", on_enter)
				frame.bind("<Leave>", on_leave)
				lbl_titulo.bind("<Enter>", on_enter)
				lbl_titulo.bind("<Leave>", on_leave)
				lbl_valor.bind("<Enter>", on_enter)
				lbl_valor.bind("<Leave>", on_leave)

		criar_card(top, "💰 Sobra mensal", disponivel, comando=self.analise_financeira)
		criar_card(top, "🏦 Saldo real", saldo_real, comando=self.mostrar_saldo_inicial, cor="green" if saldo_real >= 0 else "red")
		criar_card(top, "💳 Dívidas", dividas, comando=self.mostrar_dividas)
		criar_card(top, "📌 Pendentes", pendentes, comando=self.mostrar_pendentes)

		# =====================
		# SOBRA (DESTAQUE)
		# =====================
		cor = "green" if sobra >= 0 else "red"

		sobra_label = ctk.CTkLabel(
			self.main,
			text=f"Sobra: {sobra:.2f} CHF",
			font=("Arial", 24, "bold"),
			text_color=cor
		)
		sobra_label.pack(pady=15)

		# =====================
		# PAGAS vs POR PAGAR (lado a lado)
		# =====================
		frame_estado = ctk.CTkFrame(self.main)
		frame_estado.pack(pady=10, padx=20, fill="x")

		# PAGAS
		frame_pagas = ctk.CTkFrame(frame_estado)
		frame_pagas.pack(side="left", expand=True, fill="x", padx=10)

		lbl_pagas_t = ctk.CTkLabel(frame_pagas, text="✅ Pagas", font=("Arial", 14, "bold"), text_color="#3CB371")
		lbl_pagas_t.pack(pady=(10, 5))

		lbl_pagas_v = ctk.CTkLabel(
			frame_pagas,
			text=f"{despesas_pagas:.2f} CHF",
			font=("Arial", 16)
		)
		lbl_pagas_v.pack(pady=(0, 10))

		def abrir_pagas(event=None):
			self.mostrar_despesas("Pagas")

		def hover_pagas_on(event=None):
			frame_pagas.configure(fg_color="#3a3a3a")

		def hover_pagas_off(event=None):
			frame_pagas.configure(fg_color="transparent")

		frame_pagas.bind("<Button-1>", abrir_pagas)
		lbl_pagas_t.bind("<Button-1>", abrir_pagas)
		lbl_pagas_v.bind("<Button-1>", abrir_pagas)

		frame_pagas.bind("<Enter>", hover_pagas_on)
		frame_pagas.bind("<Leave>", hover_pagas_off)
		lbl_pagas_t.bind("<Enter>", hover_pagas_on)
		lbl_pagas_t.bind("<Leave>", hover_pagas_off)
		lbl_pagas_v.bind("<Enter>", hover_pagas_on)
		lbl_pagas_v.bind("<Leave>", hover_pagas_off)

		# POR PAGAR
		frame_por_pagar = ctk.CTkFrame(frame_estado)
		frame_por_pagar.pack(side="left", expand=True, fill="x", padx=10)

		lbl_pp_t = ctk.CTkLabel(frame_por_pagar, text="⏳ Por pagar", font=("Arial", 14, "bold"), text_color="#FFA500")
		lbl_pp_t.pack(pady=(10, 5))

		lbl_pp_v = ctk.CTkLabel(
			frame_por_pagar,
			text=f"{despesas_por_pagar:.2f} CHF",
			font=("Arial", 16)
		)
		lbl_pp_v.pack(pady=(0, 10))

		def abrir_por_pagar(event=None):
			self.mostrar_despesas("Por pagar")

		def hover_pp_on(event=None):
			frame_por_pagar.configure(fg_color="#3a3a3a")

		def hover_pp_off(event=None):
			frame_por_pagar.configure(fg_color="transparent")

		frame_por_pagar.bind("<Button-1>", abrir_por_pagar)
		lbl_pp_t.bind("<Button-1>", abrir_por_pagar)
		lbl_pp_v.bind("<Button-1>", abrir_por_pagar)

		frame_por_pagar.bind("<Enter>", hover_pp_on)
		frame_por_pagar.bind("<Leave>", hover_pp_off)
		lbl_pp_t.bind("<Enter>", hover_pp_on)
		lbl_pp_t.bind("<Leave>", hover_pp_off)
		lbl_pp_v.bind("<Enter>", hover_pp_on)
		lbl_pp_v.bind("<Leave>", hover_pp_off)

		# =====================
		# SCORE + ALERTAS LADO A LADO
		# =====================
		container = ctk.CTkFrame(self.main)
		container.pack(pady=15, padx=20, fill="x")

		# LEFT = SCORE
		frame_score = ctk.CTkFrame(container)
		frame_score.pack(side="left", expand=True, fill="both", padx=10)

		score, detalhes = self.calcular_score()

		lbl_score = ctk.CTkLabel(
			frame_score,
			text=f"Score Financeiro: {score}/100",
			font=("Arial", 18, "bold")
		)
		lbl_score.pack(anchor="w", padx=10, pady=(10, 5))

		score_widgets = [lbl_score]

		for d in detalhes:
			lbl = ctk.CTkLabel(frame_score, text=d)
			lbl.pack(anchor="w", padx=15)
			score_widgets.append(lbl)

		self.bind_clickable_frame(frame_score, score_widgets, self.analise_financeira)

		# RIGHT = ALERTAS
		frame_alertas = ctk.CTkFrame(container)
		frame_alertas.pack(side="left", expand=True, fill="both", padx=10)

		alertas = self.gerar_alertas()
	
		if pendentes > 0:
			alertas.append((f"⚠️ Tens {pendentes:.0f} CHF em pendentes", "orange"))

		lbl_alertas = ctk.CTkLabel(
			frame_alertas,
			text="Alertas",
			font=("Arial", 16, "bold")
		)
		lbl_alertas.pack(anchor="w", padx=10, pady=(10, 5))

		alerta_widgets = [lbl_alertas]

		if alertas:
			for texto, cor in alertas:
				lbl = ctk.CTkLabel(frame_alertas, text=texto, text_color=cor)
				lbl.pack(anchor="w", padx=15)
				alerta_widgets.append(lbl)
		else:
			lbl = ctk.CTkLabel(frame_alertas, text="Sem alertas 👍")
			lbl.pack(anchor="w", padx=15)
			alerta_widgets.append(lbl)

		self.bind_clickable_frame(frame_alertas, alerta_widgets, self.analise_financeira)

		# =====================
		# METAS PRINCIPAIS
		# =====================
		metas = self.dados.get("metas", [])

		if metas:
			frame_metas = ctk.CTkFrame(self.main)
			frame_metas.pack(pady=15, padx=20, fill="x")

			ctk.CTkLabel(
				frame_metas,
				text="🎯 Metas principais",
				font=("Arial", 18, "bold")
			).pack(anchor="w", padx=10, pady=(10, 5))

			for meta in metas[:3]:
				nome = meta["nome"]
				tipo = meta["tipo"]
				alvo = float(meta["alvo"])

				atual = self.calcular_valor_meta(tipo)

				if tipo == "poupanca":
					progresso = 0 if alvo <= 0 else max(0, min(1, atual / alvo))
					estado = "✅" if atual >= alvo else "⏳"
				elif tipo == "despesas":
					progresso = 1 if atual <= alvo else max(0, min(1, alvo / atual))
					estado = "✅" if atual <= alvo else "⏳"
				elif tipo == "divida":
					progresso = 1 if atual <= alvo else max(0, min(1, alvo / atual))
					estado = "✅" if atual <= alvo else "⏳"
				else:
					progresso = 0
					estado = "⏳"

				row = ctk.CTkFrame(frame_metas, fg_color="transparent")
				row.pack(fill="x", padx=10, pady=5)

				lbl_meta = ctk.CTkLabel(
					row,
					text=f"{estado} {nome} ({atual:.2f} / {alvo:.2f} CHF)"
				)
				lbl_meta.pack(anchor="w")

				bar = ctk.CTkProgressBar(row)
				bar.pack(fill="x", pady=2)
				bar.set(progresso)

				self.bind_clickable_frame(row, [lbl_meta, bar], self.mostrar_metas)

	# =====================
	# DESPESAS
	# =====================
	def mostrar_despesas(self, filtro_estado_inicial="Todas"):
		self.limpar_main()

		mes = self.dados["mes_atual"]

		selecionado = {"nome": None}
		self.despesa_linhas = {}

		# =====================
		# PESQUISA + FILTRO
		# =====================
		top = ctk.CTkFrame(self.main)
		top.pack(fill="x", padx=10, pady=5)

		pesquisa = ctk.CTkEntry(top, placeholder_text="Pesquisar...")
		pesquisa.pack(side="left", padx=5)

		categorias = ["Todas"] + self.dados["categorias"]
		filtro = ctk.CTkOptionMenu(top, values=categorias)
		filtro.set("Todas")
		filtro.pack(side="left", padx=5)

		estado_filtro = ctk.CTkOptionMenu(top, values=["Todas", "Pagas", "Por pagar"])
		estado_filtro.set(filtro_estado_inicial)
		estado_filtro.pack(side="left", padx=5)

		# =====================
		# LISTA VISUAL
		# =====================
		# LISTA (scrollável)
		lista_container = ctk.CTkFrame(self.main)
		lista_container.pack(fill="both", expand=True, padx=10, pady=5)

		lista_frame = ctk.CTkScrollableFrame(lista_container)
		lista_frame.pack(fill="both", expand=True)

		def limpar_selecao_visual():
			for _, row in self.despesa_linhas.items():
				row.configure(fg_color="transparent")

		def preencher_campos(nome_sel):
			info = self.dados["meses"][mes]["despesas"][nome_sel]

			if isinstance(info, dict):
				valor_sel = info["valor"]
				cat_sel = info["categoria"]
			else:
				valor_sel = info
				cat_sel = "Sem categoria"

			nome.delete(0, "end")
			nome.insert(0, nome_sel)

			valor.delete(0, "end")
			valor.insert(0, str(valor_sel))

			categoria.set(cat_sel)

			selecionado["nome"] = nome_sel

		def selecionar_despesa(nome_sel):
			limpar_selecao_visual()

			if nome_sel in self.despesa_linhas:
				self.despesa_linhas[nome_sel].configure(fg_color="#144870")

			preencher_campos(nome_sel)

		def bind_hover(frame, normal_color="transparent", hover_color="#1c4f7a"):
			def on_enter(event):
				if selecionado["nome"] != frame.nome_despesa:
					frame.configure(fg_color=hover_color)

			def on_leave(event):
				if selecionado["nome"] != frame.nome_despesa:
					frame.configure(fg_color=normal_color)

			frame.bind("<Enter>", on_enter)
			frame.bind("<Leave>", on_leave)

		def atualizar_lista():
			for widget in lista_frame.winfo_children():
				widget.destroy()

			header = ctk.CTkFrame(lista_frame, fg_color="#2a2a2a", corner_radius=6)
			header.pack(fill="x", pady=(0, 5), padx=3)

			ctk.CTkLabel(header, text="Nome", width=200, anchor="w").pack(side="left", padx=(10,5), pady=6)
			ctk.CTkLabel(header, text="Valor", width=120, anchor="e").pack(side="left", padx=5)
			ctk.CTkLabel(header, text="Categoria", width=140, anchor="w").pack(side="left", padx=5)
			ctk.CTkLabel(header, text="Estado", width=120, anchor="center").pack(side="left", padx=5)

			linha = ctk.CTkFrame(lista_frame, height=2, fg_color="#444")
			linha.pack(fill="x", padx=5, pady=(0,5))

			self.despesa_linhas = {}

			termo = pesquisa.get().lower().strip()
			cat_sel = filtro.get()
			estado_sel = estado_filtro.get()

			for nome_despesa, info in self.dados["meses"][mes]["despesas"].items():
				if isinstance(info, dict):
					valor_despesa = info["valor"]
					categoria_despesa = info["categoria"]
					pago = info.get("pago", False)
				else:
					valor_despesa = info
					categoria_despesa = "Sem categoria"
					pago = False

				if termo and termo not in nome_despesa.lower():
					continue

				if cat_sel != "Todas" and categoria_despesa != cat_sel:
					continue

				if estado_sel == "Pagas" and not pago:
					continue

				if estado_sel == "Por pagar" and pago:
					continue

				row = ctk.CTkFrame(lista_frame, fg_color="transparent", corner_radius=8)
				row.pack(fill="x", pady=3, padx=3)
				row.nome_despesa = nome_despesa

				estado_txt = "✅ Pago" if pago else "⏳ Por pagar"

				lbl_nome = ctk.CTkLabel(row, text=nome_despesa, width=200, anchor="w")
				lbl_nome.pack(side="left", padx=(10, 5), pady=6)

				lbl_valor = ctk.CTkLabel(row, text=f"{valor_despesa:.2f} CHF", width=120, anchor="e")
				lbl_valor.pack(side="left", padx=5)

				lbl_cat = ctk.CTkLabel(row, text=categoria_despesa, width=140, anchor="w")
				lbl_cat.pack(side="left", padx=5)

				lbl_estado = ctk.CTkLabel(row, text=estado_txt, width=120, anchor="center")
				lbl_estado.pack(side="left", padx=5)

				def click_handler(event=None, n=nome_despesa):
					selecionar_despesa(n)

				row.bind("<Button-1>", click_handler)
				lbl_nome.bind("<Button-1>", click_handler)
				lbl_valor.bind("<Button-1>", click_handler)
				lbl_cat.bind("<Button-1>", click_handler)
				lbl_estado.bind("<Button-1>", click_handler)

				bind_hover(row)
				self.despesa_linhas[nome_despesa] = row

		# primeira carga
		atualizar_lista()

		pesquisa.bind("<KeyRelease>", lambda e: atualizar_lista())
		filtro.configure(command=lambda _: atualizar_lista())
		estado_filtro.configure(command=lambda _: atualizar_lista())

		# =====================
		# INPUTS
		# =====================
		# EDITOR FIXO EM BAIXO
		editor = ctk.CTkFrame(self.main)
		editor.pack(side="bottom", fill="x", padx=20, pady=10)

		linha_campos = ctk.CTkFrame(editor, fg_color="transparent")
		linha_campos.pack(pady=(10, 6))

		nome = ctk.CTkEntry(linha_campos, placeholder_text="Nome", width=260)
		nome.pack(side="left", padx=6)

		valor = ctk.CTkEntry(linha_campos, placeholder_text="Valor", width=140)
		valor.pack(side="left", padx=6)

		categoria = ctk.CTkOptionMenu(linha_campos, values=self.dados["categorias"], width=200)
		categoria.pack(side="left", padx=6)

		botoes = ctk.CTkFrame(editor, fg_color="transparent")
		botoes.pack(pady=(0, 10))
		
		# =====================
		# GUARDAR
		# =====================
		def guardar_despesa():
			n = nome.get()
			v = float(valor.get())
			c = categoria.get()

			pago_atual = False
			if selecionado["nome"] and selecionado["nome"] in self.dados["meses"][mes]["despesas"]:
				info_antiga = self.dados["meses"][mes]["despesas"][selecionado["nome"]]
				if isinstance(info_antiga, dict):
					pago_atual = info_antiga.get("pago", False)

			if selecionado["nome"]:
				del self.dados["meses"][mes]["despesas"][selecionado["nome"]]

			self.dados["meses"][mes]["despesas"][n] = {
				"valor": v,
				"categoria": c,
				"pago": pago_atual
			}

			guardar(self.dados)

			selecionado["nome"] = None
			nome.delete(0, "end")
			valor.delete(0, "end")
			limpar_selecao_visual()
			atualizar_lista()
		
		btn_add = ctk.CTkButton(botoes, text="💾 Guardar", width=120, command=guardar_despesa)
		btn_add.pack(side="left", padx=5)

		# =====================
		# REMOVER
		# =====================
		def remover():
			if not selecionado["nome"]:
				return

			del self.dados["meses"][mes]["despesas"][selecionado["nome"]]
			guardar(self.dados)

			selecionado["nome"] = None
			nome.delete(0, "end")
			valor.delete(0, "end")
			limpar_selecao_visual()
			atualizar_lista()

		btn_rem = ctk.CTkButton(
			botoes,
			text="❌ Remover",
			width=120,
			fg_color="#8B0000",
			hover_color="#A00000",
			command=remover
		)
		btn_rem.pack(side="left", padx=5)

		# =====================
		# ALTERNAR PAGO
		# =====================
		def alternar_pago():
			if not selecionado["nome"]:
				return

			info = self.dados["meses"][mes]["despesas"][selecionado["nome"]]

			if isinstance(info, dict):
				info["pago"] = not info.get("pago", False)
			else:
				self.dados["meses"][mes]["despesas"][selecionado["nome"]] = {
					"valor": info,
					"categoria": "Sem categoria",
					"pago": True
				}

			guardar(self.dados)
			atualizar_lista()

		btn_pago = ctk.CTkButton(
			botoes,
			text="✓ Pago",
			width=120,
			fg_color="#2E8B57",
			hover_color="#3CB371",
			command=alternar_pago
		)
		btn_pago.pack(side="left", padx=5)

	# =====================
	# CATEGORIAS
	# =====================
	def mostrar_categorias(self):
		self.limpar_main()

		lista = ctk.CTkTextbox(self.main, height=200)
		lista.pack(pady=10)

		for c in self.dados["categorias"]:
			lista.insert("end", c + "\n")

		entry = ctk.CTkEntry(self.main, placeholder_text="Nova categoria")
		entry.pack()

		def adicionar():
			self.dados["categorias"].append(entry.get())
			guardar(self.dados)
			self.mostrar_categorias()

		btn = ctk.CTkButton(self.main, text="Adicionar", command=adicionar)
		btn.pack(pady=5)

	def mostrar_grafico(self):
		self.limpar_main()

		mes = self.dados["mes_atual"]

		categorias = {}

		for d in self.dados["meses"][mes]["despesas"].values():
			if isinstance(d, dict):
				categorias[d["categoria"]] = categorias.get(d["categoria"], 0) + d["valor"]
			else:
				categorias["Sem categoria"] = categorias.get("Sem categoria", 0) + d

		fig, ax = plt.subplots()
		ax.pie(categorias.values(), labels=categorias.keys(), autopct="%1.1f%%")
		ax.set_title("Gastos por categoria")

		canvas = FigureCanvasTkAgg(fig, master=self.main)
		canvas.draw()
		canvas.get_tk_widget().pack(pady=20)

	# =====================
	# MESES
	# =====================
	def mostrar_meses(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="📅 Meses", font=("Arial", 20, "bold"))
		titulo.pack(pady=5)

		info = ctk.CTkLabel(self.main, text=f"Mês atual: {self.dados['mes_atual']}")
		info.pack(pady=5)

		entry = ctk.CTkEntry(self.main, placeholder_text="YYYY-MM")
		entry.pack(pady=10)

		def mudar():
			novo = entry.get().strip()

			if not novo:
				return

			mes_novo = novo not in self.dados["meses"]

			if mes_novo:
				self.dados["meses"][novo] = {"despesas": {}}
				self.aplicar_despesas_fixas_ao_mes(novo)

			self.dados["mes_atual"] = novo
			guardar(self.dados)

			self.mostrar_meses()

		btn = ctk.CTkButton(self.main, text="Mudar mês", command=mudar)
		btn.pack(pady=5)

		# lista de meses existentes
		lista = ctk.CTkScrollableFrame(self.main)
		lista.pack(fill="both", expand=True, padx=20, pady=15)

		for mes in sorted(self.dados["meses"].keys(), reverse=True):
			frame = ctk.CTkFrame(lista)
			frame.pack(fill="x", pady=4)

			ctk.CTkLabel(frame, text=mes).pack(side="left", padx=10, pady=8)

			def selecionar(m=mes):
				self.dados["mes_atual"] = m
				guardar(self.dados)
				self.mostrar_meses()

			ctk.CTkButton(frame, text="Usar", width=80, command=selecionar).pack(side="right", padx=10)

	def timeline_divida(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="📅 Timeline Financeira", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		mes_atual = self.dados["mes_atual"]
		entradas = self.total_entradas_mensais()

		self.garantir_saldo_inicial()
		saldo_inicial = float(self.dados["saldo_inicial"])

		despesas = 0
		for d in self.dados["meses"][mes_atual]["despesas"].values():
			despesas += d["valor"] if isinstance(d, dict) else d

		total_prestacoes = sum(d["prestacao"] for d in self.dados["dividas"].values())
		total_divida = sum(d["total"] for d in self.dados["dividas"].values())
		sobra = entradas - despesas - total_prestacoes

		saldo_real = saldo_inicial + sobra

		top = ctk.CTkFrame(self.main)
		top.pack(fill="x", padx=20, pady=10)

		def card(parent, titulo, valor, cor=None):
			frame = ctk.CTkFrame(parent, corner_radius=10)
			frame.pack(side="left", expand=True, fill="x", padx=8)

			ctk.CTkLabel(frame, text=titulo, font=("Arial", 12)).pack(pady=(10, 4))

			lbl = ctk.CTkLabel(frame, text=str(valor), font=("Arial", 16, "bold"))
			if cor:
				lbl.configure(text_color=cor)
			lbl.pack(pady=(0, 10))

		card(top, "💳 Dívida total", f"{total_divida:.2f} CHF")
		card(top, "💸 Prestações", f"{total_prestacoes:.2f} CHF")
		card(top, "💰 Sobra", f"{sobra:.2f} CHF", "green" if sobra >= 0 else "red")

		config = ctk.CTkFrame(self.main)
		config.pack(fill="x", padx=20, pady=10)

		ctk.CTkLabel(config, text="Extra mensal", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(10, 3))
		extra_entry = ctk.CTkEntry(config, placeholder_text="Ex: 100")
		extra_entry.pack(anchor="w", padx=10, pady=(0, 8))

		ctk.CTkLabel(config, text="Modo de visualização", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(5, 3))
		modo = ctk.CTkOptionMenu(config, values=["Resumo", "Detalhado"])
		modo.set("Resumo")
		modo.pack(anchor="w", padx=10, pady=(0, 10))

		resultado = ctk.CTkTextbox(self.main, height=380)
		resultado.pack(fill="both", expand=True, padx=20, pady=10)

		def somar_meses(ym, delta):
			ano, mes = map(int, ym.split("-"))
			total = ano * 12 + (mes - 1) + delta
			novo_ano = total // 12
			novo_mes = (total % 12) + 1
			return f"{novo_ano:04d}-{novo_mes:02d}"

		def calcular():
			resultado.delete("1.0", "end")

			try:
				extra = float(extra_entry.get() or 0)
			except:
				extra = 0.0

			dividas = {
				nome: {
					"total": float(info["total"]),
					"taxa": float(info["taxa"]),
					"prestacao": float(info["prestacao"])
				}
				for nome, info in self.dados["dividas"].items()
			}

			if not dividas:
				resultado.insert("end", "Sem dívidas registadas.\n")
				return

			resultado.insert("end", "📌 Estratégia: Avalanche (dívida com juros mais altos recebe o extra)\n")
			resultado.insert("end", f"📅 Início: {mes_atual}\n")
			resultado.insert("end", f"💰 Extra mensal: {extra:.2f} CHF\n\n")

			meses = 0
			juros_totais = 0.0
			problema = False
			historico = []

			while True:
				ativas = {n: d for n, d in dividas.items() if d["total"] > 0}
				if not ativas:
					break

				meses += 1
				if meses > 600:
					problema = True
					break

				mes_label = somar_meses(mes_atual, meses - 1)
				prioritaria = max(ativas.items(), key=lambda x: x[1]["taxa"])[0]

				linha_mes = {
					"mes": mes_label,
					"itens": [],
					"total_restante": 0.0
				}

				for nome, d in ativas.items():
					taxa_mensal = d["taxa"] / 100 / 12
					juros = d["total"] * taxa_mensal
					juros_totais += juros
					d["total"] += juros

					pagamento = d["prestacao"]
					if nome == prioritaria:
						pagamento += extra

					if pagamento <= juros and d["total"] > 0:
						problema = True

					d["total"] -= pagamento
					if d["total"] < 0:
						d["total"] = 0

					linha_mes["itens"].append({
						"nome": nome,
						"restante": d["total"]
					})

					linha_mes["total_restante"] += d["total"]

				historico.append(linha_mes)

			if historico:
				data_final = historico[-1]["mes"] if not problema else "indefinida"
			else:
				data_final = mes_atual

			resultado.insert("end", "=== RESUMO ===\n")
			resultado.insert("end", f"⏳ Meses estimados: {meses}\n")
			resultado.insert("end", f"📅 Fim previsto: {data_final}\n")
			resultado.insert("end", f"💸 Juros totais estimados: {juros_totais:.2f} CHF\n")
			resultado.insert("end", f"💳 Dívida inicial: {total_divida:.2f} CHF\n")

			if meses > 0 and not problema:
				anos = meses / 12
				resultado.insert("end", f"🗓️ Aproximadamente: {anos:.1f} anos\n")

			if problema:
				resultado.insert("end", "⚠️ A simulação ficou instável ou acima de 600 meses.\n")
				resultado.insert("end", "Convém rever prestações, juros ou valor extra.\n")

			resultado.insert("end", "\n")

			if modo.get() == "Detalhado":
				resultado.insert("end", "=== DETALHE MENSAL ===\n")
				for reg in historico:
					resultado.insert("end", f"{reg['mes']} — total restante: {reg['total_restante']:.2f} CHF\n")
					for item in reg["itens"]:
						resultado.insert("end", f"   {item['nome']}: {item['restante']:.2f} CHF\n")
					resultado.insert("end", "\n")
			else:
				resultado.insert("end", "=== MARCOS ===\n")

				if historico:
					indices = [0, len(historico)//4, len(historico)//2, (3*len(historico))//4, len(historico)-1]
					vistos = set()

					for i in indices:
						if i in vistos or i < 0 or i >= len(historico):
							continue
						vistos.add(i)

						reg = historico[i]
						resultado.insert("end", f"{reg['mes']} — total restante: {reg['total_restante']:.2f} CHF\n")

				resultado.insert("end", "\n")
				resultado.insert("end", "💡 Muda para 'Detalhado' para ver mês a mês.\n")

		btn = ctk.CTkButton(config, text="Calcular timeline", command=calcular)
		btn.pack(anchor="w", padx=10, pady=(0, 10))

		calcular()

	def mostrar_valores(self):
		self.limpar_main()

		# =====================
		# SALÁRIOS
		# =====================
		titulo = ctk.CTkLabel(self.main, text="💰 Rendimentos", font=("Arial", 18))
		titulo.pack(pady=10)

		for nome, valor in self.dados["salarios"].items():
			frame = ctk.CTkFrame(self.main)
			frame.pack(pady=5, padx=10, fill="x")

			label = ctk.CTkLabel(frame, text=nome, width=100)
			label.pack(side="left", padx=10)

			entry = ctk.CTkEntry(frame)
			entry.insert(0, str(valor))
			entry.pack(side="left", padx=10)

			def guardar_salario(n=nome, e=entry):
				self.dados["salarios"][n] = float(e.get())
				guardar(self.dados)

			btn = ctk.CTkButton(frame, text="Guardar", command=guardar_salario)
			btn.pack(side="right", padx=10)

		# =====================
		# DIVISOR
		# =====================
		sep = ctk.CTkLabel(self.main, text="----------------------------")
		sep.pack(pady=10)

		# =====================
		# DÍVIDAS
		# =====================
		titulo2 = ctk.CTkLabel(self.main, text="💳 Dívidas", font=("Arial", 18))
		titulo2.pack(pady=10)

		# LISTA
		for nome, d in self.dados["dividas"].items():
			frame = ctk.CTkFrame(self.main)
			frame.pack(pady=5, padx=10, fill="x")

			nome_lbl = ctk.CTkLabel(frame, text=nome, width=100)
			nome_lbl.pack(side="left", padx=4)

			total = ctk.CTkEntry(frame, width=80)
			total.insert(0, str(d["total"]))
			total.pack(side="left", padx=5)

			taxa = ctk.CTkEntry(frame, width=60)
			taxa.insert(0, str(d["taxa"]))
			taxa.pack(side="left", padx=5)

			prest = ctk.CTkEntry(frame, width=80)
			prest.insert(0, str(d["prestacao"]))
			prest.pack(side="left", padx=5)

			def guardar_divida(n=nome, t=total, tx=taxa, p=prest):
				self.dados["dividas"][n] = {
					"inicial": self.dados["dividas"][n].get("inicial", float(t.get())),
					"total": float(t.get()),
					"taxa": float(tx.get()),
					"prestacao": float(p.get())
				}
				guardar(self.dados)

			btn_save = ctk.CTkButton(frame, text="Guardar", command=guardar_divida)
			btn_save.pack(side="left", padx=5)

			def remover_divida(n=nome):
				del self.dados["dividas"][n]
				guardar(self.dados)
				self.mostrar_valores()

			btn_del = ctk.CTkButton(frame, text="❌", width=32, command=remover_divida)
			btn_del.pack(side="right", padx=5)

		# =====================
		# ADICIONAR NOVA DÍVIDA
		# =====================
		novo_frame = ctk.CTkFrame(self.main)
		novo_frame.pack(pady=15, padx=10, fill="x")

		nome = ctk.CTkEntry(novo_frame, placeholder_text="Nome")
		nome.pack(side="left", padx=5)

		total = ctk.CTkEntry(novo_frame, placeholder_text="Total")
		total.pack(side="left", padx=5)

		taxa = ctk.CTkEntry(novo_frame, placeholder_text="Taxa %")
		taxa.pack(side="left", padx=5)

		prest = ctk.CTkEntry(novo_frame, placeholder_text="Prestação")
		prest.pack(side="left", padx=5)

		def adicionar():
			self.dados["dividas"][nome.get()] = {
				"total": float(total.get()),
				"taxa": float(taxa.get()),
				"prestacao": float(prest.get())
			}
			guardar(self.dados)
			self.mostrar_valores()

		btn_add = ctk.CTkButton(novo_frame, text="Adicionar", command=adicionar)
		btn_add.pack(side="left", padx=5)

	# =====================
	# DÍVIDAS
	# =====================
	def modo_dividas(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="📊 Simulação de Dívidas", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		mes = self.dados["mes_atual"]
		entradas = self.total_entradas_mensais()
		pendentes = self.total_pendentes()

		self.garantir_saldo_inicial()
		saldo_inicial = float(self.dados["saldo_inicial"])

		despesas = 0
		for d in self.dados["meses"][mes]["despesas"].values():
			despesas += d["valor"] if isinstance(d, dict) else d

		total_divida_atual = sum(d["total"] for d in self.dados["dividas"].values())
		total_prestacoes = sum(d["prestacao"] for d in self.dados["dividas"].values())
		sobra = entradas - despesas - total_prestacoes
		saldo_real = saldo_inicial + sobra

		top = ctk.CTkFrame(self.main)
		top.pack(fill="x", padx=20, pady=10)

		def card(parent, titulo, valor, cor=None):
			frame = ctk.CTkFrame(parent, corner_radius=10)
			frame.pack(side="left", expand=True, fill="x", padx=8)

			ctk.CTkLabel(frame, text=titulo, font=("Arial", 12)).pack(pady=(10, 4))

			lbl = ctk.CTkLabel(frame, text=str(valor), font=("Arial", 16, "bold"))
			if cor:
				lbl.configure(text_color=cor)
			lbl.pack(pady=(0, 10))

		card(top, "💰 Entradas", f"{entradas:.2f} CHF")
		card(top, "💸 Despesas", f"{despesas:.2f} CHF")
		card(top, "🏦 Saldo real", f"{saldo_real:.2f} CHF", "green" if saldo_real >= 0 else "red")
		card(top, "📌 Pendentes", f"{pendentes:.2f} CHF", "#FFA500" if pendentes > 0 else None)

		config = ctk.CTkFrame(self.main)
		config.pack(fill="x", padx=20, pady=10)

		ctk.CTkLabel(config, text="Extra mensal para dívida", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(10, 5))

		extra_entry = ctk.CTkEntry(config, placeholder_text="Ex: 100")
		extra_entry.pack(anchor="w", padx=10, pady=(0, 10))

		resultado = ctk.CTkTextbox(self.main, height=360)
		resultado.pack(fill="both", expand=True, padx=20, pady=10)

		def simular_total(extra):
			dividas = {
				nome: {
					"total": float(info["total"]),
					"taxa": float(info["taxa"]),
					"prestacao": float(info["prestacao"])
				}
				for nome, info in self.dados["dividas"].items()
			}

			if not dividas:
				return {
					"meses": 0,
					"juros": 0,
					"problema": False,
					"prioridade": "Sem dívidas"
				}

			juros_totais = 0.0
			meses = 0
			problema = False

			while True:
				ativas = {n: d for n, d in dividas.items() if d["total"] > 0}
				if not ativas:
					break

				meses += 1
				if meses > 600:
					problema = True
					break

				# avalanche: dívida com taxa mais alta recebe o extra
				prioritaria = max(ativas.items(), key=lambda x: x[1]["taxa"])[0]

				for nome, d in ativas.items():
					taxa_mensal = d["taxa"] / 100 / 12
					juros = d["total"] * taxa_mensal
					juros_totais += juros
					d["total"] += juros

					pagamento = d["prestacao"]
					if nome == prioritaria:
						pagamento += extra

					# não deixa pagar abaixo de zero no acumulado final
					d["total"] -= pagamento
					if d["total"] < 0:
						d["total"] = 0

					# se não amortiza e não houver extra suficiente, marca problema
					if pagamento <= juros and d["total"] > 0:
						problema = True

			prioridade = max(self.dados["dividas"].items(), key=lambda x: x[1]["taxa"])[0] if self.dados["dividas"] else "Sem dívidas"

			return {
				"meses": meses,
				"juros": juros_totais,
				"problema": problema,
				"prioridade": prioridade
			}

		def mostrar_cenarios():
			resultado.delete("1.0", "end")

			try:
				extra_manual = float(extra_entry.get() or 0)
			except:
				extra_manual = 0

			cenarios = [0, 100, 250, 500]
			if extra_manual not in cenarios:
				cenarios.insert(0, extra_manual)

			cenarios = sorted(set(cenarios))

			resultado.insert("end", "📌 Estratégia usada: Avalanche (prioridade aos juros mais altos)\n\n")

			if self.dados["dividas"]:
				pior = max(self.dados["dividas"].items(), key=lambda x: x[1]["taxa"])
				resultado.insert("end", f"🔥 Dívida prioritária: {pior[0]} ({pior[1]['taxa']:.2f}%)\n\n")
			else:
				resultado.insert("end", "Sem dívidas registadas.\n")
				return

			for extra in cenarios:
				r = simular_total(extra)

				resultado.insert("end", f"=== Extra mensal: {extra:.2f} CHF ===\n")

				if r["problema"] and r["meses"] >= 600:
					resultado.insert("end", "⚠️ Simulação instável ou acima de 600 meses\n")
				elif r["problema"]:
					resultado.insert("end", "⚠️ Há dívidas que quase não amortizam\n")

				resultado.insert("end", f"⏳ Meses estimados: {r['meses']}\n")
				resultado.insert("end", f"💸 Juros estimados: {r['juros']:.2f} CHF\n")

				if r["meses"] > 0:
					anos = r["meses"] / 12
					resultado.insert("end", f"📅 Aproximadamente: {anos:.1f} anos\n")

				resultado.insert("end", "\n")

			if sobra > 0:
				resultado.insert("end", f"💡 Tens atualmente uma sobra mensal de {sobra:.2f} CHF.\n")
				resultado.insert("end", "Podes usar parte dessa sobra como extra para reduzir tempo e juros.\n")
			else:
				resultado.insert("end", "⚠️ Neste momento não tens sobra mensal positiva.\n")
				resultado.insert("end", "Antes de acelerar dívida, convém reduzir despesas ou aumentar entradas.\n")

		btn = ctk.CTkButton(config, text="Calcular cenários", command=mostrar_cenarios)
		btn.pack(anchor="w", padx=10, pady=(0, 10))

		mostrar_cenarios()

	# =====================
	# ANÁLISE
	# =====================	
	def analise_financeira(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="🧠 Análise Financeira", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		mes = self.dados["mes_atual"]
		entradas = self.total_entradas_mensais()
		pendentes = self.total_pendentes()

		despesas = 0
		categorias = {}
		for d in self.dados["meses"][mes]["despesas"].values():
			if isinstance(d, dict):
				valor = d["valor"]
				cat = d["categoria"]
			else:
				valor = d
				cat = "Sem categoria"

			despesas += valor
			categorias[cat] = categorias.get(cat, 0) + valor

		dividas = self.dados["dividas"]
		total_divida = sum(d["total"] for d in dividas.values())
		total_prestacoes = sum(d["prestacao"] for d in dividas.values())
		sobra = entradas - despesas - total_prestacoes

		score, detalhes = self.calcular_score()

		# topo
		top = ctk.CTkFrame(self.main)
		top.pack(fill="x", padx=20, pady=10)

		def card(parent, titulo, valor, cor=None):
			frame = ctk.CTkFrame(parent, corner_radius=10)
			frame.pack(side="left", expand=True, fill="x", padx=8)

			ctk.CTkLabel(frame, text=titulo, font=("Arial", 12)).pack(pady=(10, 4))

			lbl = ctk.CTkLabel(frame, text=str(valor), font=("Arial", 16, "bold"))
			if cor:
				lbl.configure(text_color=cor)
			lbl.pack(pady=(0, 10))

		card(top, "💰 Entradas", f"{entradas:.2f} CHF")
		card(top, "💸 Despesas", f"{despesas:.2f} CHF")
		card(top, "💳 Dívida total", f"{total_divida:.2f} CHF")
		card(top, "📌 Pendentes", f"{pendentes:.2f} CHF", "#FFA500" if pendentes > 0 else None)

		meio = ctk.CTkFrame(self.main)
		meio.pack(fill="x", padx=20, pady=10)

		left = ctk.CTkFrame(meio)
		left.pack(side="left", expand=True, fill="both", padx=8)

		right = ctk.CTkFrame(meio)
		right.pack(side="left", expand=True, fill="both", padx=8)

		# Situação atual
		ctk.CTkLabel(left, text="Situação atual", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))
		ctk.CTkLabel(left, text=f"Mês atual: {mes}").pack(anchor="w", padx=10)
		ctk.CTkLabel(left, text=f"Sobra mensal: {sobra:.2f} CHF", text_color="green" if sobra >= 0 else "red").pack(anchor="w", padx=10)
		ctk.CTkLabel(left, text=f"Prestações mensais: {total_prestacoes:.2f} CHF").pack(anchor="w", padx=10)
		ctk.CTkLabel(left, text=f"Score financeiro: {score}/100").pack(anchor="w", padx=10, pady=(0, 10))

		# Maior risco
		ctk.CTkLabel(right, text="Maior risco", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))

		risco = "Sem risco crítico identificado."
		if sobra < 0:
			risco = "Estás com sobra negativa. A situação atual não é sustentável."
		elif pendentes > 0:
			risco = f"Tens {pendentes:.2f} CHF em pendentes, o que distorce a tua situação real."
		elif dividas:
			pior = max(dividas.items(), key=lambda x: x[1]["taxa"])
			if pior[1]["taxa"] > 10:
				risco = f"A dívida com mais risco é {pior[0]}, com juros de {pior[1]['taxa']:.2f}%."
			else:
				risco = f"A tua maior pressão está no volume total de dívida: {total_divida:.2f} CHF."

		ctk.CTkLabel(right, text=risco, wraplength=320, justify="left").pack(anchor="w", padx=10, pady=(0, 10))

		# Maior oportunidade
		baixo = ctk.CTkFrame(self.main)
		baixo.pack(fill="x", padx=20, pady=10)

		left2 = ctk.CTkFrame(baixo)
		left2.pack(side="left", expand=True, fill="both", padx=8)

		right2 = ctk.CTkFrame(baixo)
		right2.pack(side="left", expand=True, fill="both", padx=8)

		ctk.CTkLabel(left2, text="Maior oportunidade", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))

		if categorias:
			maior_cat = max(categorias, key=categorias.get)
			gasto_cat = categorias[maior_cat]
			corte_10 = gasto_cat * 0.10
			corte_20 = gasto_cat * 0.20

			oportunidade = (
				f"A categoria com mais peso é {maior_cat} ({gasto_cat:.2f} CHF).\n"
				f"Se cortares 10%, libertas ~{corte_10:.2f} CHF/mês.\n"
				f"Se cortares 20%, libertas ~{corte_20:.2f} CHF/mês."
			)
		else:
			oportunidade = "Ainda não tens despesas suficientes para identificar uma oportunidade clara."

		ctk.CTkLabel(left2, text=oportunidade, wraplength=320, justify="left").pack(anchor="w", padx=10, pady=(0, 10))

		# Plano recomendado
		ctk.CTkLabel(right2, text="Plano recomendado", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))

		plano = []

		if sobra < 0:
			plano.append("1. Reduzir despesas ou aumentar entradas antes de acelerar dívida.")
		else:
			plano.append("1. Preservar sobra mensal positiva e evitar novas despesas pendentes.")

		if pendentes > 0:
			plano.append("2. Regularizar pendentes ou converter os mais relevantes em dívida para teres visão real.")

		if dividas:
			pior = max(dividas.items(), key=lambda x: x[1]["taxa"])
			plano.append(f"3. Direcionar esforço extra para {pior[0]} (juros mais altos).")

		if categorias:
			maior_cat = max(categorias, key=categorias.get)
			plano.append(f"4. Rever a categoria {maior_cat}, que é a que mais pesa no orçamento.")

		plano_texto = "\n".join(plano) if plano else "Sem ações recomendadas neste momento."
		ctk.CTkLabel(right2, text=plano_texto, wraplength=320, justify="left").pack(anchor="w", padx=10, pady=(0, 10))

		# Rodapé com detalhes do score
		rodape = ctk.CTkFrame(self.main)
		rodape.pack(fill="x", padx=20, pady=10)

		ctk.CTkLabel(rodape, text="Detalhes do score", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))
		for d in detalhes:
			ctk.CTkLabel(rodape, text=d).pack(anchor="w", padx=18)

		# Atalhos
		atalhos = ctk.CTkFrame(self.main)
		atalhos.pack(fill="x", padx=20, pady=10)

		ctk.CTkLabel(atalhos, text="Atalhos", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))

		linha = ctk.CTkFrame(atalhos, fg_color="transparent")
		linha.pack(anchor="w", padx=10, pady=(0, 10))

		ctk.CTkButton(linha, text="Timeline", width=120, command=self.timeline_divida).pack(side="left", padx=5)
		ctk.CTkButton(linha, text="Simulação", width=120, command=self.modo_dividas).pack(side="left", padx=5)
		ctk.CTkButton(linha, text="Metas", width=120, command=self.mostrar_metas).pack(side="left", padx=5)
		ctk.CTkButton(linha, text="Pendentes", width=120, command=self.mostrar_pendentes).pack(side="left", padx=5)

	def sair(self):
		resposta = messagebox.askyesno("Sair", "Tens a certeza que queres sair?")

		if resposta:
			try:
				guardar(self.dados)  # autosave 🔥
			except:
				pass

			self.quit()
			self.destroy()

	def mostrar_rendimentos(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="💰 Rendimentos", font=("Arial", 18))
		titulo.pack(pady=10)

		for nome, valor in self.dados["salarios"].items():
			frame = ctk.CTkFrame(self.main)
			frame.pack(pady=5, padx=10, fill="x")

			label = ctk.CTkLabel(frame, text=nome, width=120)
			label.pack(side="left", padx=5)

			entry = ctk.CTkEntry(frame)
			entry.insert(0, str(valor))
			entry.pack(side="left", padx=5)

			def guardar_salario(n=nome, e=entry):
				self.dados["salarios"][n] = float(e.get())
				guardar(self.dados)

			btn = ctk.CTkButton(frame, text="Guardar", command=guardar_salario)
			btn.pack(side="right", padx=5)

	def mostrar_dividas(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="💳 Dívidas", font=("Arial", 18))
		titulo.pack(pady=10)

		if not self.dados["dividas"]:
			ctk.CTkLabel(self.main, text="Ainda não tens dívidas registadas.").pack(pady=10)

		for nome, d in self.dados["dividas"].items():
			frame = ctk.CTkFrame(self.main)
			frame.pack(pady=5, padx=10, fill="x")

			nome_lbl = ctk.CTkLabel(frame, text=nome, width=120)
			nome_lbl.pack(side="left", padx=5)

			inicial = ctk.CTkEntry(frame, width=70)
			inicial.insert(0, str(d.get("inicial", d["total"])))
			inicial.pack(side="left", padx=4)

			total = ctk.CTkEntry(frame, width=70)
			total.insert(0, str(d["total"]))
			total.pack(side="left", padx=4)

			taxa = ctk.CTkEntry(frame, width=55)
			taxa.insert(0, str(d["taxa"]))
			taxa.pack(side="left", padx=4)

			prest = ctk.CTkEntry(frame, width=70)
			prest.insert(0, str(d["prestacao"]))
			prest.pack(side="left", padx=4)

			info = ctk.CTkLabel(frame, text=self.calcular_info_divida(d), width=130)
			info.pack(side="left", padx=6)

			def guardar_divida(n=nome, i=inicial, t=total, tx=taxa, p=prest):
				self.dados["dividas"][n] = {
					"inicial": float(i.get()),
					"total": float(t.get()),
					"taxa": float(tx.get()),
					"prestacao": float(p.get())
				}
				guardar(self.dados)
				self.mostrar_dividas()

			btn_save = ctk.CTkButton(frame, text="Guardar", command=guardar_divida, width=80)
			btn_save.pack(side="left", padx=5)

			def remover_divida(n=nome):
				del self.dados["dividas"][n]
				guardar(self.dados)
				self.mostrar_dividas()

			btn_del = ctk.CTkButton(frame, text="❌", width=40, command=remover_divida)
			btn_del.pack(side="right", padx=5)

		# =====================
		# ADICIONAR NOVA
		# =====================
		novo = ctk.CTkFrame(self.main)
		novo.pack(pady=15, padx=10, fill="x")

		nome = ctk.CTkEntry(novo, placeholder_text="Nome")
		nome.pack(side="left", padx=5)

		inicial = ctk.CTkEntry(novo, placeholder_text="Valor inicial")
		inicial.pack(side="left", padx=5)

		taxa = ctk.CTkEntry(novo, placeholder_text="Taxa %")
		taxa.pack(side="left", padx=5)

		prest = ctk.CTkEntry(novo, placeholder_text="Prestação")
		prest.pack(side="left", padx=5)

		def adicionar():
			valor_inicial = float(inicial.get())

			self.dados["dividas"][nome.get()] = {
				"inicial": valor_inicial,
				"total": valor_inicial,
				"taxa": float(taxa.get()),
				"prestacao": float(prest.get())
			}
			guardar(self.dados)
			self.mostrar_dividas()

		btn_add = ctk.CTkButton(novo, text="Adicionar", command=adicionar)
		btn_add.pack(side="left", padx=5)

	def gerar_alertas(self):
		dados = self.dados
		mes = dados["mes_atual"]

		alertas = []

		salarios = sum(dados["salarios"].values())

		despesas = 0
		categorias = {}

		for d in dados["meses"][mes]["despesas"].values():
			if isinstance(d, dict):
				valor = d["valor"]
				cat = d["categoria"]
			else:
				valor = d
				cat = "Outros"

			despesas += valor
			categorias[cat] = categorias.get(cat, 0) + valor

		dividas = dados["dividas"]
		prestacoes = sum(d["prestacao"] for d in dividas.values())

		sobra = salarios - despesas - prestacoes

		# =====================
		# ALERTA 1 - Sobra negativa
		# =====================
		if sobra < 0:
			alertas.append(("🚨 Estás a gastar mais do que ganhas!", "red"))

		# =====================
		# ALERTA 2 - Sobra baixa
		# =====================
		elif sobra < 300:
			alertas.append(("⚠ Sobra muito baixa — risco financeiro", "orange"))

		# =====================
		# ALERTA 3 - Categoria dominante
		# =====================
		if categorias:
			maior = max(categorias, key=categorias.get)

			if categorias[maior] > despesas * 0.4:
				alertas.append((f"⚠ Muito gasto em {maior}", "orange"))

			# sugestão de corte
			corte = categorias[maior] * 0.2
			alertas.append((f"💡 Cortar 20% em {maior} poupa {corte:.0f} CHF", "gray"))

		# =====================
		# ALERTA 4 - Juros altos
		# =====================
		if dividas:
			pior = max(dividas.items(), key=lambda x: x[1]["taxa"])

			if pior[1]["taxa"] > 10:
				alertas.append((f"🔥 Juros altos: {pior[0]} ({pior[1]['taxa']}%)", "red"))

		return alertas

	def calcular_score(self):
		dados = self.dados
		mes = dados["mes_atual"]

		score = 0
		detalhes = []

		salarios = sum(dados["salarios"].values())

		despesas = 0
		for d in dados["meses"][mes]["despesas"].values():
			despesas += d["valor"] if isinstance(d, dict) else d

		dividas = dados["dividas"]
		total_divida = sum(d["total"] for d in dividas.values())
		prestacoes = sum(d["prestacao"] for d in dividas.values())

		sobra = salarios - despesas - prestacoes

		# =====================
		# 1. SOBRA (40 pts)
		# =====================
		if sobra > 1000:
			score += 40
			detalhes.append("🟢 Excelente sobra mensal")
		elif sobra > 500:
			score += 30
			detalhes.append("🟡 Sobra razoável")
		elif sobra > 0:
			score += 15
			detalhes.append("🟠 Sobra baixa")
		else:
			detalhes.append("🔴 Sobra negativa")

		# =====================
		# 2. DESPESAS (20 pts)
		# =====================
		if salarios > 0:
			ratio = despesas / salarios

			if ratio < 0.5:
				score += 20
				detalhes.append("🟢 Despesas controladas")
			elif ratio < 0.7:
				score += 10
				detalhes.append("🟡 Despesas moderadas")
			else:
				detalhes.append("🔴 Despesas muito altas")

		# =====================
		# 3. DÍVIDA (20 pts)
		# =====================
		if salarios > 0:
			ratio_div = total_divida / (salarios * 12)

			if ratio_div < 1:
				score += 20
				detalhes.append("🟢 Dívida saudável")
			elif ratio_div < 2:
				score += 10
				detalhes.append("🟡 Dívida moderada")
			else:
				detalhes.append("🔴 Dívida elevada")

		# =====================
		# 4. JUROS (20 pts)
		# =====================
		if dividas:
			max_taxa = max(d["taxa"] for d in dividas.values())

			if max_taxa < 5:
				score += 20
				detalhes.append("🟢 Juros baixos")
			elif max_taxa < 10:
				score += 10
				detalhes.append("🟡 Juros médios")
			else:
				detalhes.append("🔴 Juros altos")

		if self.total_pendentes() > 0:
			score -= 10
			detalhes.append("Pendentes acumulados")

		return score, detalhes
	
	def calcular_info_divida(self, divida):
		total = float(divida.get("total", 0))
		taxa_mensal = float(divida.get("taxa", 0)) / 100 / 12
		prestacao = float(divida.get("prestacao", 0))

		if total <= 0:
			return "Liquidada"

		if prestacao <= 0:
			return "Sem prestação"

		if prestacao <= total * taxa_mensal:
			return "Não amortiza"

		meses = 0
		saldo = total

		while saldo > 0 and meses < 600:
			juros = saldo * taxa_mensal
			saldo = saldo + juros - prestacao
			meses += 1

		if meses >= 600:
			return "> 600 meses"

		return f"{meses} meses"
	
	def mostrar_progresso_dividas(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="📊 Progresso das Dívidas", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		if not self.dados["dividas"]:
			ctk.CTkLabel(self.main, text="Ainda não tens dívidas registadas.").pack(pady=20)
			return

		for nome, d in self.dados["dividas"].items():
			frame = ctk.CTkFrame(self.main)
			frame.pack(fill="x", padx=20, pady=8)

			inicial = float(d.get("inicial", d["total"]))
			total = float(d.get("total", 0))
			taxa = float(d.get("taxa", 0))
			prestacao = float(d.get("prestacao", 0))

			if inicial <= 0:
				progresso = 0
			else:
				progresso = (inicial - total) / inicial
				progresso = max(0, min(1, progresso))

			top = ctk.CTkFrame(frame, fg_color="transparent")
			top.pack(fill="x", padx=10, pady=(10, 5))

			ctk.CTkLabel(top, text=nome, font=("Arial", 16, "bold")).pack(side="left")
			ctk.CTkLabel(top, text=f"{progresso * 100:.1f}% pago").pack(side="right")

			bar = ctk.CTkProgressBar(frame)
			bar.pack(fill="x", padx=10, pady=5)
			bar.set(progresso)

			info = ctk.CTkFrame(frame, fg_color="transparent")
			info.pack(fill="x", padx=10, pady=(5, 10))

			ctk.CTkLabel(info, text=f"Inicial: {inicial:.2f} CHF").pack(anchor="w")
			ctk.CTkLabel(info, text=f"Atual: {total:.2f} CHF").pack(anchor="w")
			ctk.CTkLabel(info, text=f"Prestação: {prestacao:.2f} CHF").pack(anchor="w")
			ctk.CTkLabel(info, text=f"Taxa: {taxa:.2f}%").pack(anchor="w")
			ctk.CTkLabel(info, text=f"Tempo estimado: {self.calcular_info_divida(d)}").pack(anchor="w")

	def calcular_valor_meta(self, tipo):
		mes = self.dados["mes_atual"]

		salarios = self.total_entradas_mensais()

		despesas = 0
		for d in self.dados["meses"][mes]["despesas"].values():
			despesas += d["valor"] if isinstance(d, dict) else d

		total_divida = sum(d["total"] for d in self.dados["dividas"].values())
		prestacoes = sum(d["prestacao"] for d in self.dados["dividas"].values())

		disponivel = salarios - despesas - prestacoes

		if tipo == "poupanca":
			return disponivel
		elif tipo == "despesas":
			return despesas
		elif tipo == "divida":
			return total_divida

		return 0

	def mostrar_metas(self):
		self.limpar_main()

		if "metas" not in self.dados:
			self.dados["metas"] = []

		titulo = ctk.CTkLabel(self.main, text="🎯 Metas", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		# =====================
		# LISTA DE METAS
		# =====================
		container = ctk.CTkScrollableFrame(self.main)
		container.pack(fill="both", expand=True, padx=20, pady=10)

		if not self.dados["metas"]:
			ctk.CTkLabel(container, text="Ainda não tens metas definidas.").pack(pady=10)

		for i, meta in enumerate(self.dados["metas"]):
			frame = ctk.CTkFrame(container)
			frame.pack(fill="x", pady=8)

			nome = meta["nome"]
			tipo = meta["tipo"]
			alvo = float(meta["alvo"])

			atual = self.calcular_valor_meta(tipo)

			if tipo == "poupanca":
				progresso = 0 if alvo <= 0 else max(0, min(1, atual / alvo))
				texto_tipo = "Poupança"
				bom = atual >= alvo
			elif tipo == "despesas":
				progresso = 1 if atual <= alvo else max(0, min(1, alvo / atual))
				texto_tipo = "Despesas"
				bom = atual <= alvo
			elif tipo == "divida":
				progresso = 1 if atual <= alvo else max(0, min(1, alvo / atual))
				texto_tipo = "Dívida"
				bom = atual <= alvo
			else:
				progresso = 0
				texto_tipo = tipo
				bom = False

			top = ctk.CTkFrame(frame, fg_color="transparent")
			top.pack(fill="x", padx=10, pady=(10, 5))

			ctk.CTkLabel(top, text=nome, font=("Arial", 16, "bold")).pack(side="left")
			ctk.CTkLabel(top, text=f"{texto_tipo}", font=("Arial", 12)).pack(side="right")

			ctk.CTkLabel(frame, text=f"Atual: {atual:.2f} CHF | Alvo: {alvo:.2f} CHF").pack(anchor="w", padx=10)

			bar = ctk.CTkProgressBar(frame)
			bar.pack(fill="x", padx=10, pady=5)
			bar.set(progresso)

			cor = "green" if bom else "orange"
			estado = "Atingida ✅" if bom else "Em progresso ⏳"
			ctk.CTkLabel(frame, text=estado, text_color=cor).pack(anchor="w", padx=10, pady=(0, 5))

			def remover_meta(index=i):
				del self.dados["metas"][index]
				guardar(self.dados)
				self.mostrar_metas()

			ctk.CTkButton(frame, text="❌ Remover", width=100, command=remover_meta).pack(padx=10, pady=(0, 10), anchor="e")

		# =====================
		# ADICIONAR META
		# =====================
		form = ctk.CTkFrame(self.main)
		form.pack(fill="x", padx=20, pady=10)

		nome_entry = ctk.CTkEntry(form, placeholder_text="Nome da meta")
		nome_entry.pack(side="left", padx=5, pady=10)

		tipo_menu = ctk.CTkOptionMenu(form, values=["poupanca", "despesas", "divida"])
		tipo_menu.set("poupanca")
		tipo_menu.pack(side="left", padx=5)

		alvo_entry = ctk.CTkEntry(form, placeholder_text="Valor alvo")
		alvo_entry.pack(side="left", padx=5)

		def adicionar_meta():
			self.dados["metas"].append({
				"nome": nome_entry.get(),
				"tipo": tipo_menu.get(),
				"alvo": float(alvo_entry.get())
			})
			guardar(self.dados)
			self.mostrar_metas()

		ctk.CTkButton(form, text="Adicionar Meta", command=adicionar_meta).pack(side="left", padx=5)

	def garantir_despesas_fixas(self):
		if "despesas_fixas" not in self.dados:
			self.dados["despesas_fixas"] = {}

	def mostrar_despesas_fixas(self):
		self.limpar_main()
		self.garantir_despesas_fixas()

		titulo = ctk.CTkLabel(self.main, text="⚙️ Despesas Fixas", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		# =====================
		# LISTA
		# =====================
		container = ctk.CTkScrollableFrame(self.main)
		container.pack(fill="both", expand=True, padx=20, pady=10)

		for nome, info in self.dados["despesas_fixas"].items():
			frame = ctk.CTkFrame(container)
			frame.pack(fill="x", pady=6)

			ctk.CTkLabel(frame, text=nome, width=160, anchor="w").pack(side="left", padx=5)

			valor_entry = ctk.CTkEntry(frame, width=100)
			valor_entry.insert(0, str(info["valor"]))
			valor_entry.pack(side="left", padx=5)

			cat_entry = ctk.CTkEntry(frame, width=140)
			cat_entry.insert(0, info["categoria"])
			cat_entry.pack(side="left", padx=5)

			def guardar_fixa(n=nome, v=valor_entry, c=cat_entry):
				self.dados["despesas_fixas"][n] = {
					"valor": float(v.get()),
					"categoria": c.get()
				}
				guardar(self.dados)
				self.mostrar_despesas_fixas()

			def remover_fixa(n=nome):
				del self.dados["despesas_fixas"][n]
				guardar(self.dados)
				self.mostrar_despesas_fixas()

			ctk.CTkButton(frame, text="Guardar", width=90, command=guardar_fixa).pack(side="left", padx=5)
			ctk.CTkButton(frame, text="❌", width=40, command=remover_fixa).pack(side="right", padx=5)

		# =====================
		# ADICIONAR NOVA
		# =====================
		form = ctk.CTkFrame(self.main)
		form.pack(fill="x", padx=20, pady=10)

		nome_entry = ctk.CTkEntry(form, placeholder_text="Nome")
		nome_entry.pack(side="left", padx=5, pady=10)

		valor_entry = ctk.CTkEntry(form, placeholder_text="Valor")
		valor_entry.pack(side="left", padx=5)

		cat_entry = ctk.CTkEntry(form, placeholder_text="Categoria")
		cat_entry.pack(side="left", padx=5)

		def adicionar_fixa():
			self.dados["despesas_fixas"][nome_entry.get()] = {
				"valor": float(valor_entry.get()),
				"categoria": cat_entry.get()
			}
			guardar(self.dados)
			self.mostrar_despesas_fixas()

		ctk.CTkButton(form, text="Adicionar", command=adicionar_fixa).pack(side="left", padx=5)

		# =====================
		# APLICAR AO MÊS ATUAL
		# =====================
		acoes = ctk.CTkFrame(self.main)
		acoes.pack(fill="x", padx=20, pady=(0, 15))

		def aplicar_mes_atual():
			mes = self.dados["mes_atual"]

			if mes not in self.dados["meses"]:
				self.dados["meses"][mes] = {"despesas": {}}

			if "despesas" not in self.dados["meses"][mes]:
				self.dados["meses"][mes]["despesas"] = {}

			for nome, info in self.dados["despesas_fixas"].items():
				self.dados["meses"][mes]["despesas"][nome] = {
					"valor": info["valor"],
					"categoria": info["categoria"],
					"pago": False
				}

			guardar(self.dados)
			self.mostrar_despesas_fixas()

		ctk.CTkButton(
			acoes,
			text="Aplicar ao mês atual",
			command=aplicar_mes_atual
		).pack(anchor="w", padx=5, pady=5)

	def aplicar_despesas_fixas_ao_mes(self, mes):
		self.garantir_despesas_fixas()

		if mes not in self.dados["meses"]:
			self.dados["meses"][mes] = {"despesas": {}}

		if "despesas" not in self.dados["meses"][mes]:
			self.dados["meses"][mes]["despesas"] = {}

		for nome, info in self.dados["despesas_fixas"].items():
			# só adiciona se ainda não existir
			if nome not in self.dados["meses"][mes]["despesas"]:
				self.dados["meses"][mes]["despesas"][nome] = {
					"valor": info["valor"],
					"categoria": info["categoria"]
				}

	def garantir_contribuicoes(self):
		if "contribuicoes" not in self.dados:
			self.dados["contribuicoes"] = {}

	def total_entradas_mensais(self):
		self.garantir_contribuicoes()
		return sum(self.dados["salarios"].values()) + sum(self.dados["contribuicoes"].values())
	
	def mostrar_contribuicoes(self):
		self.limpar_main()
		self.garantir_contribuicoes()

		titulo = ctk.CTkLabel(self.main, text="👥 Contribuições Mensais", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		sub = ctk.CTkLabel(
			self.main,
			text=f"Total atual: {sum(self.dados['contribuicoes'].values()):.2f} CHF",
			font=("Arial", 14)
		)
		sub.pack(pady=(0, 10))

		container = ctk.CTkScrollableFrame(self.main)
		container.pack(fill="both", expand=True, padx=20, pady=10)

		if not self.dados["contribuicoes"]:
			ctk.CTkLabel(container, text="Ainda não tens contribuições registadas.").pack(pady=10)

		for nome, valor in self.dados["contribuicoes"].items():
			frame = ctk.CTkFrame(container)
			frame.pack(fill="x", pady=6)

			ctk.CTkLabel(frame, text=nome, width=180, anchor="w").pack(side="left", padx=8, pady=8)

			entry = ctk.CTkEntry(frame, width=120)
			entry.insert(0, str(valor))
			entry.pack(side="left", padx=8)

			def guardar_contribuicao(n=nome, e=entry):
				self.dados["contribuicoes"][n] = float(e.get())
				guardar(self.dados)
				self.mostrar_contribuicoes()

			def remover_contribuicao(n=nome):
				del self.dados["contribuicoes"][n]
				guardar(self.dados)
				self.mostrar_contribuicoes()

			ctk.CTkButton(frame, text="Guardar", width=90, command=guardar_contribuicao).pack(side="left", padx=5)
			ctk.CTkButton(frame, text="❌", width=40, command=remover_contribuicao).pack(side="right", padx=8)

		form = ctk.CTkFrame(self.main)
		form.pack(fill="x", padx=20, pady=10)

		nome_entry = ctk.CTkEntry(form, placeholder_text="Nome")
		nome_entry.pack(side="left", padx=6, pady=10)

		valor_entry = ctk.CTkEntry(form, placeholder_text="Valor mensal")
		valor_entry.pack(side="left", padx=6)

		def adicionar_contribuicao():
			nome = nome_entry.get().strip()
			valor = valor_entry.get().strip()

			if not nome or not valor:
				return

			self.dados["contribuicoes"][nome] = float(valor)
			guardar(self.dados)
			self.mostrar_contribuicoes()

		ctk.CTkButton(form, text="Adicionar", command=adicionar_contribuicao).pack(side="left", padx=6)

	def garantir_pendentes(self):
		if "pendentes" not in self.dados:
			self.dados["pendentes"] = {}

	def calcular_meses_pendentes(self, desde, ate=None):
		if ate is None:
			ate = self.dados["mes_atual"]

		try:
			ano_inicio, mes_inicio = map(int, desde.split("-"))
			ano_fim, mes_fim = map(int, ate.split("-"))
		except:
			return 0

		total = (ano_fim - ano_inicio) * 12 + (mes_fim - mes_inicio) + 1
		return max(0, total)
	
	def mostrar_pendentes(self):
		self.limpar_main()
		self.garantir_pendentes()

		titulo = ctk.CTkLabel(self.main, text="📌 Pendentes", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		total_geral = 0
		for nome, info in self.dados["pendentes"].items():
			meses = self.calcular_meses_pendentes(info["desde"])
			total_geral += float(info["valor_mensal"]) * meses

		sub = ctk.CTkLabel(
			self.main,
			text=f"Total pendente acumulado: {total_geral:.2f} CHF",
			font=("Arial", 15, "bold"),
			text_color="#FFA500"
		)
		sub.pack(pady=(0, 10))

		container = ctk.CTkScrollableFrame(self.main)
		container.pack(fill="both", expand=True, padx=20, pady=10)

		if not self.dados["pendentes"]:
			ctk.CTkLabel(container, text="Ainda não tens pendentes registados.").pack(pady=10)

		for nome, info in self.dados["pendentes"].items():
			valor_mensal = float(info["valor_mensal"])
			desde = info["desde"]
			notas = info.get("notas", "")
			meses = self.calcular_meses_pendentes(desde)
			total = valor_mensal * meses

			frame = ctk.CTkFrame(container)
			frame.pack(fill="x", pady=8)

			top = ctk.CTkFrame(frame, fg_color="transparent")
			top.pack(fill="x", padx=10, pady=(10, 5))

			ctk.CTkLabel(top, text=nome, font=("Arial", 16, "bold")).pack(side="left")
			ctk.CTkLabel(top, text=f"{total:.2f} CHF", text_color="#FFA500").pack(side="right")

			body = ctk.CTkFrame(frame, fg_color="transparent")
			body.pack(fill="x", padx=10, pady=(0, 10))

			ctk.CTkLabel(body, text=f"Valor mensal: {valor_mensal:.2f} CHF").pack(anchor="w")
			ctk.CTkLabel(body, text=f"Desde: {desde}").pack(anchor="w")
			ctk.CTkLabel(body, text=f"Meses em atraso: {meses}").pack(anchor="w")
			ctk.CTkLabel(body, text=f"Notas: {notas if notas else '-'}").pack(anchor="w")

			botoes = ctk.CTkFrame(body, fg_color="transparent")
			botoes.pack(anchor="e", pady=(8, 0))

			def editar_pendente(n=nome):
				self.editar_pendente_popup(n)

			def remover_pendente(n=nome):
				del self.dados["pendentes"][n]
				guardar(self.dados)
				self.mostrar_pendentes()

			def converter_pendente(n=nome):
				self.converter_pendente_em_divida(n)

			ctk.CTkButton(botoes, text="Editar", width=80, command=editar_pendente).pack(side="left", padx=4)
			ctk.CTkButton(botoes, text="Converter", width=90, command=converter_pendente).pack(side="left", padx=4)
			ctk.CTkButton(botoes, text="❌", width=40, command=remover_pendente).pack(side="left", padx=4)

		form = ctk.CTkFrame(self.main)
		form.pack(fill="x", padx=20, pady=10)

		nome_entry = ctk.CTkEntry(form, placeholder_text="Nome", width=180)
		nome_entry.pack(side="left", padx=5, pady=10)

		valor_entry = ctk.CTkEntry(form, placeholder_text="Valor mensal", width=120)
		valor_entry.pack(side="left", padx=5)

		desde_entry = ctk.CTkEntry(form, placeholder_text="Desde (YYYY-MM)", width=140)
		desde_entry.pack(side="left", padx=5)

		notas_entry = ctk.CTkEntry(form, placeholder_text="Notas", width=220)
		notas_entry.pack(side="left", padx=5)

		def adicionar_pendente():
			nome = nome_entry.get().strip()
			valor = valor_entry.get().strip()
			desde = desde_entry.get().strip()
			notas = notas_entry.get().strip()

			if not nome:
				self.erro("Nome é obrigatório")
				return

			if not valor or not self.validar_float(valor):
				self.erro("Valor mensal inválido")
				return

			if not desde or not self.validar_data_mes(desde):
				self.erro("Data inválida (usar YYYY-MM)")
				return

			self.dados["pendentes"][nome] = {
				"valor_mensal": float(valor),
				"desde": desde,
				"notas": notas
			}
			guardar(self.dados)
			self.mostrar_pendentes()

		ctk.CTkButton(form, text="Adicionar", command=adicionar_pendente).pack(side="left", padx=5)

	def editar_pendente_popup(self, nome_pendente):
		self.garantir_pendentes()

		if nome_pendente not in self.dados["pendentes"]:
			return

		info = self.dados["pendentes"][nome_pendente]

		janela = ctk.CTkToplevel(self)
		janela.title("Editar Pendente")
		largura = 560
		altura = 360

		x = self.winfo_x() + (self.winfo_width() // 2) - (largura // 2)
		y = self.winfo_y() + (self.winfo_height() // 2) - (altura // 2)

		janela.geometry(f"{largura}x{altura}+{x}+{y}")
		janela.resizable(False, False)
		janela.transient(self)
		janela.grab_set()
		janela.focus()

		ctk.CTkLabel(janela, text="Nome").pack(pady=(10, 2))
		nome_entry = ctk.CTkEntry(janela, width=300)
		nome_entry.insert(0, nome_pendente)
		nome_entry.pack()

		ctk.CTkLabel(janela, text="Valor mensal").pack(pady=(10, 2))
		valor_entry = ctk.CTkEntry(janela, width=300)
		valor_entry.insert(0, str(info["valor_mensal"]))
		valor_entry.pack()

		ctk.CTkLabel(janela, text="Desde (YYYY-MM)").pack(pady=(10, 2))
		desde_entry = ctk.CTkEntry(janela, width=300)
		desde_entry.insert(0, info["desde"])
		desde_entry.pack()

		ctk.CTkLabel(janela, text="Notas").pack(pady=(10, 2))
		notas_entry = ctk.CTkEntry(janela, width=300)
		notas_entry.insert(0, info.get("notas", ""))
		notas_entry.pack()

		def guardar_edicao():
			novo_nome = nome_entry.get().strip()
			valor_txt = valor_entry.get().strip()

			if not valor_txt:
				self.erro("Valor é obrigatório")
				return

			if not self.validar_float(valor_txt):
				self.erro("Valor inválido")
				return

			valor = float(valor_txt)

			desde = desde_entry.get().strip()
			notas = notas_entry.get().strip()

			del self.dados["pendentes"][nome_pendente]
			self.dados["pendentes"][novo_nome] = {
				"valor_mensal": valor,
				"desde": desde,
				"notas": notas
			}

			guardar(self.dados)
			janela.destroy()
			self.mostrar_pendentes()

		ctk.CTkButton(janela, text="Guardar", command=guardar_edicao).pack(pady=15)

	def total_pendentes(self):
		self.garantir_pendentes()

		total = 0
		for nome, info in self.dados["pendentes"].items():
			meses = self.calcular_meses_pendentes(info["desde"])
			total += float(info["valor_mensal"]) * meses

		return total
	
	def converter_pendente_em_divida(self, nome_pendente):
		self.garantir_pendentes()

		if nome_pendente not in self.dados["pendentes"]:
			return

		info = self.dados["pendentes"][nome_pendente]

		valor_mensal = float(info["valor_mensal"])
		desde = info["desde"]
		meses = self.calcular_meses_pendentes(desde)
		total = valor_mensal * meses

		resposta = messagebox.askyesno(
			"Converter pendente",
			f"Queres converter '{nome_pendente}' em dívida?\n\n"
			f"Meses em atraso: {meses}\n"
			f"Total acumulado: {total:.2f} CHF"
		)

		if not resposta:
			return

		nome_divida = nome_pendente

		if nome_divida in self.dados["dividas"]:
			nome_divida = f"{nome_pendente} (pendente)"

		self.dados["dividas"][nome_divida] = {
			"inicial": total,
			"total": total,
			"taxa": 0.0,
			"prestacao": 0.0
		}

		del self.dados["pendentes"][nome_pendente]

		guardar(self.dados)
		self.mostrar_pendentes()

	def mostrar_planeamento(self):
		self.limpar_main()

		titulo = ctk.CTkLabel(self.main, text="📅 Planeamento", font=("Arial", 22, "bold"))
		titulo.pack(pady=15)

		mes = self.dados["mes_atual"]
		entradas = self.total_entradas_mensais()
		pendentes = self.total_pendentes()

		self.garantir_saldo_inicial()
		saldo_inicial = float(self.dados["saldo_inicial"])

		despesas = 0
		for d in self.dados["meses"][mes]["despesas"].values():
			despesas += d["valor"] if isinstance(d, dict) else d

		dividas = self.dados["dividas"]
		total_divida = sum(d["total"] for d in dividas.values())
		total_prestacoes = sum(d["prestacao"] for d in dividas.values())

		sobra = entradas - despesas - total_prestacoes

		saldo_real = saldo_inicial + sobra

		if total_divida <= 0:
			meses_liberdade = 0
		elif sobra <= 0:
			meses_liberdade = "∞"
		else:
			meses_liberdade = int(total_divida / sobra)

		if saldo_real >= 0:
			meses_ate_zero = 0
		elif sobra > 0:
			meses_ate_zero = int(abs(saldo_inicial) / sobra) + 1
		else:
			meses_ate_zero = "∞"

		if dividas:
			pior = max(dividas.items(), key=lambda x: x[1]["taxa"])
			divida_prioritaria = f"{pior[0]} ({pior[1]['taxa']:.2f}%)"
		else:
			divida_prioritaria = "Sem dívidas"

		score, detalhes = self.calcular_score()

		# topo
		top = ctk.CTkFrame(self.main)
		top.pack(fill="x", padx=20, pady=10)

		def card(parent, titulo, valor, cor=None):
			frame = ctk.CTkFrame(parent, corner_radius=10)
			frame.pack(side="left", expand=True, fill="x", padx=8)

			ctk.CTkLabel(frame, text=titulo, font=("Arial", 12)).pack(pady=(10, 4))

			lbl = ctk.CTkLabel(frame, text=str(valor), font=("Arial", 18, "bold"))
			if cor:
				lbl.configure(text_color=cor)
			lbl.pack(pady=(0, 10))

		card(top, "💰 Sobra mensal", f"{sobra:.2f} CHF", "green" if sobra >= 0 else "red")
		card(top, "🏦 Saldo real", f"{saldo_real:.2f} CHF", "green" if saldo_real >= 0 else "red")
		card(top, "📌 Pendentes", f"{pendentes:.2f} CHF", "#FFA500" if pendentes > 0 else None)
		card(top, "⏳ Liberdade", f"{meses_liberdade} meses")

		# resumo principal
		meio = ctk.CTkFrame(self.main)
		meio.pack(fill="x", padx=20, pady=10)

		left = ctk.CTkFrame(meio)
		left.pack(side="left", expand=True, fill="both", padx=8)

		right = ctk.CTkFrame(meio)
		right.pack(side="left", expand=True, fill="both", padx=8)

		ctk.CTkLabel(left, text="Resumo", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))
		ctk.CTkLabel(left, text=f"Mês atual: {mes}").pack(anchor="w", padx=10)
		ctk.CTkLabel(left, text=f"Entradas mensais: {entradas:.2f} CHF").pack(anchor="w", padx=10)
		ctk.CTkLabel(left, text=f"Despesas mensais: {despesas:.2f} CHF").pack(anchor="w", padx=10)
		ctk.CTkLabel(left, text=f"Prestações: {total_prestacoes:.2f} CHF").pack(anchor="w", padx=10)
		ctk.CTkLabel(left, text=f"Dívida prioritária: {divida_prioritaria}").pack(anchor="w", padx=10, pady=(0, 10))
		ctk.CTkLabel(left, text=f"Meses até sair do negativo: {meses_ate_zero}").pack(anchor="w", padx=10)

		ctk.CTkLabel(right, text="Próxima ação recomendada", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))

		if sobra <= 0:
			acao = "Reduzir despesas ou aumentar entradas antes de acelerar dívida."
		elif pendentes > 0:
			acao = "Regularizar ou converter pendentes em dívida para ter visão real."
		elif dividas:
			acao = f"Focar pagamento extra em {divida_prioritaria}."
		else:
			acao = "Sem dívida ativa. Focar poupança e metas."
		ctk.CTkLabel(right, text=acao, wraplength=320, justify="left").pack(anchor="w", padx=10)

		ctk.CTkLabel(right, text=f"Score financeiro: {score}/100", font=("Arial", 15, "bold")).pack(anchor="w", padx=10, pady=(12, 4))
		for d in detalhes[:4]:
			ctk.CTkLabel(right, text=d).pack(anchor="w", padx=18)
		ctk.CTkLabel(right, text="").pack(pady=5)

		# atalhos
		bottom = ctk.CTkFrame(self.main)
		bottom.pack(fill="x", padx=20, pady=10)

		ctk.CTkLabel(bottom, text="Ferramentas", font=("Arial", 18, "bold")).pack(anchor="w", padx=10, pady=(10, 8))

		linha = ctk.CTkFrame(bottom, fg_color="transparent")
		linha.pack(padx=10, pady=(0, 10), anchor="w")

		ctk.CTkButton(linha, text="Timeline", width=120, command=self.timeline_divida).pack(side="left", padx=5)
		ctk.CTkButton(linha, text="Simulação", width=120, command=self.modo_dividas).pack(side="left", padx=5)
		ctk.CTkButton(linha, text="Análise", width=120, command=self.analise_financeira).pack(side="left", padx=5)
		ctk.CTkButton(linha, text="Metas", width=120, command=self.mostrar_metas).pack(side="left", padx=5)

	def garantir_saldo_inicial(self):
		if "saldo_inicial" not in self.dados:
			self.dados["saldo_inicial"] = 0.0

	def mostrar_saldo_inicial(self):
		self.limpar_main()
		self.garantir_saldo_inicial()

		titulo = ctk.CTkLabel(self.main, text="💰 Saldo Inicial", font=("Arial", 20, "bold"))
		titulo.pack(pady=15)

		info = ctk.CTkLabel(
			self.main,
			text="Usa este valor para indicar com quanto estás a começar.\nPode ser negativo ou positivo.",
			justify="center"
		)
		info.pack(pady=(0, 15))

		frame = ctk.CTkFrame(self.main)
		frame.pack(padx=20, pady=10)

		entry = ctk.CTkEntry(frame, width=180)
		entry.insert(0, str(self.dados["saldo_inicial"]))
		entry.pack(side="left", padx=8, pady=10)

		def guardar_saldo():
			try:
				self.dados["saldo_inicial"] = float(entry.get())
				guardar(self.dados)
				self.mostrar_saldo_inicial()
			except:
				pass

		ctk.CTkButton(frame, text="Guardar", command=guardar_saldo).pack(side="left", padx=8)

		atual = self.dados["saldo_inicial"]
		cor = "green" if atual >= 0 else "red"

		ctk.CTkLabel(
			self.main,
			text=f"Saldo atual configurado: {atual:.2f} CHF",
			font=("Arial", 16, "bold"),
			text_color=cor
		).pack(pady=15)

	def calcular_saldo_acumulado(self):
		self.garantir_saldo_inicial()

		saldo = float(self.dados["saldo_inicial"])
		resultado = {}

		for mes in sorted(self.dados["meses"].keys()):
			entradas = self.total_entradas_mensais()

			despesas = 0
			for d in self.dados["meses"][mes]["despesas"].values():
				despesas += d["valor"] if isinstance(d, dict) else d

			prestacoes = sum(d["prestacao"] for d in self.dados["dividas"].values())

			sobra = entradas - despesas - prestacoes
			saldo += sobra

			resultado[mes] = {
				"sobra": sobra,
				"saldo": saldo
			}

		return resultado
	
	def calcular_saldos_acumulados(self):
		self.garantir_saldo_inicial()

		saldo = float(self.dados["saldo_inicial"])
		resultado = {}

		for mes in sorted(self.dados["meses"].keys()):
			entradas = self.total_entradas_mensais()

			despesas = 0
			for d in self.dados["meses"][mes]["despesas"].values():
				despesas += d["valor"] if isinstance(d, dict) else d

			prestacoes = sum(d["prestacao"] for d in self.dados["dividas"].values())
			sobra = entradas - despesas - prestacoes

			saldo += sobra

			resultado[mes] = {
				"sobra": sobra,
				"saldo": saldo
			}

		return resultado
	
	def parse_float(self, valor, default=None):
		try:
			valor = valor.replace(",", ".")
			return float(valor)
		except:
			return default

	def validar_float(self, valor):
		try:
			float(valor)
			return True
		except:
			return False


	def validar_data_mes(self, texto):
		try:
			ano, mes = map(int, texto.split("-"))
			return 1 <= mes <= 12 and ano > 2000
		except:
			return False
		
	def erro(self, mensagem):
		messagebox.showerror("Erro", mensagem)

app = App()
app.mainloop()