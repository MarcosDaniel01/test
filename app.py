from flask import Flask, request, render_template_string, redirect, session, send_file
import psycopg2
import pandas as pd
import os
from datetime import datetime, timedelta
import io

app = Flask(__name__)
app.secret_key = "123456"

DATABASE_URL = os.getenv("DATABASE_URL")

def conectar():
    return psycopg2.connect(DATABASE_URL)

def criar_tabelas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        usuario TEXT UNIQUE,
        senha TEXT,
        tipo TEXT
    )
    """)

    cur.execute("""
    INSERT INTO usuarios (usuario, senha, tipo)
    VALUES ('admin','123','admin')
    ON CONFLICT (usuario) DO NOTHING
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimentacoes (
        id SERIAL PRIMARY KEY,
        produto TEXT,
        tipo TEXT,
        operacao TEXT,
        quantidade INTEGER,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# ===================== HTML =====================

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Estoque SaaS</title>
<style>
body {font-family: Arial; background:#eef1f5;}
.container {width:90%; margin:auto;}
.card {background:white; padding:20px; margin:10px; border-radius:12px; box-shadow:0 2px 5px rgba(0,0,0,0.1);}
button {padding:10px; border:none; background:#4CAF50; color:white; border-radius:6px; cursor:pointer;}
input, select {padding:8px; margin:5px;}
.top {display:flex; justify-content:space-between; align-items:center;}
.logout {background:red;}
</style>
</head>
<body>

<div class="container">

<div class="top">
<h2>📦 Sistema de Estoque</h2>
<a href="/logout"><button class="logout">Sair</button></a>
</div>

<div class="card">
<form method="post" action="/mov">
Produto: <input name="produto" required>
Tipo:
<select name="tipo">
<option>Prime</option>
<option>Link</option>
<option>Neo</option>
<option>Fitmoby</option>
</select>
Quantidade: <input name="quantidade" type="number" required>

<button name="operacao" value="entrada">Entrada</button>
<button name="operacao" value="saida">Saída</button>
</form>
</div>

<div class="card">
<h3>📊 Estoque Atual</h3>
{{tabela|safe}}
</div>

<div class="card">
<h3>🧠 Previsão Inteligente</h3>
{{previsao|safe}}
</div>

<div class="card">
<h3>🔔 Alertas</h3>
{{alertas|safe}}
</div>

<div class="card">
<a href="/excel"><button>📥 Exportar Excel</button></a>
</div>

</div>

</body>
</html>
"""

LOGIN = """
<h2>🔐 Login</h2>
<form method="post">
Usuário: <input name="usuario"><br><br>
Senha: <input type="password" name="senha"><br><br>
<button>Entrar</button>
</form>
"""

# ===================== ROTAS =====================

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        conn = conectar()
        df = pd.read_sql("SELECT * FROM usuarios", conn)

        user = df[(df.usuario==u) & (df.senha==s)]

        if not user.empty:
            session["user"] = u
            return redirect("/sistema")

    return render_template_string(LOGIN)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacoes", conn)

    if df.empty:
        return render_template_string(HTML, tabela="Sem dados", previsao="", alertas="")

    # cálculo estoque
    df["q"] = df.apply(lambda x: x["quantidade"] if x["operacao"]=="entrada" else -x["quantidade"], axis=1)
    estoque = df.groupby(["produto","tipo"])["q"].sum().reset_index()
    tabela = estoque.to_html(index=False)

    # previsão IA
    df["data"] = pd.to_datetime(df["data"])
    limite = datetime.now() - timedelta(days=90)
    df2 = df[df["data"] >= limite]

    lista_prev = []
    lista_alerta = []

    for p in df2["produto"].unique():
        d = df2[df2["produto"]==p]
        saida = d[d["operacao"]=="saida"]["quantidade"].sum()
        dias = (datetime.now() - d["data"].min()).days or 1
        media = saida/dias if dias else 0
        total = d["q"].sum()
        dias_rest = int(total/media) if media>0 else 999

        status = "🔴 CRÍTICO" if dias_rest < 7 else "🟢 OK"

        lista_prev.append(f"{p} → {dias_rest} dias ({status})<br>")

        if total < 10:
            lista_alerta.append(f"⚠ Estoque baixo: {p} ({total})<br>")

    previsao_html = "".join(lista_prev)
    alertas_html = "".join(lista_alerta)

    return render_template_string(HTML, tabela=tabela, previsao=previsao_html, alertas=alertas_html)

@app.route("/mov", methods=["POST"])
def mov():
    if "user" not in session:
        return redirect("/")

    data = request.form
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO movimentacoes (produto, tipo, operacao, quantidade)
    VALUES (%s,%s,%s,%s)
    """,(data["produto"], data["tipo"], data["operacao"], data["quantidade"]))

    conn.commit()
    conn.close()

    return redirect("/sistema")

@app.route("/excel")
def excel():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacoes", conn)

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name="relatorio.xlsx", as_attachment=True)

# ===================== START =====================

if __name__ == "__main__":
    criar_tabelas()
    app.run(host="0.0.0.0", port=10000)