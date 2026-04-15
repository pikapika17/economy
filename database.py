import sqlite3
import json
import os

DB_FILE = "economy.db"
JSON_FILE = "dados.json"


def get_connection():
	conn = sqlite3.connect(DB_FILE)
	conn.row_factory = sqlite3.Row
	return conn


def init_db():
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
	CREATE TABLE IF NOT EXISTS config (
		key TEXT PRIMARY KEY,
		value TEXT
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS salarios (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		nome TEXT NOT NULL UNIQUE,
		valor REAL NOT NULL
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS contribuicoes (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		nome TEXT NOT NULL UNIQUE,
		valor REAL NOT NULL
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS categorias (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		nome TEXT NOT NULL UNIQUE
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS despesas (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		mes TEXT NOT NULL,
		nome TEXT NOT NULL,
		valor REAL NOT NULL,
		categoria TEXT NOT NULL,
		pago INTEGER NOT NULL DEFAULT 0
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS dividas (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		nome TEXT NOT NULL UNIQUE,
		inicial REAL NOT NULL,
		total REAL NOT NULL,
		taxa REAL NOT NULL,
		prestacao REAL NOT NULL
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS pendentes (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		nome TEXT NOT NULL UNIQUE,
		valor_mensal REAL NOT NULL,
		desde TEXT NOT NULL,
		notas TEXT DEFAULT ''
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS despesas_fixas (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		nome TEXT NOT NULL UNIQUE,
		valor REAL NOT NULL,
		categoria TEXT NOT NULL
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS metas (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		nome TEXT NOT NULL,
		tipo TEXT NOT NULL,
		alvo REAL NOT NULL
	)
	""")

	conn.commit()
	conn.close()


def set_config(key, value):
	conn = get_connection()
	cur = conn.cursor()
	cur.execute("""
		INSERT INTO config (key, value)
		VALUES (?, ?)
		ON CONFLICT(key) DO UPDATE SET value=excluded.value
	""", (key, json.dumps(value)))
	conn.commit()
	conn.close()


def get_config(key, default=None):
	conn = get_connection()
	cur = conn.cursor()
	cur.execute("SELECT value FROM config WHERE key = ?", (key,))
	row = cur.fetchone()
	conn.close()

	if not row:
		return default

	try:
		return json.loads(row["value"])
	except Exception:
		return default


def migrate_from_json(json_file=JSON_FILE):
	if not os.path.exists(json_file):
		raise FileNotFoundError(f"Ficheiro não encontrado: {json_file}")

	with open(json_file, "r", encoding="utf-8") as f:
		dados = json.load(f)

	init_db()
	conn = get_connection()
	cur = conn.cursor()

	# limpar tudo antes de importar
	for table in [
		"config",
		"salarios",
		"contribuicoes",
		"categorias",
		"despesas",
		"dividas",
		"pendentes",
		"despesas_fixas",
		"metas",
	]:
		cur.execute(f"DELETE FROM {table}")

	# config
	cur.execute(
		"INSERT INTO config (key, value) VALUES (?, ?)",
		("mes_atual", json.dumps(dados.get("mes_atual", "")))
	)
	cur.execute(
		"INSERT INTO config (key, value) VALUES (?, ?)",
		("saldo_inicial", json.dumps(dados.get("saldo_inicial", 0.0)))
	)

	# salarios
	for nome, valor in dados.get("salarios", {}).items():
		cur.execute(
			"INSERT INTO salarios (nome, valor) VALUES (?, ?)",
			(nome, float(valor))
		)

	# contribuicoes
	for nome, valor in dados.get("contribuicoes", {}).items():
		cur.execute(
			"INSERT INTO contribuicoes (nome, valor) VALUES (?, ?)",
			(nome, float(valor))
		)

	# categorias
	for nome in dados.get("categorias", []):
		cur.execute(
			"INSERT INTO categorias (nome) VALUES (?)",
			(nome,)
		)

	# despesas
	for mes, info_mes in dados.get("meses", {}).items():
		for nome, info in info_mes.get("despesas", {}).items():
			if isinstance(info, dict):
				valor = float(info.get("valor", 0))
				categoria = info.get("categoria", "Sem categoria")
				pago = 1 if info.get("pago", False) else 0
			else:
				valor = float(info)
				categoria = "Sem categoria"
				pago = 0

			cur.execute("""
				INSERT INTO despesas (mes, nome, valor, categoria, pago)
				VALUES (?, ?, ?, ?, ?)
			""", (mes, nome, valor, categoria, pago))

	# dividas
	for nome, info in dados.get("dividas", {}).items():
		cur.execute("""
			INSERT INTO dividas (nome, inicial, total, taxa, prestacao)
			VALUES (?, ?, ?, ?, ?)
		""", (
			nome,
			float(info.get("inicial", info.get("total", 0))),
			float(info.get("total", 0)),
			float(info.get("taxa", 0)),
			float(info.get("prestacao", 0)),
		))

	# pendentes
	for nome, info in dados.get("pendentes", {}).items():
		cur.execute("""
			INSERT INTO pendentes (nome, valor_mensal, desde, notas)
			VALUES (?, ?, ?, ?)
		""", (
			nome,
			float(info.get("valor_mensal", 0)),
			info.get("desde", ""),
			info.get("notas", ""),
		))

	# despesas fixas
	for nome, info in dados.get("despesas_fixas", {}).items():
		cur.execute("""
			INSERT INTO despesas_fixas (nome, valor, categoria)
			VALUES (?, ?, ?)
		""", (
			nome,
			float(info.get("valor", 0)),
			info.get("categoria", "Sem categoria"),
		))

	# metas
	for meta in dados.get("metas", []):
		cur.execute("""
			INSERT INTO metas (nome, tipo, alvo)
			VALUES (?, ?, ?)
		""", (
			meta.get("nome", ""),
			meta.get("tipo", ""),
			float(meta.get("alvo", 0)),
		))

	conn.commit()
	conn.close()


def export_to_dict():
	conn = get_connection()
	cur = conn.cursor()

	dados = {}

	dados["mes_atual"] = get_config("mes_atual", "")
	dados["saldo_inicial"] = get_config("saldo_inicial", 0.0)

	cur.execute("SELECT nome, valor FROM salarios ORDER BY id")
	dados["salarios"] = {row["nome"]: row["valor"] for row in cur.fetchall()}

	cur.execute("SELECT nome, valor FROM contribuicoes ORDER BY id")
	dados["contribuicoes"] = {row["nome"]: row["valor"] for row in cur.fetchall()}

	cur.execute("SELECT nome FROM categorias ORDER BY nome")
	dados["categorias"] = [row["nome"] for row in cur.fetchall()]

	cur.execute("SELECT nome, inicial, total, taxa, prestacao FROM dividas ORDER BY id")
	dados["dividas"] = {
		row["nome"]: {
			"inicial": row["inicial"],
			"total": row["total"],
			"taxa": row["taxa"],
			"prestacao": row["prestacao"],
		}
		for row in cur.fetchall()
	}

	cur.execute("SELECT nome, valor_mensal, desde, notas FROM pendentes ORDER BY id")
	dados["pendentes"] = {
		row["nome"]: {
			"valor_mensal": row["valor_mensal"],
			"desde": row["desde"],
			"notas": row["notas"],
		}
		for row in cur.fetchall()
	}

	cur.execute("SELECT nome, valor, categoria FROM despesas_fixas ORDER BY id")
	dados["despesas_fixas"] = {
		row["nome"]: {
			"valor": row["valor"],
			"categoria": row["categoria"],
		}
		for row in cur.fetchall()
	}

	cur.execute("SELECT nome, tipo, alvo FROM metas ORDER BY id")
	dados["metas"] = [
		{
			"nome": row["nome"],
			"tipo": row["tipo"],
			"alvo": row["alvo"],
		}
		for row in cur.fetchall()
	]

	dados["meses"] = {}
	cur.execute("SELECT mes, nome, valor, categoria, pago FROM despesas ORDER BY mes, id")
	for row in cur.fetchall():
		mes = row["mes"]
		if mes not in dados["meses"]:
			dados["meses"][mes] = {"despesas": {}}

		dados["meses"][mes]["despesas"][row["nome"]] = {
			"valor": row["valor"],
			"categoria": row["categoria"],
			"pago": bool(row["pago"]),
		}

	conn.close()
	return dados

def save_all_from_dict(dados):
	conn = get_connection()
	cur = conn.cursor()

	try:
	
		# limpar tudo
		for table in [
			"config",
			"salarios",
			"contribuicoes",
			"categorias",
			"despesas",
			"dividas",
			"pendentes",
			"despesas_fixas",
			"metas",
		]:
			cur.execute(f"DELETE FROM {table}")

		# config
		cur.execute(
			"INSERT INTO config (key, value) VALUES (?, ?)",
			("mes_atual", json.dumps(dados.get("mes_atual", "")))
		)
		cur.execute(
			"INSERT INTO config (key, value) VALUES (?, ?)",
			("saldo_inicial", json.dumps(dados.get("saldo_inicial", 0.0)))
		)

		# salarios
		for nome, valor in dados.get("salarios", {}).items():
			cur.execute(
				"INSERT INTO salarios (nome, valor) VALUES (?, ?)",
				(nome, float(valor))
			)

		# contribuicoes
		for nome, valor in dados.get("contribuicoes", {}).items():
			cur.execute(
				"INSERT INTO contribuicoes (nome, valor) VALUES (?, ?)",
				(nome, float(valor))
			)

		# categorias
		for nome in dados.get("categorias", []):
			cur.execute(
				"INSERT INTO categorias (nome) VALUES (?)",
				(nome,)
			)

		# despesas
		for mes, info_mes in dados.get("meses", {}).items():
			for nome, info in info_mes.get("despesas", {}).items():
				if isinstance(info, dict):
					valor = float(info.get("valor", 0))
					categoria = info.get("categoria", "Sem categoria")
					pago = 1 if info.get("pago", False) else 0
				else:
					valor = float(info)
					categoria = "Sem categoria"
					pago = 0

				cur.execute("""
					INSERT INTO despesas (mes, nome, valor, categoria, pago)
					VALUES (?, ?, ?, ?, ?)
				""", (mes, nome, valor, categoria, pago))

		# dividas
		for nome, info in dados.get("dividas", {}).items():
			cur.execute("""
				INSERT INTO dividas (nome, inicial, total, taxa, prestacao)
				VALUES (?, ?, ?, ?, ?)
			""", (
				nome,
				float(info.get("inicial", info.get("total", 0))),
				float(info.get("total", 0)),
				float(info.get("taxa", 0)),
				float(info.get("prestacao", 0)),
			))

		# pendentes
		for nome, info in dados.get("pendentes", {}).items():
			cur.execute("""
				INSERT INTO pendentes (nome, valor_mensal, desde, notas)
				VALUES (?, ?, ?, ?)
			""", (
				nome,
				float(info.get("valor_mensal", 0)),
				info.get("desde", ""),
				info.get("notas", ""),
			))

		# despesas fixas
		for nome, info in dados.get("despesas_fixas", {}).items():
			cur.execute("""
				INSERT INTO despesas_fixas (nome, valor, categoria)
				VALUES (?, ?, ?)
			""", (
				nome,
				float(info.get("valor", 0)),
				info.get("categoria", "Sem categoria"),
			))

		# metas
		for meta in dados.get("metas", []):
			cur.execute("""
				INSERT INTO metas (nome, tipo, alvo)
				VALUES (?, ?, ?)
			""", (
				meta.get("nome", ""),
				meta.get("tipo", ""),
				float(meta.get("alvo", 0)),
			))

		conn.commit()
	except Exception as e:
		conn.rollback()
		raise e
	finally:
		conn.close()