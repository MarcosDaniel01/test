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
# CONEXÃO
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
        id SERIAL PRIMARY KEY,
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
        c.execute("SELECT * FROM usuarios WHERE usuario=%s AND senha=%s",(u,s))
        user = c.fetchone()
        conn.close()

        if user:
            session["user"] = u
            session["tipo"] = user[2]
            return redirect("/sistema")

    return """
    <html>
    <body style="background:#ffffff;font-family:Arial;text-align:center;">
    <h2>Login</h2>
    <form method="post">
    <input name="usuario" placeholder="Usuário"><br><br>
    <input name="senha" type="password"><br><br>
    <button>Entrar</button>
    </form>
    </body>
    </html>
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
    <body style="background:#ffffff;font-family:Arial;text-align:center;">
    <h1>📦 ESTOQUE INTELIGENTE</h1>

    <form method="POST" action="/inserir">
    <select name="ger">
    """

    for g in GERENCIADORAS:
        html += f"<option>{g}</option>"

    html += """
    </select>

    <select name="tipo">
    <option>ENTRADA</option>
    <option>SAIDA</option>
    </select>

    <input name="item" placeholder="ITEM MAIÚSCULO" required>
    <input name="qtd" type="number" required>

    <button>SALVAR</button>
    </form>

    <br><a href="/excel">📊 EXPORTAR EXCEL</a><br><br>
    """

    # ADMIN
    if session["tipo"] == "admin":
        html += """
        <h3>CRIAR USUÁRIO</h3>
        <form method="POST" action="/criar_usuario">
        <input name="usuario" placeholder="Usuário"><br><br>
        <input name="senha" placeholder="Senha"><br><br>
        <select name="tipo">
        <option value="operador">Operador</option>
        <option value="admin">Admin</option>
        </select><br><br>
        <button>CRIAR</button>
        </form><br>
        """

    # TABELAS
    for nome, lista in grupos.items():
        html += f"<h3>{nome}</h3>"
        html += """
        <table border="1" style="width:95%;margin:auto;">
        <tr>
        <th>ITEM</th><th>ENTRADA</th><th>SAIDA</th>
        <th>SALDO</th><th>MÉDIA MENSAL</th>
        <th>6 MESES +20%</th><th>STATUS</th>
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

        html += "</table><br>"

    html += "</body></html>"
    return html

# ===============================
# INSERIR (SEM DUPLICAR)
# ===============================
@app.route("/inserir", methods=["POST"])
def inserir():
    ger = request.form["ger"].upper()
    tipo = request.form["tipo"].upper()
    item = request.form["item"]
    qtd = int(request.form["qtd"])

    # BLOQUEIO MAIUSCULO
    if item != item.upper():
        return "ERRO: USE MAIÚSCULO"

    # BLOQUEIO GERENCIADORA NO NOME
    for g in GERENCIADORAS:
        if g in item:
            return f"ERRO: NÃO USAR {g} NO NOME"

    conn = conectar()
    c = conn.cursor()

    # SALVA APENAS MOVIMENTAÇÃO (SEM DUPLICAR ESTOQUE)
    c.execute("""
    INSERT INTO movimentacao (data,gerenciadora,tipo,item,quantidade)
    VALUES (%s,%s,%s,%s,%s)
    """, (datetime.now(), ger, tipo, item, qtd))

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

    df["data"] = pd.to_datetime(df["data"])

    for (ger, item), grupo in df.groupby(["gerenciadora","item"]):

        entrada = grupo[grupo["tipo"]=="ENTRADA"]["quantidade"].sum() or 0
        saida = grupo[grupo["tipo"]=="SAIDA"]["quantidade"].sum() or 0

        saldo = entrada - saida

        meses = max(len(grupo["data"].dt.to_period("M").unique()),1)
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
# CRIAR USUARIO
# ===============================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "SEM PERMISSÃO"

    u = request.form["usuario"]
    s = request.form["senha"]
    t = request.form["tipo"]

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO usuarios (usuario,senha,tipo)
    VALUES (%s,%s,%s)
    ON CONFLICT (usuario) DO NOTHING
    """,(u,s,t))

    conn.commit()
    conn.close()

    return redirect("/sistema")

# ===============================
# EXCEL COMPLETO
# ===============================
@app.route("/excel")
def excel():
    dados = calcular()
    df = pd.DataFrame(dados)

    writer = pd.ExcelWriter("estoque.xlsx", engine="xlsxwriter")

    for g in GERENCIADORAS:
        df_g = df[df["ger"] == g]
        df_g.to_excel(writer, sheet_name=g, index=False)

    writer.close()

    return send_file("estoque.xlsx", as_attachment=True)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar()

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO usuarios (usuario,senha,tipo)
    VALUES (%s,%s,'admin')
    ON CONFLICT (usuario) DO NOTHING
    """, ("admin","123"))

    conn.commit()
    conn.close()

    app.run(host="0.0.0.0", port=10000)
