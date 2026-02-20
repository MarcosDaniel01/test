from flask import Flask, request, jsonify, render_template_string, redirect, session, send_file
import psycopg2
import os
from datetime import datetime, timedelta
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# CONEXÃO
# ===============================
def conectar():
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except:
        return None

# ===============================
# CRIAR TABELAS
# ===============================
def criar_tabelas():
    conn = conectar()
    if conn is None: return
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
    CREATE TABLE IF NOT EXISTS movimentacoes (
        id SERIAL PRIMARY KEY,
        produto TEXT,
        gerenciadora TEXT,
        tipo TEXT,
        quantidade INTEGER,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

# ===============================
# LOGIN
# ===============================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT tipo FROM usuarios WHERE usuario=%s AND senha=%s",(u,s))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = u
            session["tipo"] = user[0]
            return redirect("/")
        else:
            return "Login inválido"

    return '''
    <form method="post">
    <input name="usuario">
    <input name="senha" type="password">
    <button>Entrar</button>
    </form>
    '''

# ===============================
# HOME
# ===============================
@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")

    return render_template_string("""
    <html>
    <head>
    <style>
    body{background:#0f172a;color:white;font-family:Arial;text-align:center}
    .card{background:#1e293b;margin:20px;padding:20px;border-radius:10px}
    input,select,button{padding:10px;margin:5px}
    </style>
    </head>

    <body>

    <h1>📦 Estoque Inteligente</h1>

    <div class="card">
        <h3>Movimentação</h3>
        <input id="produto" placeholder="PRODUTO">
        <input id="qtd" type="number">
        <select id="tipo">
            <option>ENTRADA</option>
            <option>SAIDA</option>
        </select>
        <select id="ger">
            <option>PRIME</option>
            <option>LINK</option>
            <option>NEO</option>
            <option>FITMOBY</option>
            <option>OUTROS</option>
        </select>
        <button onclick="mov()">Salvar</button>
    </div>

    <div class="card">
        <h3>📊 Estoque</h3>
        <button onclick="carregar()">Atualizar</button>
        <div id="estoque"></div>
    </div>

    <div class="card">
        <h3>📈 Previsão 6 meses</h3>
        <button onclick="previsao()">Ver</button>
        <pre id="prev"></pre>
    </div>

    <div class="card">
        <h3>📥 Exportar</h3>
        <a href="/exportar_excel"><button>Baixar Excel</button></a>
    </div>

<script>
async function mov(){
    let produto = document.getElementById("produto").value

    if(produto !== produto.toUpperCase()){
        alert("Use MAIÚSCULO")
        return
    }

    await fetch("/mov",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
            produto:produto,
            qtd:document.getElementById("qtd").value,
            tipo:document.getElementById("tipo").value,
            ger:document.getElementById("ger").value
        })
    })

    alert("OK")
}

async function carregar(){
    let r = await fetch("/estoque_excel")
    let t = await r.text()
    document.getElementById("estoque").innerHTML = t
}

async function previsao(){
    let r = await fetch("/previsao")
    let t = await r.json()
    document.getElementById("prev").innerText = JSON.stringify(t,null,2)
}
</script>

    </body>
    </html>
    """)

# ===============================
# MOVIMENTAÇÃO (SEM DUPLICAR)
# ===============================
@app.route("/mov", methods=["POST"])
def mov():
    data = request.json

    item = data["produto"]
    if item != item.upper():
        return "ERRO: use maiúsculo"

    ger = data["ger"].upper()

    if ger not in GERENCIADORAS:
        return "Gerenciadora inválida"

    # bloqueio (exceto OUTROS)
    if ger != "OUTROS":
        for g in GERENCIADORAS:
            if g in item:
                return "Não usar nome da gerenciadora no item"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO movimentacoes (produto,gerenciadora,tipo,quantidade)
        VALUES (%s,%s,%s,%s)
    """,(item,ger,data["tipo"],int(data["qtd"])))

    conn.commit()
    conn.close()

    return "ok"

# ===============================
# ESTOQUE ORGANIZADO
# ===============================
@app.route("/estoque_excel")
def estoque_excel():
    conn = conectar()

    df = pd.read_sql("""
        SELECT produto, gerenciadora,
        SUM(CASE WHEN tipo='ENTRADA' THEN quantidade ELSE 0 END) entrada,
        SUM(CASE WHEN tipo='SAIDA' THEN quantidade ELSE 0 END) saida
        FROM movimentacoes
        GROUP BY produto, gerenciadora
        ORDER BY gerenciadora
    """, conn)

    if df.empty:
        return "Sem dados"

    df["saldo"] = df["entrada"] - df["saida"]

    html = ""

    for g in GERENCIADORAS:
        sub = df[df["gerenciadora"] == g]
        if not sub.empty:
            html += f"<h2>{g}</h2>"
            html += sub.to_html(index=False)

    conn.close()
    return html

# ===============================
# PREVISÃO IA (6 MESES)
# ===============================
@app.route("/previsao")
def previsao():
    conn = conectar()

    df = pd.read_sql("""
        SELECT produto, DATE_TRUNC('month', data) mes,
        SUM(quantidade) as total
        FROM movimentacoes
        WHERE tipo='SAIDA'
        GROUP BY produto, mes
    """, conn)

    resultado = {}

    for p in df["produto"].unique():
        media = df[df["produto"]==p]["total"].mean()
        resultado[p] = round(media * 6)

    conn.close()
    return jsonify(resultado)

# ===============================
# EXPORTAR EXCEL
# ===============================
@app.route("/exportar_excel")
def exportar_excel():
    conn = conectar()

    df = pd.read_sql("""
        SELECT produto, gerenciadora,
        SUM(CASE WHEN tipo='ENTRADA' THEN quantidade ELSE 0 END) entrada,
        SUM(CASE WHEN tipo='SAIDA' THEN quantidade ELSE 0 END) saida
        FROM movimentacoes
        GROUP BY produto, gerenciadora
    """, conn)

    df["saldo"] = df["entrada"] - df["saida"]

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for g in GERENCIADORAS:
            sub = df[df["gerenciadora"] == g]
            if not sub.empty:
                sub.to_excel(writer, sheet_name=g, index=False)

    output.seek(0)
    conn.close()

    return send_file(output, download_name="estoque.xlsx", as_attachment=True)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar_tabelas()
    app.run(host="0.0.0.0", port=10000)
