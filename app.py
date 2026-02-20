from flask import Flask, request, jsonify, render_template_string, redirect, session
import psycopg2
import os
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__)
app.secret_key = "segredo_empresa"

DATABASE_URL = os.getenv("DATABASE_URL")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# CONEXÃO SEGURA
# ===============================
def conectar():
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as e:
        print("ERRO DB:", e)
        return None

# ===============================
# CRIAR TABELAS
# ===============================
def criar_tabelas():
    conn = conectar()
    if not conn:
        return
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
    CREATE TABLE IF NOT EXISTS estoque (
        produto TEXT PRIMARY KEY,
        quantidade INTEGER,
        gerenciadora TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimentacoes (
        id SERIAL PRIMARY KEY,
        produto TEXT,
        tipo TEXT,
        quantidade INTEGER,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # cria admin padrão
    cur.execute("SELECT * FROM usuarios WHERE usuario='ADMIN'")
    if not cur.fetchone():
        cur.execute("INSERT INTO usuarios VALUES (DEFAULT,'ADMIN','123','admin')")

    conn.commit()
    cur.close()
    conn.close()

# ===============================
# VALIDAÇÃO MAIÚSCULA
# ===============================
def validar_maiusculo(texto):
    return texto == texto.upper()

# ===============================
# LOGIN
# ===============================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form["user"].upper()
        senha = request.form["senha"]

        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT tipo FROM usuarios WHERE usuario=%s AND senha=%s",(user,senha))
        res = cur.fetchone()

        if res:
            session["user"] = user
            session["tipo"] = res[0]
            return redirect("/")

        return "Login inválido"

    return """
    <h2>Login</h2>
    <form method="post">
    <input name="user" placeholder="USUARIO"><br>
    <input name="senha" type="password"><br>
    <button>Entrar</button>
    </form>
    """

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
    body { background:#0f172a; color:white; font-family:Arial;}
    .box { background:#1e293b; padding:20px; margin:20px; border-radius:10px;}
    input, select { padding:10px; margin:5px;}
    button { padding:10px; background:#22c55e; border:none;}
    </style>
    </head>

    <body>

    <h1>🚀 Sistema Empresarial</h1>

    <div class="box">
    <h2>Movimentação</h2>
    <input id="produto" placeholder="PRODUTO">
    <input id="qtd" type="number" placeholder="Quantidade">

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

    <div class="box">
    <h2>Estoque (planilha)</h2>
    <button onclick="carregar()">Atualizar</button>
    <pre id="dados"></pre>
    </div>

    <div class="box">
    <h2>Previsão 6 meses (IA)</h2>
    <button onclick="previsao()">Gerar</button>
    <pre id="prev"></pre>
    </div>

    <div class="box">
    <h2>Relatório</h2>
    <a href="/excel">Baixar Excel</a>
    </div>

    <script>
    async function mov(){
        await fetch('/mov', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
                produto:produto.value,
                quantidade:qtd.value,
                tipo:tipo.value,
                gerenciadora:ger.value
            })
        })
        alert("Salvo")
    }

    async function carregar(){
        let r = await fetch('/estoque')
        let d = await r.json()
        dados.innerText = JSON.stringify(d,null,2)
    }

    async function previsao(){
        let r = await fetch('/previsao')
        let d = await r.json()
        prev.innerText = JSON.stringify(d,null,2)
    }
    </script>

    </body>
    </html>
    """)

# ===============================
# MOVIMENTAÇÃO (ENTRADA/SAIDA)
# ===============================
@app.route("/mov", methods=["POST"])
def mov():
    data = request.json

    produto = data["produto"].upper()

    if not validar_maiusculo(produto):
        return "USE MAIÚSCULO"

    qtd = int(data["quantidade"])
    tipo = data["tipo"]
    ger = data["gerenciadora"].upper()

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT quantidade FROM estoque WHERE produto=%s",(produto,))
    res = cur.fetchone()

    if res:
        nova_qtd = res[0] + qtd if tipo == "ENTRADA" else res[0] - qtd
        cur.execute("UPDATE estoque SET quantidade=%s WHERE produto=%s",(nova_qtd,produto))
    else:
        cur.execute("INSERT INTO estoque VALUES (%s,%s,%s)",(produto,qtd,ger))

    cur.execute("INSERT INTO movimentacoes (produto,tipo,quantidade) VALUES (%s,%s,%s)",
                (produto,tipo,qtd))

    conn.commit()
    cur.close()
    conn.close()

    return "OK"

# ===============================
# ESTOQUE
# ===============================
@app.route("/estoque")
def estoque():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM estoque")
    dados = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(dados)

# ===============================
# PREVISÃO IA (6 MESES)
# ===============================
@app.route("/previsao")
def previsao():
    conn = conectar()

    try:
        df = pd.read_sql("SELECT * FROM movimentacoes WHERE tipo='SAIDA'", conn)
    except:
        return jsonify({"erro":"sem dados"})

    if df.empty:
        return jsonify({"msg":"sem histórico"})

    media = df.groupby("produto")["quantidade"].mean()

    previsao = {}
    for p in media.index:
        previsao[p] = round(media[p] * 6, 2)

    return jsonify(previsao)

# ===============================
# EXCEL
# ===============================
@app.route("/excel")
def excel():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacoes", conn)

    arquivo = "relatorio.xlsx"
    df.to_excel(arquivo, index=False)

    return open(arquivo,"rb").read()

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar_tabelas()
    app.run(host="0.0.0.0", port=10000)
