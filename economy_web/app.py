from flask import Flask, render_template, request, redirect
from database import export_to_dict, save_all_from_dict

app = Flask(__name__)


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
def despesas():
    dados = export_to_dict()
    mes = dados.get("mes_atual", "")

    if "meses" not in dados:
        dados["meses"] = {}

    if mes not in dados["meses"]:
        dados["meses"][mes] = {"despesas": {}}

    despesas = dados["meses"][mes]["despesas"]

    return render_template("despesas.html", despesas=despesas)


@app.route("/add_despesa", methods=["POST"])
def add_despesa():
    dados = export_to_dict()
    mes = dados.get("mes_atual", "")

    if "meses" not in dados:
        dados["meses"] = {}

    if mes not in dados["meses"]:
        dados["meses"][mes] = {"despesas": {}}

    nome = request.form.get("nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()
    categoria = request.form.get("categoria", "").strip()

    if not nome or not valor_txt or not categoria:
        return redirect("/despesas")

    try:
        valor = float(valor_txt)
    except ValueError:
        return redirect("/despesas")

    dados["meses"][mes]["despesas"][nome] = {
        "valor": valor,
        "categoria": categoria,
        "pago": False
    }

    save_all_from_dict(dados)
    return redirect("/despesas")


@app.route("/delete_despesa/<nome>")
def delete_despesa(nome):
    dados = export_to_dict()
    mes = dados["mes_atual"]

    if nome in dados["meses"][mes]["despesas"]:
        del dados["meses"][mes]["despesas"][nome]

    save_all_from_dict(dados)
    return redirect("/despesas")


@app.route("/toggle_pago/<nome>")
def toggle_pago(nome):
    dados = export_to_dict()
    mes = dados["mes_atual"]

    d = dados["meses"][mes]["despesas"][nome]
    d["pago"] = not d.get("pago", False)

    save_all_from_dict(dados)
    return redirect("/despesas")

@app.route("/dividas")
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
def add_divida():
    dados = export_to_dict()

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
    except ValueError:
        return redirect("/dividas")

    dados.setdefault("dividas", {})
    dados["dividas"][nome] = {
        "inicial": inicial,
        "total": inicial,
        "taxa": taxa,
        "prestacao": prestacao
    }

    save_all_from_dict(dados)
    return redirect("/dividas")

@app.route("/delete_divida/<nome>")
def delete_divida(nome):
    dados = export_to_dict()

    if nome in dados.get("dividas", {}):
        del dados["dividas"][nome]
        save_all_from_dict(dados)

    return redirect("/dividas")

@app.route("/update_divida/<nome>", methods=["POST"])
def update_divida(nome):
    dados = export_to_dict()

    if nome not in dados.get("dividas", {}):
        return redirect("/dividas")

    inicial_txt = request.form.get("inicial", "").strip()
    total_txt = request.form.get("total", "").strip()
    taxa_txt = request.form.get("taxa", "").strip()
    prestacao_txt = request.form.get("prestacao", "").strip()

    try:
        inicial = float(inicial_txt)
        total = float(total_txt)
        taxa = float(taxa_txt)
        prestacao = float(prestacao_txt)
    except ValueError:
        return redirect("/dividas")

    dados["dividas"][nome] = {
        "inicial": inicial,
        "total": total,
        "taxa": taxa,
        "prestacao": prestacao
    }

    save_all_from_dict(dados)
    return redirect("/dividas")


@app.route("/pendentes")
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
def add_pendente():
    dados = export_to_dict()

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
    except ValueError:
        return redirect("/pendentes")

    dados.setdefault("pendentes", {})
    dados["pendentes"][nome] = {
        "valor_mensal": valor_mensal,
        "desde": desde,
        "notas": notas
    }

    save_all_from_dict(dados)
    return redirect("/pendentes")

@app.route("/update_pendente/<nome>", methods=["POST"])
def update_pendente(nome):
    dados = export_to_dict()

    if nome not in dados.get("pendentes", {}):
        return redirect("/pendentes")

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
    except ValueError:
        return redirect("/pendentes")

    if novo_nome != nome:
        del dados["pendentes"][nome]

    dados["pendentes"][novo_nome] = {
        "valor_mensal": valor_mensal,
        "desde": desde,
        "notas": notas
    }

    save_all_from_dict(dados)
    return redirect("/pendentes")

@app.route("/delete_pendente/<nome>")
def delete_pendente(nome):
    dados = export_to_dict()

    if nome in dados.get("pendentes", {}):
        del dados["pendentes"][nome]
        save_all_from_dict(dados)

    return redirect("/pendentes")

@app.route("/convert_pendente/<nome>")
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

    dados.setdefault("dividas", {})

    nome_divida = nome
    if nome_divida in dados["dividas"]:
        nome_divida = f"{nome} (pendente)"

    dados["dividas"][nome_divida] = {
        "inicial": total,
        "total": total,
        "taxa": 0.0,
        "prestacao": 0.0
    }

    del dados["pendentes"][nome]

    save_all_from_dict(dados)
    return redirect("/pendentes")

@app.route("/sistema")
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
def add_salario():
    dados = export_to_dict()

    nome = request.form.get("nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()

    if not nome or not valor_txt:
        return redirect("/sistema")

    try:
        valor = float(valor_txt)
    except ValueError:
        return redirect("/sistema")

    dados.setdefault("salarios", {})
    dados["salarios"][nome] = valor

    save_all_from_dict(dados)
    return redirect("/sistema")


@app.route("/update_salario/<nome>", methods=["POST"])
def update_salario(nome):
    dados = export_to_dict()

    if nome not in dados.get("salarios", {}):
        return redirect("/sistema")

    novo_nome = request.form.get("novo_nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()

    if not novo_nome or not valor_txt:
        return redirect("/sistema")

    try:
        valor = float(valor_txt)
    except ValueError:
        return redirect("/sistema")

    if novo_nome != nome:
        del dados["salarios"][nome]

    dados["salarios"][novo_nome] = valor

    save_all_from_dict(dados)
    return redirect("/sistema")


@app.route("/delete_salario/<nome>")
def delete_salario(nome):
    dados = export_to_dict()

    if nome in dados.get("salarios", {}):
        del dados["salarios"][nome]
        save_all_from_dict(dados)

    return redirect("/sistema")

@app.route("/add_contribuicao", methods=["POST"])
def add_contribuicao():
    dados = export_to_dict()

    nome = request.form.get("nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()

    if not nome or not valor_txt:
        return redirect("/sistema")

    try:
        valor = float(valor_txt)
    except ValueError:
        return redirect("/sistema")

    dados.setdefault("contribuicoes", {})
    dados["contribuicoes"][nome] = valor

    save_all_from_dict(dados)
    return redirect("/sistema")


@app.route("/update_contribuicao/<nome>", methods=["POST"])
def update_contribuicao(nome):
    dados = export_to_dict()

    if nome not in dados.get("contribuicoes", {}):
        return redirect("/sistema")

    novo_nome = request.form.get("novo_nome", "").strip()
    valor_txt = request.form.get("valor", "").strip()

    if not novo_nome or not valor_txt:
        return redirect("/sistema")

    try:
        valor = float(valor_txt)
    except ValueError:
        return redirect("/sistema")

    if novo_nome != nome:
        del dados["contribuicoes"][nome]

    dados["contribuicoes"][novo_nome] = valor

    save_all_from_dict(dados)
    return redirect("/sistema")


@app.route("/delete_contribuicao/<nome>")
def delete_contribuicao(nome):
    dados = export_to_dict()

    if nome in dados.get("contribuicoes", {}):
        del dados["contribuicoes"][nome]
        save_all_from_dict(dados)

    return redirect("/sistema")

@app.route("/add_categoria", methods=["POST"])
def add_categoria():
    dados = export_to_dict()

    nome = request.form.get("nome", "").strip()
    if not nome:
        return redirect("/sistema")

    dados.setdefault("categorias", [])
    if nome not in dados["categorias"]:
        dados["categorias"].append(nome)
        dados["categorias"].sort()

    save_all_from_dict(dados)
    return redirect("/sistema")


@app.route("/delete_categoria/<nome>")
def delete_categoria(nome):
    dados = export_to_dict()

    if nome in dados.get("categorias", []):
        dados["categorias"].remove(nome)
        save_all_from_dict(dados)

    return redirect("/sistema")

@app.route("/planeamento")
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

if __name__ == "__main__":
    app.run(debug=True)