import json
import os
from datetime import datetime
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "economy_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "C.entrino051497")
DB_NAME = os.environ.get("DB_NAME", "economy_db")


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


# ---------------- INIT DB ----------------

def init_db():
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		CREATE TABLE IF NOT EXISTS users (
			id INT AUTO_INCREMENT PRIMARY KEY,
			username VARCHAR(255) NOT NULL UNIQUE,
			password_hash TEXT NOT NULL,
			is_admin TINYINT(1) NOT NULL DEFAULT 0
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS config (
			`key` VARCHAR(255) PRIMARY KEY,
			value TEXT
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS salarios (
			id INT AUTO_INCREMENT PRIMARY KEY,
			nome VARCHAR(255) NOT NULL UNIQUE,
			valor DOUBLE NOT NULL
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS contribuicoes (
			id INT AUTO_INCREMENT PRIMARY KEY,
			nome VARCHAR(255) NOT NULL UNIQUE,
			valor DOUBLE NOT NULL
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS categorias (
			id INT AUTO_INCREMENT PRIMARY KEY,
			nome VARCHAR(255) NOT NULL UNIQUE
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS despesas (
			id INT AUTO_INCREMENT PRIMARY KEY,
			mes VARCHAR(50) NOT NULL,
			nome VARCHAR(255) NOT NULL,
			valor DOUBLE NOT NULL,
			categoria VARCHAR(255) NOT NULL,
			pago TINYINT(1) NOT NULL DEFAULT 0
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS dividas (
			id INT AUTO_INCREMENT PRIMARY KEY,
			nome VARCHAR(255) NOT NULL UNIQUE,
			inicial DOUBLE NOT NULL,
			total DOUBLE NOT NULL,
			taxa DOUBLE NOT NULL,
			prestacao DOUBLE NOT NULL
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS pendentes (
			id INT AUTO_INCREMENT PRIMARY KEY,
			nome VARCHAR(255) NOT NULL UNIQUE,
			valor_mensal DOUBLE NOT NULL,
			desde VARCHAR(255) NOT NULL,
			notas TEXT
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS despesas_fixas (
			id INT AUTO_INCREMENT PRIMARY KEY,
			nome VARCHAR(255) NOT NULL UNIQUE,
			valor DOUBLE NOT NULL,
			categoria VARCHAR(255) NOT NULL
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS metas (
			id INT AUTO_INCREMENT PRIMARY KEY,
			nome VARCHAR(255) NOT NULL,
			tipo VARCHAR(255) NOT NULL,
			alvo DOUBLE NOT NULL
		)
	""")

	cur.execute("""
		INSERT IGNORE INTO config (user_id, `key`, value)
		VALUES (1, 'mes_atual', %s)
	""", (json.dumps(datetime.now().strftime("%Y-%m")),))

	cur.execute("""
		INSERT IGNORE INTO config (user_id, `key`, value)
		VALUES (1, 'saldo_inicial', %s)
	""", (json.dumps(0.0),))

	conn.commit()
	conn.close()
	

# ---------------- USERS ----------------

def ensure_default_admin(username, password):
	init_db()
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("SELECT id FROM users LIMIT 1")
	if not cur.fetchone():
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

	cur.execute("SELECT * FROM users WHERE username = %s", (username,))
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
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("SELECT id, username, is_admin FROM users ORDER BY username")
	rows = cur.fetchall()

	conn.close()
	return rows


def add_user(username, password, is_admin=False):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute(
		"INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)",
		(username, generate_password_hash(password), 1 if is_admin else 0)
	)

	conn.commit()
	conn.close()


def delete_user(username):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("DELETE FROM users WHERE username = %s", (username,))

	conn.commit()
	conn.close()


# ---------------- CONFIG ----------------

def set_config(user_id, key, value):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO config (user_id, `key`, value)
		VALUES (%s, %s, %s)
		ON DUPLICATE KEY UPDATE value = VALUES(value)
	""", (int(user_id), key, json.dumps(value)))

	conn.commit()
	conn.close()


def get_config(user_id, key, default=None):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		SELECT value
		FROM config
		WHERE user_id = %s AND `key` = %s
	""", (int(user_id), key))
	row = cur.fetchone()

	conn.close()

	if not row:
		return default

	try:
		return json.loads(row["value"])
	except Exception:
		return default


def update_config_db(user_id, mes_atual, saldo_inicial):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO config (user_id, `key`, value)
		VALUES (%s, 'mes_atual', %s)
		ON DUPLICATE KEY UPDATE value = VALUES(value)
	""", (int(user_id), json.dumps(mes_atual)))

	cur.execute("""
		INSERT INTO config (user_id, `key`, value)
		VALUES (%s, 'saldo_inicial', %s)
		ON DUPLICATE KEY UPDATE value = VALUES(value)
	""", (int(user_id), json.dumps(float(saldo_inicial))))

	conn.commit()
	conn.close()


# ---------------- EXPORT ----------------

def export_to_dict(user_id):
	conn = get_connection()
	cur = conn.cursor()

	dados = {}

	dados["mes_atual"] = get_config(user_id, "mes_atual", "")
	dados["saldo_inicial"] = get_config(user_id, "saldo_inicial", 0.0)

	cur.execute("SELECT nome, valor FROM salarios WHERE user_id = %s", (int(user_id),))
	dados["salarios"] = {r["nome"]: r["valor"] for r in cur.fetchall()}

	cur.execute("SELECT nome, valor FROM contribuicoes WHERE user_id = %s", (int(user_id),))
	dados["contribuicoes"] = {r["nome"]: r["valor"] for r in cur.fetchall()}

	cur.execute("SELECT nome FROM categorias WHERE user_id = %s", (int(user_id),))
	dados["categorias"] = [r["nome"] for r in cur.fetchall()]

	cur.execute("SELECT nome, inicial, total, taxa, prestacao FROM dividas WHERE user_id = %s", (int(user_id),))
	dados["dividas"] = {
		r["nome"]: {
			"inicial": r["inicial"],
			"total": r["total"],
			"taxa": r["taxa"],
			"prestacao": r["prestacao"],
		}
		for r in cur.fetchall()
	}

	cur.execute("SELECT nome, valor_mensal, desde, notas FROM pendentes WHERE user_id = %s", (int(user_id),))
	dados["pendentes"] = {
		r["nome"]: {
			"valor_mensal": r["valor_mensal"],
			"desde": r["desde"],
			"notas": r["notas"],
		}
		for r in cur.fetchall()
	}

	cur.execute("SELECT nome, valor, categoria FROM despesas_fixas WHERE user_id = %s", (int(user_id),))
	dados["despesas_fixas"] = {
		r["nome"]: {
			"valor": r["valor"],
			"categoria": r["categoria"],
		}
		for r in cur.fetchall()
	}

	cur.execute("SELECT id, nome, tipo, alvo FROM metas WHERE user_id = %s", (int(user_id),))
	dados["metas"] = list(cur.fetchall())

	dados["meses"] = {}
	cur.execute("SELECT mes, nome, valor, categoria, pago FROM despesas WHERE user_id = %s", (int(user_id),))

	for r in cur.fetchall():
		mes = r["mes"]
		dados.setdefault("meses", {}).setdefault(mes, {"despesas": {}})
		dados["meses"][mes]["despesas"][r["nome"]] = {
			"valor": r["valor"],
			"categoria": r["categoria"],
			"pago": bool(r["pago"]),
		}

	conn.close()
	return dados
		

# ---------------- DESPESAS (SQL DIRETO) ----------------

def add_meta_db(user_id, nome, tipo, alvo):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO metas (user_id, nome, tipo, alvo)
        VALUES (%s, %s, %s, %s)
    """, (int(user_id), nome, tipo, float(alvo)))

    conn.commit()
    conn.close()


def update_meta_db(user_id, meta_id, nome, tipo, alvo):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE metas
        SET nome = %s, tipo = %s, alvo = %s
        WHERE user_id = %s AND id = %s
    """, (nome, tipo, float(alvo), int(user_id), int(meta_id)))

    conn.commit()
    conn.close()


def delete_meta_db(user_id, meta_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM metas
        WHERE user_id = %s AND id = %s
    """, (int(user_id), int(meta_id)))

    conn.commit()
    conn.close()

# ---------------- SALARIOS (SQL DIRETO) ----------------

def add_salario(user_id, nome, valor):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO salarios (user_id, nome, valor)
		VALUES (%s, %s, %s)
	""", (int(user_id), nome, float(valor)))

	conn.commit()
	conn.close()


def update_salario(user_id, nome_antigo, novo_nome, valor):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		UPDATE salarios
		SET nome = %s, valor = %s
		WHERE user_id = %s AND nome = %s
	""", (novo_nome, float(valor), int(user_id), nome_antigo))

	conn.commit()
	conn.close()


def delete_salario_db(user_id, nome):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		DELETE FROM salarios
		WHERE user_id = %s AND nome = %s
	""", (int(user_id), nome))

	conn.commit()
	conn.close()


# ---------------- CONTRIBUICOES (SQL DIRETO) ----------------

def add_contribuicao_db(user_id, nome, valor):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO contribuicoes (user_id, nome, valor)
		VALUES (%s, %s, %s)
	""", (int(user_id), nome, float(valor)))

	conn.commit()
	conn.close()


def update_contribuicao_db(user_id, nome_antigo, novo_nome, valor):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		UPDATE contribuicoes
		SET nome = %s, valor = %s
		WHERE user_id = %s AND nome = %s
	""", (novo_nome, float(valor), int(user_id), nome_antigo))

	conn.commit()
	conn.close()


def delete_contribuicao_db(user_id, nome):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		DELETE FROM contribuicoes
		WHERE user_id = %s AND nome = %s
	""", (int(user_id), nome))

	conn.commit()
	conn.close()
	
# ---------------- CATEGORIAS (SQL DIRETO) ----------------

def add_categoria_db(user_id, nome):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO categorias (user_id, nome)
		VALUES (%s, %s)
	""", (int(user_id), nome))

	conn.commit()
	conn.close()


def delete_categoria_db(user_id, nome):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		DELETE FROM categorias
		WHERE user_id = %s AND nome = %s
	""", (int(user_id), nome))

	conn.commit()
	conn.close()
	
# ---------------- DIVIDAS (SQL DIRETO) ----------------

def add_divida_db(user_id, nome, inicial, taxa, prestacao):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO dividas (user_id, nome, inicial, total, taxa, prestacao)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        int(user_id),
        nome,
        float(inicial),
        float(inicial),
        float(taxa),
        float(prestacao),
    ))

    conn.commit()
    conn.close()


def update_divida_db(user_id, nome_antigo, inicial, total, taxa, prestacao):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE dividas
        SET inicial = %s, total = %s, taxa = %s, prestacao = %s
        WHERE user_id = %s AND nome = %s
    """, (
        float(inicial),
        float(total),
        float(taxa),
        float(prestacao),
        int(user_id),
        nome_antigo,
    ))

    conn.commit()
    conn.close()


def delete_divida_db(user_id, nome):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM dividas
        WHERE user_id = %s AND nome = %s
    """, (int(user_id), nome))

    conn.commit()
    conn.close()
	
# ---------------- PENDENTES (SQL DIRETO) ----------------

def add_pendente_db(user_id, nome, valor_mensal, desde, notas):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO pendentes (user_id, nome, valor_mensal, desde, notas)
        VALUES (%s, %s, %s, %s, %s)
    """, (int(user_id), nome, float(valor_mensal), desde, notas))

    conn.commit()
    conn.close()


def update_pendente_db(user_id, nome_antigo, novo_nome, valor_mensal, desde, notas):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE pendentes
        SET nome = %s, valor_mensal = %s, desde = %s, notas = %s
        WHERE user_id = %s AND nome = %s
    """, (novo_nome, float(valor_mensal), desde, notas, int(user_id), nome_antigo))

    conn.commit()
    conn.close()


def delete_pendente_db(user_id, nome):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM pendentes
        WHERE user_id = %s AND nome = %s
    """, (int(user_id), nome))

    conn.commit()
    conn.close()


def convert_pendente_to_divida_db(user_id, nome, total, novo_nome_divida=None):
    conn = get_connection()
    cur = conn.cursor()

    nome_divida = novo_nome_divida or nome

    try:
        cur.execute("""
            INSERT INTO dividas (user_id, nome, inicial, total, taxa, prestacao)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (int(user_id), nome_divida, float(total), float(total), 0.0, 0.0))

        cur.execute("""
            DELETE FROM pendentes
            WHERE user_id = %s AND nome = %s
        """, (int(user_id), nome))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ---------------- METAS (SQL DIRETO) ----------------

def add_meta_db(nome, tipo, alvo):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO metas (nome, tipo, alvo)
		VALUES (%s, %s, %s)
	""", (nome, tipo, float(alvo)))

	conn.commit()
	conn.close()


def update_meta_db(meta_id, nome, tipo, alvo):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		UPDATE metas
		SET nome = %s, tipo = %s, alvo = %s
		WHERE id = %s
	""", (nome, tipo, float(alvo), int(meta_id)))

	conn.commit()
	conn.close()


def delete_meta_db(meta_id):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		DELETE FROM metas
		WHERE id = %s
	""", (int(meta_id),))

	conn.commit()
	conn.close()
	
# ---------------- CONFIG (SQL DIRETO) ----------------

def update_config_db(mes_atual, saldo_inicial):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO config (`key`, value)
		VALUES ('mes_atual', %s)
		ON DUPLICATE KEY UPDATE value = %s
	""", (json.dumps(mes_atual), json.dumps(mes_atual)))

	cur.execute("""
		INSERT INTO config (`key`, value)
		VALUES ('saldo_inicial', %s)
		ON DUPLICATE KEY UPDATE value = %s
	""", (json.dumps(float(saldo_inicial)), json.dumps(float(saldo_inicial))))

	conn.commit()
	conn.close()
	
