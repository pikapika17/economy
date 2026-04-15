import json
import os
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

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
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


# ---------------- USERS ----------------

def ensure_default_admin(username, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users LIMIT 1")
    existe = cur.fetchone()

    if not existe:
        cur.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, 1)",
            (username, generate_password_hash(password))
        )

    conn.close()


def get_user_by_username(username):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, username, password_hash, is_admin FROM users WHERE username = %s",
        (username,)
    )

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

    conn.close()


def delete_user(username):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE username = %s", (username,))

    conn.close()


# ---------------- CONFIG ----------------

def set_config(key, value):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO config (`key`, value)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE value = VALUES(value)
    """, (key, json.dumps(value)))

    conn.close()


def get_config(key, default=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT value FROM config WHERE `key` = %s", (key,))
    row = cur.fetchone()

    conn.close()

    if not row:
        return default

    try:
        return json.loads(row["value"])
    except Exception:
        return default


# ---------------- EXPORT ----------------

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

def init_db():
    pass

def save_all_from_dict(dados):
    pass