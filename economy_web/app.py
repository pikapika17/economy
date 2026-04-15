from flask import Flask, render_template, request, redirect, session, url_for, flash
from functools import wraps

import os

from database import (
    init_db,
    ensure_default_admin,
    authenticate_user,
    list_users,
    add_user,
    get_user_by_username,
    delete_user,
    export_to_dict,
    save_all_from_dict,
    add_despesa as db_add_despesa,
    delete_despesa as db_delete_despesa,
    update_despesa_pago as db_update_despesa_pago,
    add_salario as db_add_salario,
    update_salario as db_update_salario,
    delete_salario_db,
    add_contribuicao_db,
    update_contribuicao_db,
    delete_contribuicao_db,
    add_categoria_db,
    delete_categoria_db,
    add_divida_db,
    update_divida_db,
    delete_divida_db,
    add_pendente_db,
    update_pendente_db,
    delete_pendente_db,
    convert_pendente_to_divida_db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "muda_isto_agora")

APP_USER = os.environ.get("APP_USER", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "admin123")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))

        if not session.get("is_admin"):
            flash("Apenas administradores podem aceder a esta área.", "warning")
            return redirect(url_for("dashboard"))

        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_user_context():
    return {
        "session_user": session.get("user"),
        "session_is_admin": bool(session.get("is_admin", False))
    }


def calcular_info_divida_web(divida):
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

def calcular_meses_pendentes_web(desde, ate):
    try:
        ano_inicio, mes_inicio = map(int, desde.split("-"))
        ano_fim, mes_fim = map(int, ate.split("-"))
    except Exception:
        return 0

    total = (ano_fim - ano_inicio) * 12 + (mes_fim - mes_inicio) + 1
    return max(0, total)


def validar_mes_web(texto):
    try:
        ano, mes = map(int, texto.split("-"))
        return ano > 2000 and 1 <= mes <= 12
    except Exception:
        return False
    
def calcular_sobra_web(dados, mes):
    entradas = sum(dados.get("salarios", {}).values()) + sum(dados.get("contribuicoes", {}).values())

    despesas = 0
    for d in dados.get("meses", {}).get(mes, {}).get("despesas", {}).values():
        despesas += d["valor"] if isinstance(d, dict) else d

    prestacoes = sum(d["prestacao"] for d in dados.get("dividas", {}).values())
    sobra = entradas - despesas - prestacoes

    return entradas, despesas, prestacoes, sobra


def total_pendentes_web(dados):
    mes_atual = dados.get("mes_atual", "")
    total = 0.0

    for _, p in dados.get("pendentes", {}).items():
        valor_mensal = float(p.get("valor_mensal", 0))
        desde = p.get("desde", "")
        meses = calcular_meses_pendentes_web(desde, mes_atual)
        total += valor_mensal * meses

    return total


def score_web(dados, mes):
    entradas, despesas, prestacoes, sobra = calcular_sobra_web(dados, mes)
    dividas = dados.get("dividas", {})
    total_divida = sum(d["total"] for d in dividas.values())

    score = 0
    detalhes = []

    if sobra > 1000:
        score += 40
        detalhes.append("Boa sobra mensal")
    elif sobra > 500:
        score += 30
        detalhes.append("Sobra positiva forte")
    elif sobra > 0:
        score += 15
        detalhes.append("Sobra positiva")
    else:
        detalhes.append("Sobra mensal negativa")

    if entradas > 0:
        ratio = despesas / entradas
        if ratio < 0.5:
            score += 20
            detalhes.append("Despesas controladas")
        elif ratio < 0.7:
            score += 10
            detalhes.append("Despesas aceitáveis")
        else:
            detalhes.append("Despesas pesadas")

    if entradas > 0:
        ratio_div = total_divida / (entradas * 12)
        if ratio_div < 1:
            score += 20
            detalhes.append("Dívida baixa face ao rendimento")
        elif ratio_div < 2:
            score += 10
            detalhes.append("Dívida moderada")
        else:
            detalhes.append("Dívida elevada")

    if dividas:
        max_taxa = max(d["taxa"] for d in dividas.values())
        if max_taxa < 5:
            score += 20
            detalhes.append("Juros baixos")
        elif max_taxa < 10:
            score += 10
            detalhes.append("Juros moderados")
        else:
            detalhes.append("Juros altos")

    return score, detalhes


def simular_dividas_web(dados, extra=0):
    dividas = {
        nome: {
            "total": float(info["total"]),
            "taxa": float(info["taxa"]),
            "prestacao": float(info["prestacao"])
        }
        for nome, info in dados.get("dividas", {}).items()
    }

    if not dividas:
        return {
            "meses": 0,
            "juros": 0,
            "problema": False,
            "historico": [],
            "prioridade": "Sem dívidas"
        }

    historico = []
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

        prioritaria = max(ativas.items(), key=lambda x: x[1]["taxa"])[0]

        total_restante = 0.0
        snapshot = {"mes": meses, "itens": []}

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

            total_restante += d["total"]
            snapshot["itens"].append({
                "nome": nome,
                "restante": d["total"]
            })

        snapshot["total_restante"] = total_restante
        historico.append(snapshot)

    prioridade = max(dados.get("dividas", {}).items(), key=lambda x: x[1]["taxa"])[0] if dados.get("dividas") else "Sem dívidas"

    return {
        "meses": meses,
        "juros": juros_totais,
        "problema": problema,
        "historico": historico,
        "prioridade": prioridade
    }

def resposta_ok(texto, tipo="success"):
    return {"texto": texto, "tipo": tipo}
    

@app.route("/")
@login_required
def dashboard():
    dados = export_to_dict()
    mes = dados["mes_atual"]

    entradas = sum(dados["salarios"].values()) + sum(dados["contribuicoes"].values())

    despesas = sum(
        d["valor"] if isinstance(d, dict) else d
        for d in dados["meses"].get(mes, {}).get("despesas", {}).values()
    )

    dividas = sum(d["prestacao"] for d in dados["dividas"].values())
    pendentes = sum(p["valor_mensal"] for p in dados["pendentes"].values())

    saldo_inicial = float(dados.get("saldo_inicial", 0))
    sobra = entradas - despesas - dividas
    saldo_real = saldo_inicial + sobra

    return render_template("dashboard.html",
        entradas=entradas,
        despesas=despesas,
        dividas=dividas,
        pendentes=pendentes,
        saldo=saldo_real
    )


# =========================
# DESPESAS
# =========================
@app.route("/despesas")
@login_required
def despesas():
    dados = export_to_dict()
    mes = dados.get("mes_atual", "")

    if "meses" not in dados:
        dados["meses"] = {}

    if mes not in dados["meses"]:
        dados["meses"][mes] = {"despesas": {}}

    despesas_dict = dados["meses"][mes]["despesas"]
    categorias = sorted(dados.get("categorias", []))

    pesquisa = request.args.get("pesquisa", "").strip().lower()
    categoria = request.args.get("categoria", "").strip()
    estado = request.args.get("estado", "").strip()

    despesas_filtradas = {}

    for nome, d in despesas_dict.items():
        nome_match = pesquisa in nome.lower() if pesquisa else True
        categoria_match = (not categoria or categoria == "Todas" or d.get("categoria", "") == categoria)

        pago = d.get("pago", False)
        if estado == "Pagas":
            estado_match = pago
        elif estado == "Por pagar":
            estado_match = not pago
        else:
            estado_match = True

        if nome_match and categoria_match and estado_match:
            despesas_filtradas[nome] = d

    return render_template(
        "despesas.html",
        despesas=despesas_filtradas,
        categorias=categorias,
        filtros={
            "pesquisa": request.args.get("pesquisa", ""),
            "categoria": request.args.get("categoria", "Todas"),
            "estado": request.args.get("estado", "Todas")
        }
    )


@app.route("/add_despesa", methods=["POST"])
@login_required
def add_despesa():
    dados = export_to_dict()
    mes = dados.get("mes_atual", "")

    nome = request.form.get("nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()
    categoria = request.form.get("categoria", "").strip()

    if not nome or not valor_txt or not categoria or not mes:
        flash("Faltam dados para guardar a despesa.", "error")
        return redirect("/despesas")

    try:
        valor = float(valor_txt)
        db_add_despesa(mes, nome, valor, categoria, 0)
        flash("Despesa adicionada com sucesso.", "success")
    except Exception as e:
        app.logger.exception("Erro ao adicionar despesa")
        flash(f"Erro ao adicionar despesa: {e}", "error")

    return redirect("/despesas")


@app.route("/delete_despesa/<nome>")
@login_required
def delete_despesa(nome):
    dados = export_to_dict()
    mes = dados.get("mes_atual", "")

    if not mes:
        flash("Mês atual inválido.", "error")
        return redirect("/despesas")

    try:
        db_delete_despesa(mes, nome)
        flash("Despesa removida.", "warning")
    except Exception as e:
        app.logger.exception("Erro ao apagar despesa")
        flash(f"Erro ao remover despesa: {e}", "error")

    return redirect("/despesas")


@app.route("/toggle_pago/<nome>")
@login_required
def toggle_pago(nome):
    dados = export_to_dict()
    mes = dados.get("mes_atual", "")

    if not mes:
        flash("Mês atual inválido.", "error")
        return redirect("/despesas")

    despesas_mes = dados.get("meses", {}).get(mes, {}).get("despesas", {})
    if nome not in despesas_mes:
        flash("Despesa não encontrada.", "error")
        return redirect("/despesas")

    pago_atual = despesas_mes[nome].get("pago", False)

    try:
        db_update_despesa_pago(mes, nome, not pago_atual)
        flash("Estado da despesa atualizado.", "success")
    except Exception as e:
        app.logger.exception("Erro ao atualizar estado da despesa")
        flash(f"Erro ao atualizar estado da despesa: {e}", "error")

    return redirect("/despesas")

@app.route("/dividas")
@login_required
def dividas():
    dados = export_to_dict()
    dividas_dict = dados.get("dividas", {})

    dividas_lista = []
    for nome, d in dividas_dict.items():
        item = {
            "nome": nome,
            "inicial": float(d.get("inicial", d.get("total", 0))),
            "total": float(d.get("total", 0)),
            "taxa": float(d.get("taxa", 0)),
            "prestacao": float(d.get("prestacao", 0)),
        }
        item["info"] = calcular_info_divida_web(item)
        dividas_lista.append(item)

    return render_template("dividas.html", dividas=dividas_lista)


@app.route("/add_divida", methods=["POST"])
@login_required
def add_divida():
    nome = request.form.get("nome", "").strip()
    inicial_txt = request.form.get("inicial", "").strip()
    taxa_txt = request.form.get("taxa", "").strip()
    prestacao_txt = request.form.get("prestacao", "").strip()

    if not nome or not inicial_txt or not taxa_txt or not prestacao_txt:
        return redirect("/dividas")

    try:
        inicial = float(inicial_txt)
        taxa = float(taxa_txt)
        prestacao = float(prestacao_txt)
        add_divida_db(nome, inicial, taxa, prestacao)
    except ValueError:
        return redirect("/dividas")
    except Exception as e:
        app.logger.exception("Erro ao adicionar dívida")
        flash(f"Erro ao adicionar dívida: {e}", "error")
        return redirect("/dividas")

    flash("Dívida adicionada com sucesso.", "success")
    return redirect("/dividas")


@app.route("/delete_divida/<nome>")
@login_required
def delete_divida(nome):
    try:
        delete_divida_db(nome)
    except Exception as e:
        app.logger.exception("Erro ao remover dívida")
        flash(f"Erro ao remover dívida: {e}", "error")
        return redirect("/dividas")

    flash("Dívida removida.", "warning")
    return redirect("/dividas")


@app.route("/update_divida/<nome>", methods=["POST"])
@login_required
def update_divida(nome):
    inicial_txt = request.form.get("inicial", "").strip()
    total_txt = request.form.get("total", "").strip()
    taxa_txt = request.form.get("taxa", "").strip()
    prestacao_txt = request.form.get("prestacao", "").strip()

    try:
        inicial = float(inicial_txt)
        total = float(total_txt)
        taxa = float(taxa_txt)
        prestacao = float(prestacao_txt)
        update_divida_db(nome, inicial, total, taxa, prestacao)
    except ValueError:
        return redirect("/dividas")
    except Exception as e:
        app.logger.exception("Erro ao atualizar dívida")
        flash(f"Erro ao atualizar dívida: {e}", "error")
        return redirect("/dividas")

    flash("Dívida atualizada com sucesso.", "success")
    return redirect("/dividas")


@app.route("/pendentes")
@login_required
def pendentes():
    dados = export_to_dict()
    mes_atual = dados.get("mes_atual", "")

    pendentes_dict = dados.get("pendentes", {})
    pendentes_lista = []

    total_geral = 0.0

    for nome, p in pendentes_dict.items():
        valor_mensal = float(p.get("valor_mensal", 0))
        desde = p.get("desde", "")
        notas = p.get("notas", "")

        meses = calcular_meses_pendentes_web(desde, mes_atual)
        total = valor_mensal * meses
        total_geral += total

        pendentes_lista.append({
            "nome": nome,
            "valor_mensal": valor_mensal,
            "desde": desde,
            "notas": notas,
            "meses": meses,
            "total": total
        })

    pendentes_lista.sort(key=lambda x: x["total"], reverse=True)

    return render_template(
        "pendentes.html",
        pendentes=pendentes_lista,
        total_geral=total_geral,
        mes_atual=mes_atual
    )

@app.route("/add_pendente", methods=["POST"])
@login_required
def add_pendente():
    nome = request.form.get("nome", "").strip()
    valor_txt = request.form.get("valor_mensal", "").strip()
    desde = request.form.get("desde", "").strip()
    notas = request.form.get("notas", "").strip()

    if not nome or not valor_txt or not desde:
        return redirect("/pendentes")

    if not validar_mes_web(desde):
        return redirect("/pendentes")

    try:
        valor_mensal = float(valor_txt)
        add_pendente_db(nome, valor_mensal, desde, notas)
    except ValueError:
        return redirect("/pendentes")
    except Exception as e:
        app.logger.exception("Erro ao adicionar pendente")
        flash(f"Erro ao adicionar pendente: {e}", "error")
        return redirect("/pendentes")

    flash("Pendente adicionado com sucesso.", "success")
    return redirect("/pendentes")


@app.route("/update_pendente/<nome>", methods=["POST"])
@login_required
def update_pendente(nome):
    novo_nome = request.form.get("novo_nome", "").strip()
    valor_txt = request.form.get("valor_mensal", "").strip()
    desde = request.form.get("desde", "").strip()
    notas = request.form.get("notas", "").strip()

    if not novo_nome or not valor_txt or not desde:
        return redirect("/pendentes")

    if not validar_mes_web(desde):
        return redirect("/pendentes")

    try:
        valor_mensal = float(valor_txt)
        update_pendente_db(nome, novo_nome, valor_mensal, desde, notas)
    except ValueError:
        return redirect("/pendentes")
    except Exception as e:
        app.logger.exception("Erro ao atualizar pendente")
        flash(f"Erro ao atualizar pendente: {e}", "error")
        return redirect("/pendentes")

    flash("Pendente atualizado com sucesso.", "success")
    return redirect("/pendentes")


@app.route("/delete_pendente/<nome>")
@login_required
def delete_pendente(nome):
    try:
        delete_pendente_db(nome)
    except Exception as e:
        app.logger.exception("Erro ao remover pendente")
        flash(f"Erro ao remover pendente: {e}", "error")
        return redirect("/pendentes")

    flash("Pendente removido.", "warning")
    return redirect("/pendentes")


@app.route("/convert_pendente/<nome>")
@login_required
def convert_pendente(nome):
    dados = export_to_dict()
    mes_atual = dados.get("mes_atual", "")

    if nome not in dados.get("pendentes", {}):
        return redirect("/pendentes")

    p = dados["pendentes"][nome]

    valor_mensal = float(p.get("valor_mensal", 0))
    desde = p.get("desde", "")
    meses = calcular_meses_pendentes_web(desde, mes_atual)
    total = valor_mensal * meses

    nome_divida = nome
    if nome_divida in dados.get("dividas", {}):
        nome_divida = f"{nome} (pendente)"

    try:
        convert_pendente_to_divida_db(nome, total, nome_divida)
    except Exception as e:
        app.logger.exception("Erro ao converter pendente")
        flash(f"Erro ao converter pendente: {e}", "error")
        return redirect("/pendentes")

    flash("Pendente convertido em dívida.", "success")
    return redirect("/pendentes")


@app.route("/sistema")
@login_required
def sistema():
    dados = export_to_dict()

    return render_template(
        "sistema.html",
        salarios=dados.get("salarios", {}),
        contribuicoes=dados.get("contribuicoes", {}),
        categorias=dados.get("categorias", []),
        saldo_inicial=float(dados.get("saldo_inicial", 0)),
        mes_atual=dados.get("mes_atual", "")
    )

@app.route("/update_config", methods=["POST"])
@login_required
def update_config():
    dados = export_to_dict()

    saldo_txt = request.form.get("saldo_inicial", "").strip()
    mes_atual = request.form.get("mes_atual", "").strip()

    try:
        saldo_inicial = float(saldo_txt)
    except ValueError:
        return redirect("/sistema")

    if not validar_mes_web(mes_atual):
        return redirect("/sistema")

    dados["saldo_inicial"] = saldo_inicial
    dados["mes_atual"] = mes_atual

    dados.setdefault("meses", {})
    if mes_atual not in dados["meses"]:
        dados["meses"][mes_atual] = {"despesas": {}}

    save_all_from_dict(dados)
    return redirect("/sistema")    

@app.route("/add_salario", methods=["POST"])
@login_required
def add_salario():
    nome = request.form.get("nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()

    if not nome or not valor_txt:
        return redirect("/sistema")

    try:
        valor = float(valor_txt)
        db_add_salario(nome, valor)
    except ValueError:
        return redirect("/sistema")
    except Exception as e:
        app.logger.exception("Erro ao adicionar salário")
        flash(f"Erro ao adicionar salário: {e}", "error")
        return redirect("/sistema")

    flash("Salário adicionado com sucesso.", "success")
    return redirect("/sistema")


@app.route("/update_salario/<nome>", methods=["POST"])
@login_required
def update_salario(nome):
    novo_nome = request.form.get("novo_nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()

    if not novo_nome or not valor_txt:
        return redirect("/sistema")

    try:
        valor = float(valor_txt)
        db_update_salario(nome, novo_nome, valor)
    except ValueError:
        return redirect("/sistema")
    except Exception as e:
        app.logger.exception("Erro ao atualizar salário")
        flash(f"Erro ao atualizar salário: {e}", "error")
        return redirect("/sistema")

    flash("Salário atualizado com sucesso.", "success")
    return redirect("/sistema")


@app.route("/delete_salario/<nome>")
@login_required
def delete_salario(nome):
    try:
        delete_salario_db(nome)
    except Exception as e:
        app.logger.exception("Erro ao remover salário")
        flash(f"Erro ao remover salário: {e}", "error")
        return redirect("/sistema")

    flash("Salário removido.", "warning")
    return redirect("/sistema")


@app.route("/add_contribuicao", methods=["POST"])
@login_required
def add_contribuicao():
    nome = request.form.get("nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()

    if not nome or not valor_txt:
        return redirect("/sistema")

    try:
        valor = float(valor_txt)
        add_contribuicao_db(nome, valor)
    except ValueError:
        return redirect("/sistema")
    except Exception as e:
        app.logger.exception("Erro ao adicionar contribuição")
        flash(f"Erro ao adicionar contribuição: {e}", "error")
        return redirect("/sistema")

    flash("Contribuição adicionada com sucesso.", "success")
    return redirect("/sistema")


@app.route("/update_contribuicao/<nome>", methods=["POST"])
@login_required
def update_contribuicao(nome):
    novo_nome = request.form.get("novo_nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()

    if not novo_nome or not valor_txt:
        return redirect("/sistema")

    try:
        valor = float(valor_txt)
        update_contribuicao_db(nome, novo_nome, valor)
    except ValueError:
        return redirect("/sistema")
    except Exception as e:
        app.logger.exception("Erro ao atualizar contribuição")
        flash(f"Erro ao atualizar contribuição: {e}", "error")
        return redirect("/sistema")

    flash("Contribuição atualizada com sucesso.", "success")
    return redirect("/sistema")


@app.route("/delete_contribuicao/<nome>")
@login_required
def delete_contribuicao(nome):
    try:
        delete_contribuicao_db(nome)
    except Exception as e:
        app.logger.exception("Erro ao remover contribuição")
        flash(f"Erro ao remover contribuição: {e}", "error")
        return redirect("/sistema")

    flash("Contribuição removida.", "warning")
    return redirect("/sistema")


@app.route("/add_categoria", methods=["POST"])
@login_required
def add_categoria():
    nome = request.form.get("nome", "").strip()

    if not nome:
        return redirect("/sistema")

    try:
        add_categoria_db(nome)
    except Exception as e:
        app.logger.exception("Erro ao adicionar categoria")
        flash(f"Erro ao adicionar categoria: {e}", "error")
        return redirect("/sistema")

    flash("Categoria adicionada com sucesso.", "success")
    return redirect("/sistema")


@app.route("/delete_categoria/<nome>")
@login_required
def delete_categoria(nome):
    try:
        delete_categoria_db(nome)
    except Exception as e:
        app.logger.exception("Erro ao remover categoria")
        flash(f"Erro ao remover categoria: {e}", "error")
        return redirect("/sistema")

    flash("Categoria removida.", "warning")
    return redirect("/sistema")


@app.route("/planeamento")
@login_required
def planeamento():
    dados = export_to_dict()
    mes = dados.get("mes_atual", "")

    entradas, despesas, prestacoes, sobra = calcular_sobra_web(dados, mes)
    saldo_inicial = float(dados.get("saldo_inicial", 0))
    saldo_real = saldo_inicial + sobra
    pendentes = total_pendentes_web(dados)

    total_divida = sum(d["total"] for d in dados.get("dividas", {}).values())
    score, detalhes = score_web(dados, mes)

    if total_divida <= 0:
        meses_liberdade = 0
    elif sobra <= 0:
        meses_liberdade = "∞"
    else:
        meses_liberdade = int(total_divida / sobra)

    prioridade = "Sem dívidas"
    if dados.get("dividas"):
        pior = max(dados["dividas"].items(), key=lambda x: x[1]["taxa"])
        prioridade = f"{pior[0]} ({pior[1]['taxa']:.2f}%)"

    return render_template(
        "planeamento.html",
        mes=mes,
        entradas=entradas,
        despesas=despesas,
        prestacoes=prestacoes,
        sobra=sobra,
        saldo_real=saldo_real,
        pendentes=pendentes,
        total_divida=total_divida,
        meses_liberdade=meses_liberdade,
        prioridade=prioridade,
        score=score,
        detalhes=detalhes
    )

@app.route("/simulacao")
@login_required
def simulacao():
    dados = export_to_dict()

    extra_txt = request.args.get("extra", "0").strip()
    try:
        extra = float(extra_txt)
    except ValueError:
        extra = 0.0

    resultado = simular_dividas_web(dados, extra)

    cenarios = []
    for valor in [0, 100, 250, 500]:
        r = simular_dividas_web(dados, valor)
        cenarios.append({
            "extra": valor,
            "meses": r["meses"],
            "juros": r["juros"],
            "problema": r["problema"]
        })

    return render_template(
        "simulacao.html",
        extra=extra,
        resultado=resultado,
        cenarios=cenarios
    )

@app.route("/timeline")
@login_required
def timeline():
    dados = export_to_dict()

    extra_txt = request.args.get("extra", "0").strip()
    modo = request.args.get("modo", "resumo").strip().lower()

    try:
        extra = float(extra_txt)
    except ValueError:
        extra = 0.0

    resultado = simular_dividas_web(dados, extra)

    historico = resultado["historico"]
    if modo != "detalhado" and historico:
        indices = [0, len(historico)//4, len(historico)//2, (3*len(historico))//4, len(historico)-1]
        vistos = set()
        resumido = []
        for i in indices:
            if i in vistos or i < 0 or i >= len(historico):
                continue
            vistos.add(i)
            resumido.append(historico[i])
        historico = resumido

    return render_template(
        "timeline.html",
        extra=extra,
        modo=modo,
        resultado=resultado,
        historico=historico
    )

@app.route("/admin/users")
@admin_required
def admin_users():
    users = list_users()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/add", methods=["POST"])
@admin_required
def admin_add_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "user").strip().lower()
    is_admin = role == "admin"

    if not username or not password:
        flash("Preenche utilizador e password.", "error")
        return redirect(url_for("admin_users"))

    if get_user_by_username(username):
        flash("Já existe um utilizador com esse nome.", "warning")
        return redirect(url_for("admin_users"))

    try:
        add_user(username, password, is_admin=is_admin)
    except Exception:
        flash("Não foi possível criar o utilizador.", "error")
        return redirect(url_for("admin_users"))

    flash("Utilizador criado com sucesso.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<username>", methods=["POST"])
@admin_required
def admin_delete_user(username):
    if username == session.get("user"):
        flash("Não podes remover o teu próprio utilizador.", "warning")
        return redirect(url_for("admin_users"))

    user = get_user_by_username(username)
    if not user:
        flash("Utilizador não encontrado.", "warning")
        return redirect(url_for("admin_users"))

    if bool(user["is_admin"]):
        admins = [u for u in list_users() if u["is_admin"]]
        if len(admins) <= 1:
            flash("Não podes remover o último administrador.", "warning")
            return redirect(url_for("admin_users"))

    delete_user(username)
    flash("Utilizador removido.", "success")
    return redirect(url_for("admin_users"))


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        try:
            user = authenticate_user(username, password)
        except Exception:
            erro = "Erro interno a validar credenciais. Tenta novamente."
            return render_template("login.html", erro=erro), 500

        if user:
            session["logged_in"] = True
            session["user"] = user["username"]
            session["is_admin"] = user["is_admin"]
            return redirect(url_for("dashboard"))

        erro = "Credenciais inválidas."

    return render_template("login.html", erro=erro)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/update_despesa/<nome_antigo>", methods=["POST"])
@login_required
def update_despesa(nome_antigo):
    dados = export_to_dict()
    mes = dados.get("mes_atual", "")

    if "meses" not in dados:
        dados["meses"] = {}

    if mes not in dados["meses"]:
        dados["meses"][mes] = {"despesas": {}}

    despesas = dados["meses"][mes]["despesas"]

    if nome_antigo not in despesas:
        return redirect("/despesas")

    novo_nome = request.form.get("novo_nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()
    categoria = request.form.get("categoria", "").strip()

    if not novo_nome or not valor_txt or not categoria:
        return redirect("/despesas")

    try:
        valor = float(valor_txt)
    except ValueError:
        return redirect("/despesas")

    info_antiga = despesas[nome_antigo]
    pago = info_antiga.get("pago", False) if isinstance(info_antiga, dict) else False

    if novo_nome != nome_antigo:
        del despesas[nome_antigo]

    despesas[novo_nome] = {
        "valor": valor,
        "categoria": categoria,
        "pago": pago
    }

    save_all_from_dict(dados)
    flash("Despesa atualizada com sucesso.", "success")
    return redirect("/despesas")


init_db()
ensure_default_admin(APP_USER, APP_PASSWORD)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)