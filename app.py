from flask import Flask, request, redirect, session, send_file
import sqlite3
from datetime import datetime
import pandas as pd
import os
import shutil
import getpass

app = Flask(__name__)
app.secret_key = "segredo"

DB = "estoque.db"
BACKUP = "backup.db"

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# BANCO
# ===============================
def conectar():
    return sqlite3.connect(DB)

def criar():
    conn = conectar()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        usuario TEXT,
        tipo TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS movimentacao(
        data TEXT,
        gerenciadora TEXT,
        tipo TEXT,
        item TEXT,
        quantidade INTEGER
    )
    """)

    conn.commit()
    conn.close()

# ===============================
# LOGIN AUTOMÁTICO
# ===============================
@app.route("/")
def login():
    user = getpass.getuser()

    session["user"] = user
    session["tipo"] = "admin"

    return redirect("/sistema")

# ===============================
# BACKUP AUTOMÁTICO
# ===============================
def fazer_backup():
    if os.path.exists(DB):
        shutil.copy(DB, BACKUP)

# ===============================
# RESTAURAR BACKUP
# ===============================
@app.route("/restaurar")
def restaurar():
    if os.path.exists(BACKUP):
        shutil.copy(BACKUP, DB)
        return "Backup restaurado com sucesso!"
    return "Nenhum backup encontrado"

# ===============================
# SISTEMA
# ===============================
@app.route("/sistema")
def sistema():

    fazer_backup()  # backup automático ao abrir

    dados = calcular()

    grupos = {g: [] for g in GERENCIADORAS}
    for d in dados:
        grupos[d["ger"]].append(d)

    html = """
    <html>
    <head>
    <style>
    body{font-family:Arial;background:#f4f4f4;text-align:center;}
    table{width:95%;margin:20px auto;border-collapse:collapse;background:white;}
    th,td{padding:8px;border:1px solid #ccc;}
    th{background:black;color:white;}
    .PRIME{background:#2e7d32;color:white;padding:10px;}
    .LINK{background:#1565c0;color:white;padding:10px;}
    .NEO{background:#00897b;color:white;padding:10px;}
    .FITMOBY{background:#6a1b9a;color:white;padding:10px;}
    .OUTROS{background:#ef6c00;color:white;padding:10px;}
    form{background:white;padding:20px;width:400px;margin:auto;border-radius:10px;}
    button{background:green;color:white;padding:10px;width:100%;}
    </style>
    </head>
    <body>

    <h1>📦 ESTOQUE INTELIGENTE</h1>

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

    <button>INSERIR</button>
    </form>

    <br>
    <a href="/excel">📊 EXPORTAR EXCEL</a><br>
    <a href="/restaurar">♻️ RESTAURAR BACKUP</a><br>
    """

    for nome, lista in grupos.items():
        html += f"<div class='{nome}'>{nome}</div>"
        html += """
        <table>
        <tr>
        <th>ITEM</th><th>ENTRADA</th><th>SAIDA</th>
        <th>SALDO</th><th>MÉDIA</th><th>6 MESES</th><th>STATUS</th>
        </tr>
        """

        for d in lista:
            cor = "red" if d["saldo"] < 50 else "black"

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

    # 🔠 BLOQUEIO MAIUSCULO
    if item != item.upper():
        return "ERRO: Use apenas MAIÚSCULO"

    # 🚫 BLOQUEIO GERENCIADORA
    if ger != "OUTROS":
        for g in GERENCIADORAS:
            if g in item:
                return f"ERRO: Não usar {g} no item"

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO movimentacao VALUES (?,?,?,?,?)
    """, (datetime.now(), ger, tipo, item, qtd))

    conn.commit()
    conn.close()

    return redirect("/sistema")

# ===============================
# IA / CALCULO
# ===============================
def calcular():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacao", conn)
    conn.close()

    if df.empty:
        return []

    resultado = []

    for (ger, item), grupo in df.groupby(["gerenciadora","item"]):

        entrada = grupo[grupo["tipo"]=="ENTRADA"]["quantidade"].sum()
        saida = grupo[grupo["tipo"]=="SAIDA"]["quantidade"].sum()

        saldo = entrada - saida

        meses = max(len(grupo["data"].unique()),1)
        media = saida / meses

        proj = int((media * 6) * 1.2)  # +20%

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
    app.run(host="0.0.0.0", port=10000)
