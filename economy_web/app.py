from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file, jsonify
from functools import wraps
from datetime import datetime
from translations import translations

from config import (
	SECRET_KEY,
	BOOTSTRAP_ADMIN,
	APP_USER,
	APP_PASSWORD,
	ALLOWED_LANGUAGES,
	COMMON_CURRENCIES,
	FLASK_HOST,
	FLASK_PORT,
	FLASK_DEBUG,
)

import io, json, pycountry, csv, time, requests

from database import (
	init_db,
	ensure_default_admin,
	authenticate_user,
	list_users,
	add_user,
	get_user_by_username,
	delete_user,
	export_to_dict,
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
	add_meta_db,
	update_meta_db,
	delete_meta_db,
	update_config_db,
	ensure_user_defaults,
	create_invite_code,
	invite_code_exists,
	use_invite_code,
	list_invite_codes,
	delete_invite_code,
	create_random_invite_code,
	create_multiple_invite_codes,
	set_user_admin,
	update_user_password,
	get_admin_stats,
	get_latest_users,
	get_user_by_email,
	get_user_by_username_or_email,
	create_password_reset_token,
	get_valid_password_reset,
	mark_password_reset_used,
	update_user_password_by_id,
	get_user_by_id,
	update_user_profile,
	email_belongs_to_other_user,
	update_own_password,
	get_connection,
	update_user_language,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY

FX_CACHE = {
    "rates": {},
    "timestamp": 0
}

FX_CACHE_TTL = 3600  # 1 hora


def get_exchange_rate(base_currency, target_currency):
    base_currency = (base_currency or "").upper()
    target_currency = (target_currency or "").upper()

    if not base_currency or not target_currency:
        raise ValueError("Moedas inválidas.")

    if base_currency == target_currency:
        return 1.0

    cache_key = f"{base_currency}->{target_currency}"
    now = time.time()

    if cache_key in FX_CACHE["rates"] and (now - FX_CACHE["timestamp"] < FX_CACHE_TTL):
        return FX_CACHE["rates"][cache_key]

    url = f"https://api.frankfurter.dev/v2/rate/{base_currency}/{target_currency}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()

    if "rate" not in data:
        raise ValueError("Não foi possível obter a taxa de câmbio.")

    rate = float(data["rate"])

    FX_CACHE["rates"][cache_key] = rate
    FX_CACHE["timestamp"] = now

    return rate


def t(key, **kwargs):
    lang = session.get("language", "pt")
    text = translations.get(lang, translations["pt"]).get(key, key)
    return text.format(**kwargs)


def get_previous_month(mes):
    try:
        ano, mes_num = map(int, mes.split("-"))
        if mes_num == 1:
            return f"{ano - 1}-12"
        return f"{ano}-{mes_num - 1:02d}"
    except Exception:
        return None


def get_month_expenses_total(dados, mes):
    total = 0.0
    for d in dados.get("meses", {}).get(mes, {}).get("despesas", {}).values():
        total += d["valor"] if isinstance(d, dict) else float(d)
    return total


def get_top_expense_category(dados, mes):
    categorias = {}

    for _, d in dados.get("meses", {}).get(mes, {}).get("despesas", {}).items():
        if isinstance(d, dict):
            categoria = d.get("categoria", "Sem categoria")
            valor = float(d.get("valor", 0))
        else:
            categoria = "Sem categoria"
            valor = float(d)

        categorias[categoria] = categorias.get(categoria, 0) + valor

    if not categorias:
        return None, 0.0

    categoria, valor = max(categorias.items(), key=lambda x: x[1])
    return categoria, valor


def estimate_months_with_extra(divida_total, taxa_anual, prestacao, extra):
    saldo = float(divida_total)
    taxa_mensal = float(taxa_anual) / 100 / 12
    pagamento = float(prestacao) + float(extra)

    if saldo <= 0:
        return 0

    if pagamento <= saldo * taxa_mensal:
        return None

    meses = 0
    while saldo > 0 and meses < 600:
        juros = saldo * taxa_mensal
        saldo = saldo + juros - pagamento
        meses += 1

    return meses if meses < 600 else None


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
        "session_display_name": session.get("display_name"),
        "session_is_admin": bool(session.get("is_admin", False)),
        "session_language": session.get("language", "pt"),
        "session_currency": session.get("currency", "CHF"),
        "available_languages": [
            ("pt", "Português"),
            ("en", "English"),
            ("de", "Deutsch"),
            ("it", "Italiano"),
            ("es", "Español"),
            ("fr", "Français"),
            ("pl", "Polski"),
            ("ru", "Русский"),
        ],
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
		detalhes.append("score_good_surplus")
	elif sobra > 500:
		score += 30
		detalhes.append("score_strong_positive_surplus")
	elif sobra > 0:
		score += 15
		detalhes.append("score_positive_surplus")
	else:
		detalhes.append("score_negative_surplus")

	if entradas > 0:
		ratio = despesas / entradas
		if ratio < 0.5:
			score += 20
			detalhes.append("score_expenses_controlled")
		elif ratio < 0.7:
			score += 10
			detalhes.append("score_expenses_acceptable")
		else:
			detalhes.append("score_expenses_heavy")

	if entradas > 0:
		ratio_div = total_divida / (entradas * 12)
		if ratio_div < 1:
			score += 20
			detalhes.append("score_debt_low_vs_income")
		elif ratio_div < 2:
			score += 10
			detalhes.append("score_debt_moderate")
		else:
			detalhes.append("score_debt_high")

	if dividas:
		max_taxa = max(d["taxa"] for d in dividas.values())
		if max_taxa < 5:
			score += 20
			detalhes.append("score_interest_low")
		elif max_taxa < 10:
			score += 10
			detalhes.append("score_interest_moderate")
		else:
			detalhes.append("score_interest_high")

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
	

def get_all_countries():
	countries = sorted([country.name for country in pycountry.countries], key=lambda x: x.lower())
	return countries


def get_common_currencies():
	return COMMON_CURRENCIES


def gerar_insights_web(dados, mes):
    entradas, despesas, prestacoes, sobra = calcular_sobra_web(dados, mes)
    pendentes_total = total_pendentes_web(dados)
    dividas = dados.get("dividas", {})
    total_divida = sum(d["total"] for d in dividas.values())

    insights = []

    if entradas > 0:
        ratio_despesas = despesas / entradas
        ratio_pressao = (despesas + prestacoes) / entradas

        if ratio_despesas >= 0.8:
            insights.append({
                "tipo": "error",
                "texto": "insight_expenses_very_high"
            })
        elif ratio_despesas >= 0.6:
            insights.append({
                "tipo": "warning",
                "texto": "insight_expenses_high"
            })

        if ratio_pressao >= 0.9:
            insights.append({
                "tipo": "error",
                "texto": "insight_monthly_pressure_critical"
            })
        elif ratio_pressao >= 0.75:
            insights.append({
                "tipo": "warning",
                "texto": "insight_monthly_pressure_high"
            })

    if sobra <= 0:
        insights.append({
            "tipo": "error",
            "texto": "insight_no_surplus"
        })
    elif sobra < 300:
        insights.append({
            "tipo": "warning",
            "texto": "insight_low_surplus"
        })
    else:
        insights.append({
            "tipo": "success",
            "texto": "insight_good_surplus"
        })

    if pendentes_total > 0:
        if entradas > 0 and pendentes_total > entradas:
            insights.append({
                "tipo": "warning",
                "texto": "insight_pending_high"
            })
        else:
            insights.append({
                "tipo": "warning",
                "texto": "insight_pending_exists"
            })

    if dividas:
        pior_divida = max(dividas.items(), key=lambda x: x[1]["taxa"])
        nome_pior = pior_divida[0]
        taxa_pior = float(pior_divida[1]["taxa"])

        if taxa_pior >= 10:
            insights.append({
                "tipo": "warning",
                "texto": "insight_high_interest_debt",
                "vars": {
                    "name": nome_pior,
                    "rate": f"{taxa_pior:.2f}"
                }
            })
        else:
            insights.append({
                "tipo": "info",
                "texto": "insight_priority_debt",
                "vars": {
                    "name": nome_pior,
                    "rate": f"{taxa_pior:.2f}"
                }
            })

        # novo insight: mais 100 por mês
        info_divida = pior_divida[1]
        meses_atual = estimate_months_with_extra(
            info_divida["total"],
            info_divida["taxa"],
            info_divida["prestacao"],
            0
        )
        meses_extra = estimate_months_with_extra(
            info_divida["total"],
            info_divida["taxa"],
            info_divida["prestacao"],
            100
        )

        if meses_atual and meses_extra and meses_extra < meses_atual:
            poupanca = meses_atual - meses_extra
            insights.append({
                "tipo": "info",
                "texto": "insight_extra_payment_help",
                "vars": {
                    "name": nome_pior,
                    "months": str(poupanca)
                }
            })

    # novo insight: comparação com mês anterior
    mes_anterior = get_previous_month(mes)
    if mes_anterior:
        despesas_anterior = get_month_expenses_total(dados, mes_anterior)
        if despesas_anterior > 0:
            diff = despesas - despesas_anterior
            pct = (diff / despesas_anterior) * 100

            if pct >= 10:
                insights.append({
                    "tipo": "warning",
                    "texto": "insight_worse_than_last_month",
                    "vars": {
                        "percent": f"{pct:.1f}"
                    }
                })
            elif pct <= -10:
                insights.append({
                    "tipo": "success",
                    "texto": "insight_better_than_last_month",
                    "vars": {
                        "percent": f"{abs(pct):.1f}"
                    }
                })

    # novo insight: categoria mais pesada
    categoria_top, valor_top = get_top_expense_category(dados, mes)
    if categoria_top and despesas > 0:
        peso = (valor_top / despesas) * 100
        if peso >= 35:
            insights.append({
                "tipo": "info",
                "texto": "insight_top_category",
                "vars": {
                    "category": categoria_top,
                    "percent": f"{peso:.1f}"
                }
            })

    if total_divida <= 0 and pendentes_total <= 0 and sobra > 0:
        insights.append({
            "tipo": "success",
            "texto": "insight_financial_balance"
        })

    return insights[:6]


@app.route("/api/convert")
@login_required
def api_convert():
    amount = request.args.get("amount", "").strip()
    from_currency = request.args.get("from", session.get("currency", "CHF")).strip().upper()
    to_currency = request.args.get("to", "EUR").strip().upper()

    try:
        amount_value = float(amount) if amount else 0.0

        if amount_value < 0:
            raise ValueError("Valor inválido.")

        rate = get_exchange_rate(from_currency, to_currency)
        converted = amount_value * rate

        return jsonify({
            "ok": True,
            "amount": amount_value,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": rate,
            "converted": converted,
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400
	
	
@app.route("/converter", methods=["GET", "POST"])
@login_required
def converter():
    currencies = get_common_currencies()

    result = None
    amount = ""
    from_currency = session.get("currency", "CHF")
    to_currency = "EUR"

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        from_currency = request.form.get("from_currency", from_currency).strip().upper()
        to_currency = request.form.get("to_currency", to_currency).strip().upper()

        try:
            amount_value = float(amount)

            if amount_value < 0:
                raise ValueError("Valor inválido.")

            rate = get_exchange_rate(from_currency, to_currency)
            converted = amount_value * rate

            result = {
                "amount": amount_value,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": rate,
                "converted": converted,
            }

        except Exception as e:
            app.logger.exception("Erro no conversor de moedas")
            flash(f"Erro ao converter moeda: {e}", "error")

    return render_template(
        "converter.html",
        currencies=currencies,
        result=result,
        amount=amount,
        from_currency=from_currency,
        to_currency=to_currency,
    )


@app.before_request
def ensure_language():
	if "language" not in session:
		session["language"] = "pt"


@app.context_processor
def inject_translations():
	return dict(t=t)


@app.route("/set-language-public", methods=["POST"])
def set_language_public():
    lang = request.form.get("language", "").strip()
    allowed = ["pt", "en", "de", "it", "es", "fr", "pl", "ru"]

    if lang in allowed:
        session["language"] = lang

    return redirect(request.referrer or url_for("login"))


@app.route("/")
@login_required
def dashboard():
	dados = export_to_dict(session["user_id"])
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

	total_geral = despesas + dividas + pendentes
	insights = gerar_insights_web(dados, mes)

	return render_template(
		"dashboard.html",
		entradas=entradas,
		despesas=despesas,
		dividas=dividas,
		pendentes=pendentes,
		saldo=saldo_real,
		total_geral=total_geral,
		insights=insights,
	)


# =========================
# DESPESAS
# =========================
@app.route("/despesas")
@login_required
def despesas():
	dados = export_to_dict(session["user_id"])
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
	dados = export_to_dict(session["user_id"])
	mes = dados.get("mes_atual", "")

	nome = request.form.get("nome", "").strip()
	valor_txt = request.form.get("valor", "").strip()
	categoria = request.form.get("categoria", "").strip()

	if not nome or not valor_txt or not categoria or not mes:
		flash("Faltam dados para guardar a despesa.", "error")
		return redirect("/despesas")

	try:
		valor = float(valor_txt)
		db_add_despesa(session["user_id"], mes, nome, valor, categoria, 0)
		flash("Despesa adicionada com sucesso.", "success")
	except Exception as e:
		app.logger.exception("Erro ao adicionar despesa")
		flash(f"Erro ao adicionar despesa: {e}", "error")

	return redirect("/despesas")


@app.route("/delete_despesa/<nome>", methods=["POST"])
@login_required
def delete_despesa(nome):
	dados = export_to_dict(session["user_id"])
	mes = dados.get("mes_atual", "")

	if not mes:
		flash("Mês atual inválido.", "error")
		return redirect("/despesas")

	try:
		db_delete_despesa(session["user_id"], mes, nome)
		flash("Despesa removida.", "warning")
	except Exception as e:
		app.logger.exception("Erro ao apagar despesa")
		flash(f"Erro ao remover despesa: {e}", "error")

	return redirect("/despesas")


@app.route("/toggle_pago/<nome>", methods=["POST"])
@login_required
def toggle_pago(nome):
	dados = export_to_dict(session["user_id"])
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
		db_update_despesa_pago(session["user_id"], mes, nome, not pago_atual)
		flash("Estado da despesa atualizado.", "success")
	except Exception as e:
		app.logger.exception("Erro ao atualizar estado da despesa")
		flash(f"Erro ao atualizar estado da despesa: {e}", "error")

	return redirect("/despesas")

@app.route("/dividas")
@login_required
def dividas():
	dados = export_to_dict(session["user_id"])
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
		add_divida_db(session["user_id"], nome, inicial, taxa, prestacao)
	except ValueError:
		return redirect("/dividas")
	except Exception as e:
		app.logger.exception("Erro ao adicionar dívida")
		flash(f"Erro ao adicionar dívida: {e}", "error")
		return redirect("/dividas")

	flash("Dívida adicionada com sucesso.", "success")
	return redirect("/dividas")


@app.route("/delete_divida/<nome>", methods=["POST"])
@login_required
def delete_divida(nome):
	try:
		delete_divida_db(session["user_id"], nome)
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
		update_divida_db(session["user_id"], nome, inicial, total, taxa, prestacao)
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
	dados = export_to_dict(session["user_id"])
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
		add_pendente_db(session["user_id"], nome, valor_mensal, desde, notas)
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
		update_pendente_db(session["user_id"], nome, novo_nome, valor_mensal, desde, notas)
	except ValueError:
		return redirect("/pendentes")
	except Exception as e:
		app.logger.exception("Erro ao atualizar pendente")
		flash(f"Erro ao atualizar pendente: {e}", "error")
		return redirect("/pendentes")

	flash("Pendente atualizado com sucesso.", "success")
	return redirect("/pendentes")


@app.route("/delete_pendente/<nome>", methods=["POST"])
@login_required
def delete_pendente(nome):
	try:
		delete_pendente_db(session["user_id"], nome)
	except Exception as e:
		app.logger.exception("Erro ao remover pendente")
		flash(f"Erro ao remover pendente: {e}", "error")
		return redirect("/pendentes")

	flash("Pendente removido.", "warning")
	return redirect("/pendentes")


@app.route("/convert_pendente/<nome>", methods=["POST"])
@login_required
def convert_pendente(nome):
	dados = export_to_dict(session["user_id"])
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
		convert_pendente_to_divida_db(session["user_id"], nome, total, nome_divida)
	except Exception as e:
		app.logger.exception("Erro ao converter pendente")
		flash(f"Erro ao converter pendente: {e}", "error")
		return redirect("/pendentes")

	flash("Pendente convertido em dívida.", "success")
	return redirect("/pendentes")


@app.route("/sistema")
@login_required
def sistema():
	dados = export_to_dict(session["user_id"])

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
	saldo_txt = request.form.get("saldo_inicial", "").strip()
	mes_atual = request.form.get("mes_atual", "").strip()

	try:
		saldo_inicial = float(saldo_txt)
	except ValueError:
		return redirect("/sistema")

	if not validar_mes_web(mes_atual):
		return redirect("/sistema")

	try:
		update_config_db(session["user_id"], mes_atual, saldo_inicial)
	except Exception as e:
		app.logger.exception("Erro ao atualizar config")
		flash(f"Erro ao atualizar config: {e}", "error")
		return redirect("/sistema")

	flash("Configuração atualizada com sucesso.", "success")
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
		db_add_salario(session["user_id"], nome, valor)
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
		db_update_salario(session["user_id"], nome, novo_nome, valor)
	except ValueError:
		return redirect("/sistema")
	except Exception as e:
		app.logger.exception("Erro ao atualizar salário")
		flash(f"Erro ao atualizar salário: {e}", "error")
		return redirect("/sistema")

	flash("Salário atualizado com sucesso.", "success")
	return redirect("/sistema")


@app.route("/delete_salario/<nome>", methods=["POST"])
@login_required
def delete_salario(nome):
	try:
		delete_salario_db(session["user_id"], nome)
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
		add_contribuicao_db(session["user_id"], nome, valor)
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
		update_contribuicao_db(session["user_id"], nome, novo_nome, valor)
	except ValueError:
		return redirect("/sistema")
	except Exception as e:
		app.logger.exception("Erro ao atualizar contribuição")
		flash(f"Erro ao atualizar contribuição: {e}", "error")
		return redirect("/sistema")

	flash("Contribuição atualizada com sucesso.", "success")
	return redirect("/sistema")


@app.route("/delete_contribuicao/<nome>", methods=["POST"])
@login_required
def delete_contribuicao(nome):
	try:
		delete_contribuicao_db(session["user_id"], nome)
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
		add_categoria_db(session["user_id"], nome)
	except Exception as e:
		app.logger.exception("Erro ao adicionar categoria")
		flash(f"Erro ao adicionar categoria: {e}", "error")
		return redirect("/sistema")

	flash("Categoria adicionada com sucesso.", "success")
	return redirect("/sistema")


@app.route("/delete_categoria/<nome>", methods=["POST"])
@login_required
def delete_categoria(nome):
	try:
		delete_categoria_db(session["user_id"], nome)
	except Exception as e:
		app.logger.exception("Erro ao remover categoria")
		flash(f"Erro ao remover categoria: {e}", "error")
		return redirect("/sistema")

	flash("Categoria removida.", "warning")
	return redirect("/sistema")


@app.route("/planeamento")
@login_required
def planeamento():
	dados = export_to_dict(session["user_id"])
	mes = dados.get("mes_atual", "")

	entradas, despesas, prestacoes, sobra = calcular_sobra_web(dados, mes)
	saldo_inicial = float(dados.get("saldo_inicial", 0))
	saldo_real = saldo_inicial + sobra
	pendentes = total_pendentes_web(dados)

	total_divida = sum(d["total"] for d in dados.get("dividas", {}).values())
	score, detalhes = score_web(dados, mes)

	total_geral = despesas + prestacoes + pendentes

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
		total_geral=total_geral,
		meses_liberdade=meses_liberdade,
		prioridade=prioridade,
		score=score,
		detalhes=detalhes
	)

@app.route("/simulacao")
@login_required
def simulacao():
	dados = export_to_dict(session["user_id"])

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

	total_divida = sum(d["total"] for d in dados.get("dividas", {}).values())
	total_pendentes = total_pendentes_web(dados)
	total_geral = total_divida + total_pendentes

	return render_template(
		"simulacao.html",
		extra=extra,
		resultado=resultado,
		cenarios=cenarios,
		total_divida=total_divida,
		total_pendentes=total_pendentes,
		total_geral=total_geral
	)

@app.route("/timeline")
@login_required
def timeline():
	dados = export_to_dict(session["user_id"])

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


@app.route("/admin")
@admin_required
def admin_dashboard():
	stats = get_admin_stats()
	latest_users = get_latest_users(5)
	return render_template("admin_dashboard.html", stats=stats, latest_users=latest_users)


@app.route("/admin/users")
@admin_required
def admin_users():
	users = list_users()
	return render_template("admin_users.html", users=users)


@app.route("/admin/users/add", methods=["POST"])
@admin_required
def admin_add_user():
	username = request.form.get("username", "").strip()
	email = request.form.get("email", "").strip().lower()
	password = request.form.get("password", "").strip()
	role = request.form.get("role", "user").strip().lower()
	is_admin = role == "admin"

	if not username or not email or not password:
		flash("Preenche utilizador, email e password.", "error")
		return redirect(url_for("admin_users"))

	if get_user_by_username(username):
		flash("Já existe um utilizador com esse nome.", "warning")
		return redirect(url_for("admin_users"))

	if get_user_by_email(email):
		flash("Já existe um utilizador com esse email.", "warning")
		return redirect(url_for("admin_users"))

	try:
		add_user(username, email, password, is_admin=is_admin)
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


@app.route("/admin/users/toggle-admin/<username>", methods=["POST"])
@admin_required
def admin_toggle_user_admin(username):
	if username == session.get("user"):
		flash("Não podes alterar o teu próprio papel aqui.", "warning")
		return redirect(url_for("admin_users"))

	user = get_user_by_username(username)
	if not user:
		flash("Utilizador não encontrado.", "warning")
		return redirect(url_for("admin_users"))

	novo_estado = not bool(user["is_admin"])

	if not novo_estado:
		admins = [u for u in list_users() if u["is_admin"]]
		if len(admins) <= 1:
			flash("Não podes remover o último administrador.", "warning")
			return redirect(url_for("admin_users"))

	try:
		set_user_admin(username, novo_estado)
	except Exception as e:
		app.logger.exception("Erro ao alterar permissões do utilizador")
		flash(f"Erro ao atualizar permissões: {e}", "error")
		return redirect(url_for("admin_users"))

	if novo_estado:
		flash("Utilizador promovido a administrador.", "success")
	else:
		flash("Permissões de administrador removidas.", "warning")

	return redirect(url_for("admin_users"))


@app.route("/admin/users/reset-password/<username>", methods=["POST"])
@admin_required
def admin_reset_user_password(username):
	user = get_user_by_username(username)
	if not user:
		flash("Utilizador não encontrado.", "warning")
		return redirect(url_for("admin_users"))

	new_password = request.form.get("new_password", "").strip()
	confirm_password = request.form.get("confirm_password", "").strip()

	if not new_password or not confirm_password:
		flash("Preenche os dois campos da nova password.", "error")
		return redirect(url_for("admin_users"))

	if new_password != confirm_password:
		flash("As passwords não coincidem.", "error")
		return redirect(url_for("admin_users"))

	if len(new_password) < 6:
		flash("A password deve ter pelo menos 6 caracteres.", "error")
		return redirect(url_for("admin_users"))

	try:
		update_user_password(username, new_password)
	except Exception as e:
		app.logger.exception("Erro ao atualizar password")
		flash(f"Erro ao atualizar password: {e}", "error")
		return redirect(url_for("admin_users"))

	flash(f"Password do utilizador {username} atualizada com sucesso.", "success")
	return redirect(url_for("admin_users"))


@app.route("/register", methods=["GET", "POST"])
def register():
	if request.method == "POST":
		username = request.form.get("username", "").strip()
		email = request.form.get("email", "").strip().lower()
		password = request.form.get("password", "").strip()
		confirm_password = request.form.get("confirm_password", "").strip()
		invite_code = request.form.get("invite_code", "").strip()
		first_name = request.form.get("first_name", "").strip()
		last_name = request.form.get("last_name", "").strip()
		birth_date = request.form.get("birth_date", "").strip()
		country = request.form.get("country", "").strip()
		language = request.form.get("language", "pt").strip()
		currency = request.form.get("currency", "CHF").strip()

		if not username or not email or not password or not confirm_password or not invite_code or not first_name or not last_name or not country:
			flash("Preenche todos os campos obrigatórios.", "error")
			return render_template(
				"register.html",
				countries=get_all_countries(),
				currencies=get_common_currencies(),
			), 400

		if password != confirm_password:
			flash("As passwords não coincidem.", "error")
			return render_template(
				"register.html",
				countries=get_all_countries(),
				currencies=get_common_currencies(),
			), 400

		if len(password) < 6:
			flash("A password deve ter pelo menos 6 caracteres.", "error")
			return render_template(
				"register.html",
				countries=get_all_countries(),
				currencies=get_common_currencies(),
			), 400

		if get_user_by_username(username):
			flash("Já existe um utilizador com esse nome.", "warning")
			return render_template(
				"register.html",
				countries=get_all_countries(),
				currencies=get_common_currencies(),
			), 400

		if get_user_by_email(email):
			flash("Já existe uma conta com esse email.", "warning")
			return render_template(
				"register.html",
				countries=get_all_countries(),
				currencies=get_common_currencies(),
			), 400

		convite = invite_code_exists(invite_code)
		if not convite:
			flash("Código de convite inválido ou já usado.", "error")
			return render_template(
				"register.html",
				countries=get_all_countries(),
				currencies=get_common_currencies(),
			), 400

		try:
			add_user(
				username=username,
				email=email,
				password=password,
				is_admin=False,
				first_name=first_name,
				last_name=last_name,
				birth_date=birth_date if birth_date else None,
				country=country,
				language=language,
				currency=currency,
			)
			use_invite_code(invite_code)

			user = authenticate_user(email, password)

			if user:
				ensure_user_defaults(user["id"])

				display_name = f"{(user.get('first_name') or '').strip()} {(user.get('last_name') or '').strip()}".strip()
				if not display_name:
					display_name = user["username"]

				session["logged_in"] = True
				session["user"] = user["username"]
				session["display_name"] = display_name
				session["user_id"] = user["id"]
				session["is_admin"] = user["is_admin"]
				session["language"] = user.get("language", "pt")
				session["currency"] = user.get("currency", "CHF")

				flash("Conta criada com sucesso.", "success")
				return redirect(url_for("dashboard"))

			flash("Conta criada, mas não foi possível iniciar sessão.", "warning")
			return redirect(url_for("login"))

		except Exception as e:
			app.logger.exception("Erro ao registar utilizador")
			flash(f"Erro ao criar conta: {e}", "error")
			return render_template(
				"register.html",
				countries=get_all_countries(),
				currencies=get_common_currencies(),
			), 500

	return render_template(
		"register.html",
		countries=get_all_countries(),
		currencies=get_common_currencies(),
	)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
	if request.method == "POST":
		email = request.form.get("email", "").strip().lower()

		if not email:
			flash("Introduz o teu email.", "error")
			return render_template("forgot_password.html"), 400

		try:
			token = create_password_reset_token(email)

			# Para já mostramos o link no flash/log.
			# Mais tarde ligamos SMTP e mandamos email real.
			if token:
				reset_link = url_for("reset_password", token=token, _external=True)
				app.logger.info("Password reset link for %s: %s", email, reset_link)
				flash(f"Link de reset gerado: {reset_link}", "success")
			else:
				flash("Se existir uma conta com esse email, o link foi gerado.", "success")

		except Exception as e:
			app.logger.exception("Erro ao gerar reset de password")
			flash(f"Erro ao processar pedido: {e}", "error")
			return render_template("forgot_password.html"), 500

		return redirect(url_for("login"))

	return render_template("forgot_password.html")


@app.route("/set-language", methods=["POST"])
@login_required
def set_language():
    lang = request.form.get("language", "").strip()
    allowed = ["pt", "en", "de", "it", "es", "fr", "pl", "ru"]

    if lang not in allowed:
        flash("Idioma inválido.", "error")
        return redirect(request.referrer or url_for("dashboard"))

    session["language"] = lang
    update_user_language(session["user_id"], lang)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
	reset_entry = get_valid_password_reset(token)

	if not reset_entry:
		flash("Link inválido ou expirado.", "error")
		return redirect(url_for("login"))

	if request.method == "POST":
		password = request.form.get("password", "").strip()
		confirm_password = request.form.get("confirm_password", "").strip()

		if not password or not confirm_password:
			flash("Preenche ambos os campos.", "error")
			return render_template("reset_password.html", token=token), 400

		if password != confirm_password:
			flash("As passwords não coincidem.", "error")
			return render_template("reset_password.html", token=token), 400

		if len(password) < 6:
			flash("A password deve ter pelo menos 6 caracteres.", "error")
			return render_template("reset_password.html", token=token), 400

		try:
			update_user_password_by_id(reset_entry["user_id"], password)
			mark_password_reset_used(token)
			flash("Password atualizada com sucesso.", "success")
			return redirect(url_for("login"))
		except Exception as e:
			app.logger.exception("Erro ao atualizar password")
			flash(f"Erro ao atualizar password: {e}", "error")
			return render_template("reset_password.html", token=token), 500

	return render_template("reset_password.html", token=token)


@app.route("/perfil")
@login_required
def perfil():
	user = get_user_by_id(session["user_id"])

	if not user:
		flash("Utilizador não encontrado.", "error")
		return redirect(url_for("dashboard"))

	return render_template(
		"perfil.html",
		user=user,
		countries=get_all_countries(),
		currencies=get_common_currencies(),
	)



@app.route("/perfil/update", methods=["POST"])
@login_required
def update_profile():
	user_id = session["user_id"]

	first_name = request.form.get("first_name", "").strip()
	last_name = request.form.get("last_name", "").strip()
	email = request.form.get("email", "").strip().lower()
	birth_date = request.form.get("birth_date", "").strip()
	country = request.form.get("country", "").strip()
	language = request.form.get("language", "").strip()
	currency = request.form.get("currency", "").strip()

	if not first_name or not last_name or not email or not country or not language or not currency:
		flash("Preenche todos os campos obrigatórios.", "error")
		return redirect(url_for("perfil"))

	if email_belongs_to_other_user(email, user_id):
		flash("Esse email já está a ser usado por outra conta.", "warning")
		return redirect(url_for("perfil"))

	try:
		update_user_profile(
			user_id,
			first_name,
			last_name,
			email,
			birth_date,
			country,
			language,
			currency
		)

		display_name = f"{first_name} {last_name}".strip()
		session["display_name"] = display_name if display_name else session.get("user")
		session["language"] = language
		session["currency"] = currency

		flash("Perfil atualizado com sucesso.", "success")
	except Exception as e:
		app.logger.exception("Erro ao atualizar perfil")
		flash(f"Erro ao atualizar perfil: {e}", "error")

	return redirect(url_for("perfil"))


@app.route("/perfil/password", methods=["POST"])
@login_required
def update_profile_password():
	user_id = session["user_id"]

	current_password = request.form.get("current_password", "").strip()
	new_password = request.form.get("new_password", "").strip()
	confirm_password = request.form.get("confirm_password", "").strip()

	if not current_password or not new_password or not confirm_password:
		flash("Preenche todos os campos da password.", "error")
		return redirect(url_for("perfil"))

	if new_password != confirm_password:
		flash("As novas passwords não coincidem.", "error")
		return redirect(url_for("perfil"))

	if len(new_password) < 6:
		flash("A nova password deve ter pelo menos 6 caracteres.", "error")
		return redirect(url_for("perfil"))

	try:
		ok, message = update_own_password(user_id, current_password, new_password)

		if ok:
			flash(message, "success")
		else:
			flash(message, "error")

	except Exception as e:
		app.logger.exception("Erro ao atualizar password do perfil")
		flash(f"Erro ao atualizar password: {e}", "error")

	return redirect(url_for("perfil"))


@app.route("/login", methods=["GET", "POST"])
def login():
	erro = None

	if request.method == "POST":
		identifier = request.form.get("identifier", "").strip()
		password = request.form.get("password", "").strip()

		try:
			user = authenticate_user(identifier, password)
		except Exception:
			erro = "Erro interno a validar credenciais. Tenta novamente."
			return render_template("login.html", erro=erro), 500

		if user:
			ensure_user_defaults(user["id"])

			display_name = f"{(user.get('first_name') or '').strip()} {(user.get('last_name') or '').strip()}".strip()
			if not display_name:
				display_name = user["username"]

			selected_lang = session.get("language", "pt")

			session["logged_in"] = True
			session["user"] = user["username"]
			session["display_name"] = display_name
			session["user_id"] = user["id"]
			session["is_admin"] = user["is_admin"]
			session["language"] = selected_lang
			session["currency"] = user.get("currency", "CHF")

			update_user_language(user["id"], selected_lang)

			return redirect(url_for("dashboard"))

		erro = "Credenciais inválidas."

	return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
	lang = session.get("language", "pt")
	session.clear()
	session["language"] = lang
	return redirect(url_for("login"))


@app.route("/update_despesa/<nome_antigo>", methods=["POST"])
@login_required
def update_despesa(nome_antigo):
	dados = export_to_dict(session["user_id"])
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

	flash("Despesa atualizada com sucesso.", "success")
	return redirect("/despesas")


@app.route("/metas")
@login_required
def metas():
	dados = export_to_dict(session["user_id"])
	return render_template("metas.html", metas=dados.get("metas", []))


@app.route("/add_meta", methods=["POST"])
@login_required
def add_meta():
	nome = request.form.get("nome", "").strip()
	tipo = request.form.get("tipo", "").strip()
	alvo_txt = request.form.get("alvo", "").strip()

	if not nome or not tipo or not alvo_txt:
		return redirect("/metas")

	try:
		alvo = float(alvo_txt)
		add_meta_db(session["user_id"], nome, tipo, alvo)
	except ValueError:
		return redirect("/metas")
	except Exception as e:
		app.logger.exception("Erro ao adicionar meta")
		flash(f"Erro ao adicionar meta: {e}", "error")
		return redirect("/metas")

	flash("Meta adicionada com sucesso.", "success")
	return redirect("/metas")


@app.route("/update_meta/<int:meta_id>", methods=["POST"])
@login_required
def update_meta(meta_id):
	nome = request.form.get("nome", "").strip()
	tipo = request.form.get("tipo", "").strip()
	alvo_txt = request.form.get("alvo", "").strip()

	if not nome or not tipo or not alvo_txt:
		return redirect("/metas")

	try:
		alvo = float(alvo_txt)
		update_meta_db(session["user_id"], meta_id, nome, tipo, alvo)
	except ValueError:
		return redirect("/metas")
	except Exception as e:
		app.logger.exception("Erro ao atualizar meta")
		flash(f"Erro ao atualizar meta: {e}", "error")
		return redirect("/metas")

	flash("Meta atualizada com sucesso.", "success")
	return redirect("/metas")


@app.route("/delete_meta/<int:meta_id>", methods=["POST"])
@login_required
def delete_meta(meta_id):
	try:
		delete_meta_db(session["user_id"], meta_id)
	except Exception as e:
		app.logger.exception("Erro ao remover meta")
		flash(f"Erro ao remover meta: {e}", "error")
		return redirect("/metas")

	flash("Meta removida.", "warning")
	return redirect("/metas")


@app.route("/admin/invites")
@admin_required
def admin_invites():
	invites = list_invite_codes()
	return render_template("admin_invites.html", invites=invites)


@app.route("/admin/invites/add", methods=["POST"])
@admin_required
def admin_add_invite():
	code = request.form.get("code", "").strip()

	if not code:
		flash("Código inválido.", "error")
		return redirect(url_for("admin_invites"))

	try:
		create_invite_code(code)
		flash("Código de convite criado com sucesso.", "success")
	except Exception as e:
		app.logger.exception("Erro ao criar código de convite")
		flash(f"Erro ao criar código: {e}", "error")

	return redirect(url_for("admin_invites"))


@app.route("/admin/invites/delete/<code>", methods=["POST"])
@admin_required
def admin_delete_invite(code):
	try:
		delete_invite_code(code)
		flash("Código removido.", "warning")
	except Exception as e:
		app.logger.exception("Erro ao remover código")
		flash(f"Erro ao remover código: {e}", "error")

	return redirect(url_for("admin_invites"))


@app.route("/admin/invites/generate", methods=["POST"])
@admin_required
def admin_generate_invite():
	try:
		code = create_random_invite_code(10)
		flash(f"Código gerado com sucesso: {code}", "success")
	except Exception as e:
		app.logger.exception("Erro ao gerar código de convite")
		flash(f"Erro ao gerar código: {e}", "error")

	return redirect(url_for("admin_invites"))


@app.route("/admin/invites/generate-multiple", methods=["POST"])
@admin_required
def admin_generate_multiple_invites():
	quantity_txt = request.form.get("quantity", "5").strip()

	try:
		quantity = int(quantity_txt)
		if quantity < 1:
			quantity = 1
		if quantity > 50:
			quantity = 50
	except ValueError:
		quantity = 5

	try:
		codes = create_multiple_invite_codes(quantity, 10)
		flash("Códigos gerados: " + ", ".join(codes), "success")
	except Exception as e:
		app.logger.exception("Erro ao gerar múltiplos códigos")
		flash(f"Erro ao gerar códigos: {e}", "error")

	return redirect(url_for("admin_invites"))


@app.route("/export")
@login_required
def export_page():
	return render_template("export.html")


@app.route("/export/json")
@login_required
def export_data_json():
	try:
		dados = export_to_dict(session["user_id"])

		buffer = io.BytesIO()
		buffer.write(json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8"))
		buffer.seek(0)

		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		filename = f"financas_{session.get('user', 'user')}_{timestamp}.json"

		return send_file(
			buffer,
			as_attachment=True,
			download_name=filename,
			mimetype="application/json"
		)
	except Exception as e:
		app.logger.exception("Erro ao exportar JSON")
		flash(f"Erro ao exportar JSON: {e}", "error")
		return redirect(url_for("export_page"))


@app.route("/export/csv")
@login_required
def export_data_csv():
	try:
		dados = export_to_dict(session["user_id"])

		output = io.StringIO()
		writer = csv.writer(output)

		writer.writerow(["SECÇÃO", "CAMPO_1", "CAMPO_2", "CAMPO_3", "CAMPO_4", "VALOR"])

		writer.writerow(["CONFIG", "mes_atual", "", "", "", dados.get("mes_atual", "")])
		writer.writerow(["CONFIG", "saldo_inicial", "", "", "", dados.get("saldo_inicial", 0)])

		for nome, valor in dados.get("salarios", {}).items():
			writer.writerow(["SALARIO", nome, "", "", "", valor])

		for nome, valor in dados.get("contribuicoes", {}).items():
			writer.writerow(["CONTRIBUICAO", nome, "", "", "", valor])

		for nome in dados.get("categorias", []):
			writer.writerow(["CATEGORIA", nome, "", "", "", ""])

		for nome, info in dados.get("dividas", {}).items():
			writer.writerow([
				"DIVIDA",
				nome,
				info.get("inicial", 0),
				info.get("total", 0),
				info.get("taxa", 0),
				info.get("prestacao", 0)
			])

		for nome, info in dados.get("pendentes", {}).items():
			writer.writerow([
				"PENDENTE",
				nome,
				info.get("valor_mensal", 0),
				info.get("desde", ""),
				info.get("notas", ""),
				""
			])

		for nome, info in dados.get("despesas_fixas", {}).items():
			writer.writerow([
				"DESPESA_FIXA",
				nome,
				info.get("categoria", ""),
				"",
				"",
				info.get("valor", 0)
			])

		for meta in dados.get("metas", []):
			writer.writerow([
				"META",
				meta.get("nome", ""),
				meta.get("tipo", ""),
				"",
				"",
				meta.get("alvo", 0)
			])

		for mes, info_mes in dados.get("meses", {}).items():
			for nome, info in info_mes.get("despesas", {}).items():
				writer.writerow([
					"DESPESA",
					mes,
					nome,
					info.get("categoria", ""),
					int(bool(info.get("pago", False))),
					info.get("valor", 0)
				])

		csv_bytes = io.BytesIO(output.getvalue().encode("utf-8-sig"))
		csv_bytes.seek(0)

		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		filename = f"financas_{session.get('user', 'user')}_{timestamp}.csv"

		return send_file(
			csv_bytes,
			as_attachment=True,
			download_name=filename,
			mimetype="text/csv"
		)
	except Exception as e:
		app.logger.exception("Erro ao exportar CSV")
		flash(f"Erro ao exportar CSV: {e}", "error")
		return redirect(url_for("export_page"))
	

@app.route("/import/csv", methods=["POST"])
@login_required
def import_csv():
	file = request.files.get("file")
	data_type = request.form.get("type")

	if not file:
		flash("Ficheiro inválido.", "error")
		return redirect(url_for("import_page"))

	try:
		import csv
		import io

		stream = io.StringIO(file.stream.read().decode("utf-8"))
		reader = csv.DictReader(stream)

		rows = list(reader)

		# TODO: tratar consoante data_type
		print(f"Import {data_type}: {len(rows)} linhas")

		flash("CSV importado com sucesso.", "success")

	except Exception as e:
		flash(f"Erro ao importar CSV: {e}", "error")

	return redirect(url_for("import_page"))


@app.route("/import", methods=["GET", "POST"])
@login_required
def import_data():
	if request.method == "POST":
		file = request.files.get("file")

		if not file or file.filename == "":
			flash("Seleciona um ficheiro para importar.", "error")
			return redirect(url_for("import_data"))

		if not file.filename.lower().endswith(".json"):
			flash("Só é permitido importar ficheiros JSON.", "error")
			return redirect(url_for("import_data"))

		try:
			dados = json.load(file)

			user_id = session["user_id"]

			# CONFIG
			update_config_db(
				user_id,
				dados.get("mes_atual", datetime.now().strftime("%Y-%m")),
				float(dados.get("saldo_inicial", 0.0))
			)

			conn = get_connection()
			cur = conn.cursor()

			try:
				cur.execute("DELETE FROM salarios WHERE user_id = %s", (user_id,))
				cur.execute("DELETE FROM contribuicoes WHERE user_id = %s", (user_id,))
				cur.execute("DELETE FROM categorias WHERE user_id = %s", (user_id,))
				cur.execute("DELETE FROM despesas WHERE user_id = %s", (user_id,))
				cur.execute("DELETE FROM dividas WHERE user_id = %s", (user_id,))
				cur.execute("DELETE FROM pendentes WHERE user_id = %s", (user_id,))
				cur.execute("DELETE FROM despesas_fixas WHERE user_id = %s", (user_id,))
				cur.execute("DELETE FROM metas WHERE user_id = %s", (user_id,))

				for nome, valor in dados.get("salarios", {}).items():
					cur.execute("""
						INSERT INTO salarios (user_id, nome, valor)
						VALUES (%s, %s, %s)
					""", (user_id, nome, float(valor)))

				for nome, valor in dados.get("contribuicoes", {}).items():
					cur.execute("""
						INSERT INTO contribuicoes (user_id, nome, valor)
						VALUES (%s, %s, %s)
					""", (user_id, nome, float(valor)))

				for nome in dados.get("categorias", []):
					cur.execute("""
						INSERT INTO categorias (user_id, nome)
						VALUES (%s, %s)
					""", (user_id, nome))

				for nome, info in dados.get("dividas", {}).items():
					cur.execute("""
						INSERT INTO dividas (user_id, nome, inicial, total, taxa, prestacao)
						VALUES (%s, %s, %s, %s, %s, %s)
					""", (
						user_id,
						nome,
						float(info.get("inicial", info.get("total", 0))),
						float(info.get("total", 0)),
						float(info.get("taxa", 0)),
						float(info.get("prestacao", 0)),
					))

				for nome, info in dados.get("pendentes", {}).items():
					cur.execute("""
						INSERT INTO pendentes (user_id, nome, valor_mensal, desde, notas)
						VALUES (%s, %s, %s, %s, %s)
					""", (
						user_id,
						nome,
						float(info.get("valor_mensal", 0)),
						info.get("desde", ""),
						info.get("notas", ""),
					))

				for nome, info in dados.get("despesas_fixas", {}).items():
					cur.execute("""
						INSERT INTO despesas_fixas (user_id, nome, valor, categoria)
						VALUES (%s, %s, %s, %s)
					""", (
						user_id,
						nome,
						float(info.get("valor", 0)),
						info.get("categoria", "Sem categoria"),
					))

				for meta in dados.get("metas", []):
					cur.execute("""
						INSERT INTO metas (user_id, nome, tipo, alvo)
						VALUES (%s, %s, %s, %s)
					""", (
						user_id,
						meta.get("nome", ""),
						meta.get("tipo", ""),
						float(meta.get("alvo", 0)),
					))

				for mes, info_mes in dados.get("meses", {}).items():
					for nome, info in info_mes.get("despesas", {}).items():
						cur.execute("""
							INSERT INTO despesas (user_id, mes, nome, valor, categoria, pago)
							VALUES (%s, %s, %s, %s, %s, %s)
						""", (
							user_id,
							mes,
							nome,
							float(info.get("valor", 0)),
							info.get("categoria", "Sem categoria"),
							1 if info.get("pago", False) else 0,
						))

				conn.commit()
			except Exception:
				conn.rollback()
				raise
			finally:
				conn.close()

			flash("Dados importados com sucesso.", "success")
			return redirect(url_for("dashboard"))

		except Exception as e:
			app.logger.exception("Erro ao importar dados")
			flash(f"Erro ao importar dados: {e}", "error")
			return redirect(url_for("import_data"))

	return render_template("import.html")


init_db()
if BOOTSTRAP_ADMIN:
	if not APP_USER or not APP_PASSWORD:
		raise RuntimeError(
			"BOOTSTRAP_ADMIN is enabled but APP_USER or APP_PASSWORD is missing."
		)
	ensure_default_admin(APP_USER, APP_PASSWORD)


if __name__ == "__main__":
	app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)