from flask import Flask, request, redirect, session, send_file
import sqlite3
from datetime import datetime
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "segredo"

DB = "estoque.db"

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ================= BANCO =================
def conectar():
    return sqlite3.connect(DB)

def criar():
    conn = conectar()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios(
        usuario TEXT PRIMARY KEY,
        senha TEXT,
        tipo TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS movimentacao(
        data TEXT,
        gerenciadora TEXT,
        tipo TEXT,
        item TEXT,
        quantidade INTEGER
    )""")

    conn.commit()
    conn.close()

# ================= LOGIN =================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE usuario=? AND senha=?", (u,s))
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

# ================= SISTEMA =================
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
    body{font-family:Arial;background:#111;color:white;text-align:center;}
    table{width:95%;margin:20px auto;border-collapse:collapse;background:#222;}
    th,td{padding:10px;border:1px solid #444;}
    th{background:black;}
    .PRIME{background:#2e7d32;padding:10px;}
    .LINK{background:#1565c0;padding:10px;}
    .NEO{background:#00897b;padding:10px;}
    .FITMOBY{background:#6a1b9a;padding:10px;}
    .OUTROS{background:#ef6c00;padding:10px;}
    form{background:#222;padding:20px;width:400px;margin:auto;border-radius:10px;}
    input,select{width:100%;padding:8px;margin:5px;}
    button{background:green;color:white;padding:10px;width:100%;}
    </style>
    </head>
    <body>

    <h1>📦 ESTOQUE INTELIGENTE</h1>

    <form method="POST" action="/inserir">
    <select name="ger">
    """ + "".join([f"<option>{g}</option>" for g in GERENCIADORAS]) + """
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
    <a href="/excel">📊 Excel</a> |
    <a href="/backup">💾 Backup</a> |
    <a href="/novo_usuario">👤 Novo Usuário</a>
    """

    for nome, lista in grupos.items():
        html += f"<div class='{nome}'>{nome}</div><table>"
        html += "<tr><th>ITEM</th><th>ENT</th><th>SAI</th><th>SALDO</th><th>MÉDIA</th><th>6M+20%</th><th>STATUS</th></tr>"

        for d in lista:
            cor = "red" if d["saldo"] < d["proj"] else "white"

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

# ================= INSERIR =================
@app.route("/inserir", methods=["POST"])
def inserir():
    ger = request.form["ger"].upper()
    tipo = request.form["tipo"].upper()
    item = request.form["item"]
    qtd = int(request.form["qtd"])

    if item != item.upper():
        return "ERRO: Apenas MAIÚSCULO"

    if ger != "OUTROS":
        for g in GERENCIADORAS:
            if g in item:
                return "ERRO: não usar gerenciadora no nome"

    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO movimentacao VALUES (?,?,?,?,?)",
              (datetime.now(), ger, tipo, item, qtd))
    conn.commit()
    conn.close()

    return redirect("/sistema")

# ================= IA =================
def calcular():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacao", conn)
    conn.close()

    if df.empty:
        return []

    df["data"] = pd.to_datetime(df["data"])
    df["mes"] = df["data"].dt.to_period("M")

    resultado = []

    for (ger, item), grupo in df.groupby(["gerenciadora","item"]):
        entrada = grupo[grupo["tipo"]=="ENTRADA"]["quantidade"].sum()
        saida = grupo[grupo["tipo"]=="SAIDA"]["quantidade"].sum()

        saldo = entrada - saida
        media = saida / max(len(grupo["mes"].unique()),1)

        proj = int(media * 6 * 1.2)  # +20%

        status = "OK"
        if saldo < proj:
            status = "COMPRAR"

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

# ================= EXCEL =================
@app.route("/excel")
def excel():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacao", conn)
    conn.close()

    df["data"] = pd.to_datetime(df["data"])
    df["mes"] = df["data"].dt.to_period("M").astype(str)

    estoque = calcular()
    df_estoque = pd.DataFrame(estoque)

    mensal = df.groupby(["gerenciadora","item","mes","tipo"])["quantidade"].sum().reset_index()

    nome = "estoque.xlsx"

    with pd.ExcelWriter(nome, engine="xlsxwriter") as writer:
        df_estoque.to_excel(writer, sheet_name="ESTOQUE", index=False)
        mensal.to_excel(writer, sheet_name="MENSAL", index=False)

    return send_file(nome, as_attachment=True)

# ================= ADMIN =================
@app.route("/novo_usuario", methods=["GET","POST"])
def novo():
    if session.get("tipo") != "admin":
        return "Acesso negado"

    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]
        t = request.form["tipo"]

        conn = conectar()
        c = conn.cursor()
        c.execute("INSERT INTO usuarios VALUES (?,?,?)",(u,s,t))
        conn.commit()
        conn.close()

        return redirect("/sistema")

    return """
    <form method="post">
    <input name="usuario">
    <input name="senha">
    <select name="tipo">
    <option>admin</option>
    <option>operador</option>
    </select>
    <button>Criar</button>
    </form>
    """

# ================= BACKUP =================
@app.route("/backup")
def backup():
    if session.get("tipo") != "admin":
        return "Acesso negado"

    return send_file(DB, as_attachment=True)

# ================= START =================
if __name__ == "__main__":
    criar()

    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO usuarios VALUES ('admin','123','admin')")
    conn.commit()
    conn.close()

    app.run(host="0.0.0.0", port=10000)
