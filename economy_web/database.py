import json
import os
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "economy_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "C.entrino051497")
DB_NAME = os.environ.get("DB_NAME", "economy_db")

JSON_FILE = "dados.json"


def get_connection():
	return pymysql.connect(
		host=DB_HOST,
		user=DB_USER,
		password=DB_PASSWORD,
		database=DB_NAME,
		charset="utf8mb4",
		autocommit=False,
		cursorclass=pymysql.cursors.DictCursor,
	)

def init_db():
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
	CREATE TABLE IF NOT EXISTS config (
		`key` VARCHAR(255) PRIMARY KEY,
		value TEXT
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS salarios (
		id INT AUTO_INCREMENT PRIMARY KEY,
		nome TEXT NOT NULL UNIQUE,
		valor REAL NOT NULL
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS contribuicoes (
		id INT AUTO_INCREMENT PRIMARY KEY,
		nome TEXT NOT NULL UNIQUE,
		valor REAL NOT NULL
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS categorias (
		id INT AUTO_INCREMENT PRIMARY KEY,
		nome TEXT NOT NULL UNIQUE
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS despesas (
		id INT AUTO_INCREMENT PRIMARY KEY,
		mes TEXT NOT NULL,
		nome TEXT NOT NULL,
		valor REAL NOT NULL,
		categoria TEXT NOT NULL,
		pago INTEGER NOT NULL DEFAULT 0
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS dividas (
		id INT AUTO_INCREMENT PRIMARY KEY,
		nome TEXT NOT NULL UNIQUE,
		inicial REAL NOT NULL,
		total REAL NOT NULL,
		taxa REAL NOT NULL,
		prestacao REAL NOT NULL
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS pendentes (
		id INT AUTO_INCREMENT PRIMARY KEY,
		nome TEXT NOT NULL UNIQUE,
		valor_mensal REAL NOT NULL,
		desde TEXT NOT NULL,
		notas TEXT DEFAULT ''
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS despesas_fixas (
		id INT AUTO_INCREMENT PRIMARY KEY,
		nome TEXT NOT NULL UNIQUE,
		valor REAL NOT NULL,
		categoria TEXT NOT NULL
	)
	""")

	cur.execute("""
	CREATE TABLE IF NOT EXISTS metas (
		id INT AUTO_INCREMENT PRIMARY KEY,
		nome TEXT NOT NULL,
		tipo TEXT NOT NULL,
		alvo REAL NOT NULL
	)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS users (
			id INT AUTO_INCREMENT PRIMARY KEY,
			username TEXT NOT NULL UNIQUE,
			password_hash TEXT NOT NULL,
			is_admin INTEGER NOT NULL DEFAULT 0
		)
		""")

	conn.commit()
	conn.close()


def ensure_default_admin(username, password):
	init_db()
	conn = get_connection()
	cur = conn.cursor()
	cur.execute("SELECT id FROM users LIMIT 1")
	existe = cur.fetchone()

	if not existe:
		cur.execute(
			"INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, 1)",
			(username, generate_password_hash(password))
		)
		conn.commit()

	conn.close()


def get_user_by_username(username):
	init_db()
	conn = get_connection()
	cur = conn.cursor()
	cur.execute("SELECT id, username, password_hash, is_admin FROM users WHERE username = %s", (username,))
	row = cur.fetchone()
	conn.close()
	return row


def authenticate_user(username, password):
	user = get_user_by_username(username)
	if not user:
		return None

	if check_password_hash(user["password_hash"], password):
		return {
			"id": user["id"],
			"username": user["username"],
			"is_admin": bool(user["is_admin"])
		}

	return None


def list_users():
	init_db()
	conn = get_connection()
	cur = conn.cursor()
	cur.execute("SELECT id, username, is_admin FROM users ORDER BY username")
	rows = cur.fetchall()
	conn.close()
	return rows


def add_user(username, password, is_admin=False):
	init_db()
	conn = get_connection()
	cur = conn.cursor()
	cur.execute(
		"INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)",
		(username, generate_password_hash(password), 1 if is_admin else 0)
	)
	conn.commit()
	conn.close()


def delete_user(username):
	init_db()
	conn = get_connection()
	cur = conn.cursor()
	cur.execute("DELETE FROM users WHERE username = %s", (username,))
	conn.commit()
	conn.close()


def set_config(key, value):
	conn = get_connection()
	cur = conn.cursor()
	cur.execute("""
		INSERT INTO config (`key`, value)
		VALUES (%s, %s)
		ON DUPLICATE KEY UPDATE value = VALUES(value)
	""", (key, json.dumps(value)))
	conn.commit()
	conn.close()


def get_config(key, default=None):
	conn = get_connection()
	cur = conn.cursor()
	cur.execute("SELECT value FROM config WHERE key = %s", (key,))
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

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()