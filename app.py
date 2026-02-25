from flask import Flask, request, redirect, session, send_file
import psycopg2
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "segredo_super")

DATABASE_URL = os.environ.get("DATABASE_URL")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ==============================
# CONEXÃO BANCO
# ==============================
def conectar():
    return psycopg2.connect(DATABASE_URL)

# ==============================
# CRIAR TABELAS
# ==============================
def criar_tabelas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        usuario TEXT PRIMARY KEY,
        senha TEXT NOT NULL,
        tipo TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimentacoes(
        id SERIAL PRIMARY KEY,
        data TIMESTAMP,
        gerenciadora TEXT,
        tipo TEXT,
        item TEXT,
        quantidade INTEGER
    );
    """)

    conn.commit()

    # cria admin padrão se não existir
    cur.execute("""
    INSERT INTO usuarios (usuario, senha, tipo)
    VALUES ('admin','123','admin')
    ON CONFLICT (usuario) DO NOTHING;
    """)

    conn.commit()
    conn.close()

# ==============================
# LOGIN
# ==============================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario=%s AND senha=%s", (u,s))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = u
            session["tipo"] = user[2]
            return redirect("/sistema")

        return "Login inválido"

    return """
    <h2>Login</h2>
    <form method="post">
    <input name="usuario" placeholder="Usuario"><br>
    <input name="senha" type="password"><br>
    <button>Entrar</button>
    </form>
    """

# ==============================
# SISTEMA
# ==============================
@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacoes", conn)
    conn.close()

    resultado = []

    if not df.empty:
        df["data"] = pd.to_datetime(df["data"])

        for (ger, item), grupo in df.groupby(["gerenciadora","item"]):

            entrada = grupo[grupo["tipo"]=="ENTRADA"]["quantidade"].sum()
            saida = grupo[grupo["tipo"]=="SAIDA"]["quantidade"].sum()
            saldo = entrada - saida

            meses = max(len(grupo["data"].dt.to_period("M").unique()),1)
            media = saida / meses
            proj = int(media * 6 * 1.2)

            status = "OK"
            if saldo < proj:
                status = "COMPRAR"

            resultado.append({
                "ger": ger,
                "item": item,
                "entrada": int(entrada),
                "saida": int(saida),
                "saldo": int(saldo),
                "proj": proj,
                "status": status
            })

    html = """
    <h1>📦 ESTOQUE INTELIGENTE</h1>
    <form method="POST" action="/movimentar">
    <select name="ger">""" + "".join([f"<option>{g}</option>" for g in GERENCIADORAS]) + """</select>
    <select name="tipo">
    <option>ENTRADA</option>
    <option>SAIDA</option>
    </select>
    <input name="item" placeholder="ITEM MAIÚSCULO">
    <input name="qtd" type="number">
    <button>Salvar</button>
    </form>
    <br><a href="/excel">Exportar Excel</a>
    <table border=1>
    <tr><th>Ger</th><th>Item</th><th>Entrada</th><th>Saida</th><th>Saldo</th><th>6M+20%</th><th>Status</th></tr>
    """

    for r in resultado:
        html += f"""
        <tr>
        <td>{r['ger']}</td>
        <td>{r['item']}</td>
        <td>{r['entrada']}</td>
        <td>{r['saida']}</td>
        <td>{r['saldo']}</td>
        <td>{r['proj']}</td>
        <td>{r['status']}</td>
        </tr>
        """

    html += "</table>"
    return html

# ==============================
# MOVIMENTAÇÃO
# ==============================
@app.route("/movimentar", methods=["POST"])
def movimentar():
    if "user" not in session:
        return redirect("/")

    ger = request.form["ger"].upper()
    tipo = request.form["tipo"].upper()
    item = request.form["item"]
    qtd = int(request.form["qtd"])

    if item != item.upper():
        return "Use apenas MAIÚSCULO"

    if ger != "OUTROS":
        for g in GERENCIADORAS:
            if g in item:
                return "Não usar nome da gerenciadora no item"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO movimentacoes (data, gerenciadora, tipo, item, quantidade)
    VALUES (%s,%s,%s,%s,%s)
    """, (datetime.now(), ger, tipo, item, qtd))

    conn.commit()
    conn.close()

    return redirect("/sistema")

# ==============================
# EXCEL
# ==============================
@app.route("/excel")
def excel():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacoes", conn)
    conn.close()

    nome = "relatorio.xlsx"
    df.to_excel(nome, index=False)
    return send_file(nome, as_attachment=True)

# ==============================
# START (IMPORTANTE PARA RENDER)
# ==============================
criar_tabelas()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
