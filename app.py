from flask import Flask, request, redirect, session, send_file
import psycopg2
import os
from datetime import datetime
import pandas as pd

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# CONEXÃO POSTGRES (PERMANENTE)
# ===============================
def conectar():
    return psycopg2.connect(DATABASE_URL)

# ===============================
# CRIAR TABELAS
# ===============================
def criar():
    conn = conectar()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        usuario TEXT PRIMARY KEY,
        senha TEXT,
        tipo TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS movimentacao(
        data TIMESTAMP,
        gerenciadora TEXT,
        tipo TEXT,
        item TEXT,
        quantidade INTEGER
    )
    """)

    conn.commit()
    conn.close()

# ===============================
# LOGIN
# ===============================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE usuario=%s AND senha=%s", (u,s))
        user = c.fetchone()
        conn.close()

        if user:
            session["user"] = u
            session["tipo"] = user[2]
            return redirect("/sistema")

    return """
    <h2>Login</h2>
    <form method="post">
    <input name="usuario" placeholder="Usuario"><br>
    <input name="senha" type="password"><br>
    <button>Entrar</button>
    </form>
    """

# ===============================
# SISTEMA
# ===============================
@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    dados = calcular()

    grupos = {g: [] for g in GERENCIADORAS}
    for d in dados:
        grupos[d["ger"]].append(d)

    html = """
    <html>
    <head>
    <style>
    body{font-family:Arial;background:#0f172a;color:white;text-align:center;}
    table{width:95%;margin:20px auto;border-collapse:collapse;background:white;color:black;}
    th,td{padding:8px;border:1px solid #ccc;}
    th{background:black;color:white;}
    .PRIME{background:#22c55e;padding:10px;}
    .LINK{background:#3b82f6;padding:10px;}
    .NEO{background:#14b8a6;padding:10px;}
    .FITMOBY{background:#a855f7;padding:10px;}
    .OUTROS{background:#f97316;padding:10px;}
    form{background:#1e293b;padding:20px;width:400px;margin:auto;border-radius:10px;}
    button{background:#22c55e;color:white;padding:10px;width:100%;}
    input,select{padding:10px;margin:5px;width:95%;}
    </style>
    </head>
    <body>

    <h1>🚀 ESTOQUE INTELIGENTE PRO</h1>

    <form method="POST" action="/inserir">
    <select name="ger">
    <option>PRIME</option>
    <option>LINK</option>
    <option>NEO</option>
    <option>FITMOBY</option>
    <option>OUTROS</option>
    </select>

    <select name="tipo">
    <option>ENTRADA</option>
    <option>SAIDA</option>
    </select>

    <input name="item" placeholder="ITEM (MAIÚSCULO)" required>
    <input name="qtd" type="number" required>

    <button>SALVAR</button>
    </form>

    <br>
    <a href="/excel">📊 EXPORTAR EXCEL</a><br><br>
    """

    if session["tipo"] == "admin":
        html += """
        <form method="POST" action="/criar_usuario">
        <h3>Criar Operador</h3>
        <input name="usuario" placeholder="Usuario">
        <input name="senha" placeholder="Senha">
        <button>Criar</button>
        </form>

        <br>
        <a href="/backup">💾 BACKUP</a><br><br>
        """

    for nome, lista in grupos.items():
        html += f"<div class='{nome}'><b>{nome}</b></div>"
        html += """
        <table>
        <tr>
        <th>ITEM</th><th>ENTRADA</th><th>SAIDA</th>
        <th>SALDO</th><th>MÉDIA</th><th>6M+20%</th><th>STATUS</th>
        </tr>
        """

        for d in lista:
            cor = "red" if d["saldo"] < d["proj"] else "black"

            html += f"""
            <tr>
            <td>{d['item']}</td>
            <td>{d['entrada']}</td>
            <td>{d['saida']}</td>
            <td style='color:{cor}'>{d['saldo']}</td>
            <td>{d['media']}</td>
            <td>{d['proj']}</td>
            <td>{d['status']}</td>
            </tr>
            """

        html += "</table>"

    html += "</body></html>"
    return html

# ===============================
# INSERIR
# ===============================
@app.route("/inserir", methods=["POST"])
def inserir():
    ger = request.form["ger"].upper()
    tipo = request.form["tipo"].upper()
    item = request.form["item"]
    qtd = int(request.form["qtd"])

    if item != item.upper():
        return "ERRO: USE MAIÚSCULO"

    for g in GERENCIADORAS:
        if g in item:
            return f"ERRO: NÃO USAR {g}"

    conn = conectar()
    c = conn.cursor()

    c.execute("INSERT INTO movimentacao VALUES (%s,%s,%s,%s,%s)",
              (datetime.now(), ger, tipo, item, qtd))

    conn.commit()
    conn.close()

    return redirect("/sistema")

# ===============================
# IA CALCULO
# ===============================
def calcular():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM movimentacao", conn)
    conn.close()

    if df.empty:
        return []

    resultado = []

    for (ger, item), grupo in df.groupby(["gerenciadora","item"]):
        entrada = grupo[grupo["tipo"]=="ENTRADA"]["quantidade"].sum()
        saida = grupo[grupo["tipo"]=="SAIDA"]["quantidade"].sum()

        entrada = entrada or 0
        saida = saida or 0

        saldo = entrada - saida

        meses = max(len(pd.to_datetime(grupo["data"]).dt.to_period("M").unique()),1)
        media = saida / meses

        proj = int((media * 6) * 1.2)

        status = "OK" if saldo >= proj else "COMPRAR"

        resultado.append({
            "ger": ger,
            "item": item,
            "entrada": int(entrada),
            "saida": int(saida),
            "saldo": int(saldo),
            "media": int(media),
            "proj": int(proj),
            "status": status
        })

    return resultado

# ===============================
# CRIAR OPERADOR
# ===============================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session["tipo"] != "admin":
        return "SEM PERMISSÃO"

    u = request.form["usuario"]
    s = request.form["senha"]

    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO usuarios VALUES (%s,%s,'operador') ON CONFLICT DO NOTHING", (u,s))
    conn.commit()
    conn.close()

    return redirect("/sistema")

# ===============================
# BACKUP
# ===============================
@app.route("/backup")
def backup():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM movimentacao", conn)
    conn.close()

    df.to_excel("backup.xlsx", index=False)
    return send_file("backup.xlsx", as_attachment=True)

# ===============================
# EXCEL
# ===============================
@app.route("/excel")
def excel():
    dados = calcular()
    df = pd.DataFrame(dados)
    df.to_excel("estoque.xlsx", index=False)
    return send_file("estoque.xlsx", as_attachment=True)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar()

    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO usuarios VALUES (%s,%s,'admin') ON CONFLICT DO NOTHING", ("admin","123"))
    conn.commit()
    conn.close()

    app.run(host="0.0.0.0", port=10000)
