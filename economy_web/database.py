import json
import os
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
        autocommit=False,  # 🔥 FIX: transações controladas
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

    cur.execute("SELECT nome, valor FROM salarios")
    dados["salarios"] = {r["nome"]: r["valor"] for r in cur.fetchall()}

    cur.execute("SELECT nome, valor FROM contribuicoes")
    dados["contribuicoes"] = {r["nome"]: r["valor"] for r in cur.fetchall()}

    cur.execute("SELECT nome FROM categorias")
    dados["categorias"] = [r["nome"] for r in cur.fetchall()]

    cur.execute("SELECT nome, inicial, total, taxa, prestacao FROM dividas")
    dados["dividas"] = {
        r["nome"]: {
            "inicial": r["inicial"],
            "total": r["total"],
            "taxa": r["taxa"],
            "prestacao": r["prestacao"],
        }
        for r in cur.fetchall()
    }

    cur.execute("SELECT nome, valor_mensal, desde, notas FROM pendentes")
    dados["pendentes"] = {
        r["nome"]: {
            "valor_mensal": r["valor_mensal"],
            "desde": r["desde"],
            "notas": r["notas"],
        }
        for r in cur.fetchall()
    }

    cur.execute("SELECT nome, valor, categoria FROM despesas_fixas")
    dados["despesas_fixas"] = {
        r["nome"]: {
            "valor": r["valor"],
            "categoria": r["categoria"],
        }
        for r in cur.fetchall()
    }

    cur.execute("SELECT nome, tipo, alvo FROM metas")
    dados["metas"] = list(cur.fetchall())

    dados["meses"] = {}
    cur.execute("SELECT mes, nome, valor, categoria, pago FROM despesas")

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


# ---------------- SAVE ----------------

def save_all_from_dict(dados):
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    try:
        for table in [
            "config","salarios","contribuicoes","categorias",
            "despesas","dividas","pendentes","despesas_fixas","metas"
        ]:
            cur.execute(f"DELETE FROM {table}")

        set_config("mes_atual", dados.get("mes_atual", ""))
        set_config("saldo_inicial", dados.get("saldo_inicial", 0.0))

        for nome, v in dados.get("salarios", {}).items():
            cur.execute("INSERT INTO salarios (nome, valor) VALUES (%s, %s)", (nome, v))

        for nome, v in dados.get("contribuicoes", {}).items():
            cur.execute("INSERT INTO contribuicoes (nome, valor) VALUES (%s, %s)", (nome, v))

        for nome in dados.get("categorias", []):
            cur.execute("INSERT INTO categorias (nome) VALUES (%s)", (nome,))

        for mes, info in dados.get("meses", {}).items():
            for nome, d in info.get("despesas", {}).items():
                cur.execute(
                    "INSERT INTO despesas (mes,nome,valor,categoria,pago) VALUES (%s,%s,%s,%s,%s)",
                    (mes, nome, d["valor"], d["categoria"], int(d.get("pago", False)))
                )

        for nome, d in dados.get("dividas", {}).items():
            cur.execute(
                "INSERT INTO dividas (nome,inicial,total,taxa,prestacao) VALUES (%s,%s,%s,%s,%s)",
                (nome, d["inicial"], d["total"], d["taxa"], d["prestacao"])
            )

        for nome, d in dados.get("pendentes", {}).items():
            cur.execute(
                "INSERT INTO pendentes (nome,valor_mensal,desde,notas) VALUES (%s,%s,%s,%s)",
                (nome, d["valor_mensal"], d["desde"], d["notas"])
            )

        for nome, d in dados.get("despesas_fixas", {}).items():
            cur.execute(
                "INSERT INTO despesas_fixas (nome,valor,categoria) VALUES (%s,%s,%s)",
                (nome, d["valor"], d["categoria"])
            )

        for m in dados.get("metas", []):
            cur.execute(
                "INSERT INTO metas (nome,tipo,alvo) VALUES (%s,%s,%s)",
                (m["nome"], m["tipo"], m["alvo"])
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()