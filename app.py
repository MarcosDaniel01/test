from flask import Flask, render_template_string, request, redirect, send_file
import pandas as pd
import os

app = Flask(__name__)

ARQUIVO = "estoque.xlsx"

GERENCIADORAS = ["Prime", "Fitmoby", "Outros"]

# =========================
# CRIAR BASE INICIAL
# =========================
def iniciar_base():
    if not os.path.exists(ARQUIVO):
        df = pd.DataFrame(columns=[
            "Gerenciadora",
            "Item",
            "Entrada",
            "Saida",
            "Saldo",
            "Previsao_6_meses"
        ])
        df.to_excel(ARQUIVO, index=False)

# =========================
# CARREGAR BASE
# =========================
def carregar():
    iniciar_base()
    return pd.read_excel(ARQUIVO)

# =========================
# SALVAR BASE
# =========================
def salvar(df):
    df.to_excel(ARQUIVO, index=False)

# =========================
# CALCULAR PREVISÃO
# =========================
def calcular_previsao(saida):
    try:
        media_mensal = float(saida)
        return round(media_mensal * 6, 2)
    except:
        return 0

# =========================
# HOME
# =========================
@app.route("/", methods=["GET", "POST"])
def index():
    df = carregar()

    if request.method == "POST":
        try:
            ger = request.form["gerenciadora"].strip().title()
            item = request.form["item"].strip().title()

            if item == "":
                return "ERRO: Nome do item obrigatório"

            entrada = int(request.form.get("entrada", 0))
            saida = int(request.form.get("saida", 0))

            saldo = entrada - saida
            previsao = calcular_previsao(saida)

            novo = pd.DataFrame([{
                "Gerenciadora": ger,
                "Item": item,
                "Entrada": entrada,
                "Saida": saida,
                "Saldo": saldo,
                "Previsao_6_meses": previsao
            }])

            df = pd.concat([df, novo], ignore_index=True)

            salvar(df)

            return redirect("/")

        except Exception as e:
            return f"Erro ao salvar: {e}"

    # AGRUPAR POR GERENCIADORA
    grupos = df.groupby("Gerenciadora")

    html = """
    <html>
    <head>
    <title>Controle de Estoque</title>
    <style>
        body { font-family: Arial; background:#f4f6f9; padding:20px; }
        h2 { color:#333; }
        .box {
            background:white;
            padding:15px;
            margin-bottom:20px;
            border-radius:10px;
            box-shadow:0 2px 5px rgba(0,0,0,0.1);
        }
        table {
            width:100%;
            border-collapse: collapse;
        }
        th, td {
            padding:8px;
            border-bottom:1px solid #ddd;
            text-align:center;
        }
        th {
            background:#007bff;
            color:white;
        }
        input, select {
            padding:8px;
            margin:5px;
        }
        button {
            padding:10px;
            background:#28a745;
            color:white;
            border:none;
            cursor:pointer;
        }
    </style>
    </head>

    <body>

    <h2>📦 Controle de Estoque Inteligente</h2>

    <div class="box">
    <form method="POST">
        <select name="gerenciadora" required>
            {% for g in gerenciadoras %}
            <option value="{{g}}">{{g}}</option>
            {% endfor %}
        </select>

        <input name="item" placeholder="Nome do Item" required>
        <input name="entrada" type="number" placeholder="Entrada">
        <input name="saida" type="number" placeholder="Saída">

        <button type="submit">Adicionar</button>
    </form>
    </div>

    {% for nome, grupo in grupos %}
    <div class="box">
        <h3>{{nome}}</h3>

        <table>
            <tr>
                <th>Item</th>
                <th>Entrada</th>
                <th>Saída</th>
                <th>Saldo</th>
                <th>6 Meses</th>
            </tr>

            {% for i, row in grupo.iterrows() %}
            <tr>
                <td>{{row["Item"]}}</td>
                <td>{{row["Entrada"]}}</td>
                <td>{{row["Saida"]}}</td>
                <td>{{row["Saldo"]}}</td>
                <td>{{row["Previsao_6_meses"]}}</td>
            </tr>
            {% endfor %}
        </table>

        <br>
        <a href="/exportar/{{nome}}">
            <button>Exportar Excel</button>
        </a>
    </div>
    {% endfor %}

    </body>
    </html>
    """

    return render_template_string(html,
        grupos=grupos,
        gerenciadoras=GERENCIADORAS
    )

# =========================
# EXPORTAR POR GERENCIADORA
# =========================
@app.route("/exportar/<ger>")
def exportar(ger):
    df = carregar()
    filtrado = df[df["Gerenciadora"] == ger]

    nome_arquivo = f"{ger}_estoque.xlsx"
    filtrado.to_excel(nome_arquivo, index=False)

    return send_file(nome_arquivo, as_attachment=True)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
