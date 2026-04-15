import json
import os
import secrets
import string
from datetime import datetime, timedelta
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
			email VARCHAR(255) NOT NULL UNIQUE,
			first_name VARCHAR(255) NOT NULL DEFAULT '',
			last_name VARCHAR(255) NOT NULL DEFAULT '',
			birth_date DATE NULL,
			country VARCHAR(255) NOT NULL DEFAULT '',
			password_hash TEXT NOT NULL,
			is_admin TINYINT(1) NOT NULL DEFAULT 0
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS password_resets (
			id INT AUTO_INCREMENT PRIMARY KEY,
			user_id INT NOT NULL,
			token VARCHAR(255) NOT NULL UNIQUE,
			expires_at DATETIME NOT NULL,
			used TINYINT(1) NOT NULL DEFAULT 0
		)
	""")

	cur.execute("""
		CREATE TABLE IF NOT EXISTS invite_codes (
			id INT AUTO_INCREMENT PRIMARY KEY,
			code VARCHAR(255) NOT NULL UNIQUE,
			is_active TINYINT(1) NOT NULL DEFAULT 1,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	""")	

	cur.execute("""
		CREATE TABLE IF NOT EXISTS config (
			user_id INT NOT NULL,
			`key` VARCHAR(255) NOT NULL,
			value TEXT,
			PRIMARY KEY (user_id, `key`)
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

	mes_atual_default = datetime.now().strftime("%Y-%m")

	cur.execute("""
		INSERT IGNORE INTO config (user_id, `key`, value)
		VALUES (1, 'mes_atual', %s)
	""", (json.dumps(mes_atual_default),))

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


def add_user(username, email, password, is_admin=False, first_name="", last_name="", birth_date=None, country=""):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (
            username, email, first_name, last_name, birth_date, country, password_hash, is_admin
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        username,
        email,
        first_name,
        last_name,
        birth_date if birth_date else None,
        country,
        generate_password_hash(password),
        1 if is_admin else 0
    ))

    conn.commit()
    conn.close()
	

def get_display_name(user):
    first_name = (user.get("first_name") or "").strip()
    last_name = (user.get("last_name") or "").strip()

    full_name = f"{first_name} {last_name}".strip()
    return full_name if full_name else user["username"]


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

def add_despesa(user_id, mes, nome, valor, categoria, pago=0):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO despesas (user_id, mes, nome, valor, categoria, pago)
		VALUES (%s, %s, %s, %s, %s, %s)
	""", (int(user_id), mes, nome, float(valor), categoria, int(pago)))

	conn.commit()
	conn.close()


def delete_despesa(user_id, mes, nome):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		DELETE FROM despesas
		WHERE user_id = %s AND mes = %s AND nome = %s
	""", (int(user_id), mes, nome))

	conn.commit()
	conn.close()


def update_despesa_pago(user_id, mes, nome, pago):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		UPDATE despesas
		SET pago = %s
		WHERE user_id = %s AND mes = %s AND nome = %s
	""", (int(pago), int(user_id), mes, nome))

	conn.commit()
	conn.close()


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
	
def ensure_user_defaults(user_id):
	conn = get_connection()
	cur = conn.cursor()

	mes_atual_default = datetime.now().strftime("%Y-%m")

	cur.execute("""
		INSERT IGNORE INTO config (user_id, `key`, value)
		VALUES (%s, 'mes_atual', %s)
	""", (int(user_id), json.dumps(mes_atual_default)))

	cur.execute("""
		INSERT IGNORE INTO config (user_id, `key`, value)
		VALUES (%s, 'saldo_inicial', %s)
	""", (int(user_id), json.dumps(0.0)))

	conn.commit()
	conn.close()


# ---------------- INVITE CODES ----------------

def create_invite_code(code):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		INSERT INTO invite_codes (code, is_active)
		VALUES (%s, 1)
	""", (code,))

	conn.commit()
	conn.close()


def invite_code_exists(code):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		SELECT id, code, is_active
		FROM invite_codes
		WHERE code = %s AND is_active = 1
	""", (code,))

	row = cur.fetchone()
	conn.close()
	return row


def use_invite_code(code):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		UPDATE invite_codes
		SET is_active = 0
		WHERE code = %s
	""", (code,))

	conn.commit()
	conn.close()


def list_invite_codes():
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		SELECT id, code, is_active, created_at
		FROM invite_codes
		ORDER BY id DESC
	""")

	rows = cur.fetchall()
	conn.close()
	return rows


def delete_invite_code(code):
	conn = get_connection()
	cur = conn.cursor()

	cur.execute("""
		DELETE FROM invite_codes
		WHERE code = %s
	""", (code,))

	conn.commit()
	conn.close()


def generate_invite_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_random_invite_code(length=10):
    while True:
        code = generate_invite_code(length)
        if not invite_code_exists_any(code):
            create_invite_code(code)
            return code
		

def invite_code_exists_any(code):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM invite_codes
        WHERE code = %s
    """, (code,))

    row = cur.fetchone()
    conn.close()
    return row


def generate_invite_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_random_invite_code(length=10):
    while True:
        code = generate_invite_code(length)
        if not invite_code_exists_any(code):
            create_invite_code(code)
            return code


def create_multiple_invite_codes(quantity=5, length=10):
    codes = []

    for _ in range(int(quantity)):
        code = create_random_invite_code(length)
        codes.append(code)

    return codes


# ---------------- ADMIN USERS ----------------

def set_user_admin(username, is_admin):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET is_admin = %s
        WHERE username = %s
    """, (1 if is_admin else 0, username))

    conn.commit()
    conn.close()


def update_user_password(username, new_password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET password_hash = %s
        WHERE username = %s
    """, (generate_password_hash(new_password), username))

    conn.commit()
    conn.close()


# ---------------- ADMIN DASHBOARD ----------------

def get_admin_stats():
    conn = get_connection()
    cur = conn.cursor()

    stats = {}

    cur.execute("SELECT COUNT(*) AS total FROM users")
    stats["total_users"] = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM users WHERE is_admin = 1")
    stats["total_admins"] = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM invite_codes")
    stats["total_invites"] = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM invite_codes WHERE is_active = 1")
    stats["active_invites"] = cur.fetchone()["total"]

    conn.close()
    return stats


def get_latest_users(limit=5):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, username, is_admin
        FROM users
        ORDER BY id DESC
        LIMIT %s
    """, (int(limit),))

    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    row = cur.fetchone()

    conn.close()
    return row


def get_user_by_username_or_email(identifier):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE username = %s OR email = %s
        LIMIT 1
    """, (identifier, identifier))
    row = cur.fetchone()

    conn.close()
    return row


def authenticate_user(identifier, password):
    user = get_user_by_username_or_email(identifier)

    if not user:
        return None

    if check_password_hash(user["password_hash"], password):
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": bool(user["is_admin"])
        }

    return None


def create_password_reset_token(email):
    user = get_user_by_email(email)
    if not user:
        return None

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=1)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO password_resets (user_id, token, expires_at, used)
        VALUES (%s, %s, %s, 0)
    """, (int(user["id"]), token, expires_at.strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

    return token


def get_valid_password_reset(token):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT pr.*, u.username, u.email
        FROM password_resets pr
        JOIN users u ON u.id = pr.user_id
        WHERE pr.token = %s
          AND pr.used = 0
          AND pr.expires_at >= NOW()
        LIMIT 1
    """, (token,))

    row = cur.fetchone()
    conn.close()
    return row


def mark_password_reset_used(token):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE password_resets
        SET used = 1
        WHERE token = %s
    """, (token,))

    conn.commit()
    conn.close()


def update_user_password_by_id(user_id, new_password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET password_hash = %s
        WHERE id = %s
    """, (generate_password_hash(new_password), int(user_id)))

    conn.commit()
    conn.close()