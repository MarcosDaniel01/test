from flask import Flask, request, jsonify, render_template_string, redirect, session, send_file
import psycopg2
import os
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
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# ===============================
# CRIAR TABELAS
# ===============================
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
    <input name="usuario" placeholder="usuario">
    <input name="senha" type="password" placeholder="senha">
    <button>Entrar</button>
    </form>
    '''

# ===============================
# HOME (INTERFACE)
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
    table{width:100%;background:white;color:black}
    </style>
    </head>

    <body>

    <h1>📦 ESTOQUE INTELIGENTE</h1>

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
        <h3>📊 ESTOQUE</h3>
        <button onclick="carregar()">Atualizar</button>
        <div id="estoque"></div>
    </div>

    <div class="card">
        <h3>📥 Exportar Excel</h3>
        <a href="/exportar_excel"><button>Baixar</button></a>
    </div>

<script>
async function mov(){
    let produto = document.getElementById("produto").value

    if(produto !== produto.toUpperCase()){
        alert("APENAS MAIÚSCULO")
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

    alert("SALVO")
}

async function carregar(){
    let r = await fetch("/estoque_excel")
    let t = await r.text()
    document.getElementById("estoque").innerHTML = t
}
</script>

    </body>
    </html>
    """)

# ===============================
# MOVIMENTAÇÃO (INTELIGENTE)
# ===============================
@app.route("/mov", methods=["POST"])
def mov():
    data = request.json

    produto = data["produto"]
    if produto != produto.upper():
        return "ERRO: MAIÚSCULO"

    ger = data["ger"].upper()

    if ger not in GERENCIADORAS:
        return "Gerenciadora inválida"

    # bloquear nome da gerenciadora no item
    if ger != "OUTROS":
        for g in GERENCIADORAS:
            if g in produto:
                return "Produto não pode conter gerenciadora"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO movimentacoes (produto,gerenciadora,tipo,quantidade)
        VALUES (%s,%s,%s,%s)
    """,(produto,ger,data["tipo"],int(data["qtd"])))

    conn.commit()
    conn.close()

    return "ok"

# ===============================
# ESTOQUE (PLANILHA COMPLETA)
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
        ORDER BY gerenciadora, produto
    """, conn)

    if df.empty:
        return "Sem dados"

    df["saldo"] = df["entrada"] - df["saida"]

    # PREVISÃO
    df_saida = pd.read_sql("""
        SELECT produto,
        DATE_TRUNC('month', data) mes,
        SUM(quantidade) total
        FROM movimentacoes
        WHERE tipo='SAIDA'
        GROUP BY produto, mes
    """, conn)

    previsao = {}
    for p in df_saida["produto"].unique():
        media = df_saida[df_saida["produto"]==p]["total"].mean()
        previsao[p] = round(media * 6)

    df["previsao_6m"] = df["produto"].map(previsao).fillna(0)

    df["status"] = df.apply(lambda r: "⚠️ BAIXO" if r["saldo"] <= r["previsao_6m"] else "✅ OK", axis=1)

    html = """
    <h2>📊 ESTOQUE GERAL</h2>
    <table border="1">
    <tr>
    <th>GERENCIADORA</th>
    <th>PRODUTO</th>
    <th>ENTRADA</th>
    <th>SAIDA</th>
    <th>SALDO</th>
    <th>PREVISÃO 6M</th>
    <th>STATUS</th>
    </tr>
    """

    for g in GERENCIADORAS:
        sub = df[df["gerenciadora"] == g]
        for _, r in sub.iterrows():
            html += f"""
            <tr>
            <td><b>{g}</b></td>
            <td>{r['produto']}</td>
            <td>{r['entrada']}</td>
            <td>{r['saida']}</td>
            <td>{r['saldo']}</td>
            <td>{r['previsao_6m']}</td>
            <td>{r['status']}</td>
            </tr>
            """

    html += "</table>"
    conn.close()
    return html

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
