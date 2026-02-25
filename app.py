from flask import Flask, request, redirect, session, send_file
import os
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.secret_key = "segredo"

# ==========================================
# DATABASE (Render ou Local)
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, future=True)
else:
    engine = create_engine("sqlite:///estoque.db", future=True)

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ==========================================
# CRIAR TABELAS
# ==========================================
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios(
            usuario TEXT PRIMARY KEY,
            senha TEXT,
            tipo TEXT
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS movimentacao(
            id SERIAL PRIMARY KEY,
            data TIMESTAMP,
            gerenciadora TEXT,
            tipo TEXT,
            item TEXT,
            quantidade INTEGER
        )
        """))

        conn.execute(text("""
        INSERT INTO usuarios (usuario, senha, tipo)
        VALUES ('admin','123','admin')
        ON CONFLICT (usuario) DO NOTHING
        """))

init_db()

# ==========================================
# LOGIN
# ==========================================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        with engine.connect() as conn:
            user = conn.execute(text("""
                SELECT * FROM usuarios
                WHERE usuario=:u AND senha=:s
            """), {"u":u,"s":s}).fetchone()

        if user:
            session["user"] = u
            session["tipo"] = user[2]
            return redirect("/sistema")
        else:
            return "Login inválido"

    return """
    <h2>Login</h2>
    <form method="post">
    <input name="usuario" placeholder="usuario"><br><br>
    <input name="senha" type="password"><br><br>
    <button>Entrar</button>
    </form>
    """

# ==========================================
# CRIAR USUARIO (FUNCIONANDO)
# ==========================================
@app.route("/criar_usuario", methods=["GET","POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Acesso negado"

    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]
        t = request.form["tipo"]

        if not u or not s:
            return "Preencha todos os campos"

        with engine.begin() as conn:

            existe = conn.execute(text("""
                SELECT usuario FROM usuarios
                WHERE usuario=:u
            """), {"u":u}).fetchone()

            if existe:
                return "Usuário já existe"

            conn.execute(text("""
                INSERT INTO usuarios (usuario, senha, tipo)
                VALUES (:u,:s,:t)
            """), {"u":u,"s":s,"t":t})

        return redirect("/sistema")

    return """
    <h2>Novo Usuário</h2>
    <form method="post">
    <input name="usuario"><br><br>
    <input name="senha"><br><br>
    <select name="tipo">
    <option value="admin">admin</option>
    <option value="operador">operador</option>
    </select><br><br>
    <button>Criar</button>
    </form>
    """

# ==========================================
# INSERIR ENTRADA / SAIDA (CORRIGIDO)
# ==========================================
@app.route("/inserir", methods=["POST"])
def inserir():
    ger = request.form["ger"].upper()
    tipo = request.form["tipo"].upper()
    item = request.form["item"].strip()
    qtd = int(request.form["qtd"])

    if item != item.upper():
        return "Use MAIÚSCULO no item"

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO movimentacao
            (data, gerenciadora, tipo, item, quantidade)
            VALUES (:d,:g,:t,:i,:q)
        """), {
            "d": datetime.now(),
            "g": ger,
            "t": tipo,
            "i": item,
            "q": qtd
        })

    return redirect("/sistema")

# ==========================================
# CALCULO
# ==========================================
def calcular():
    df = pd.read_sql("SELECT * FROM movimentacao", engine)

    if df.empty:
        return []

    df["data"] = pd.to_datetime(df["data"])

    resultado = []

    for (ger, item), g in df.groupby(["gerenciadora","item"]):

        entrada = g[g["tipo"]=="ENTRADA"]["quantidade"].sum()
        saida = g[g["tipo"]=="SAIDA"]["quantidade"].sum()
        saldo = entrada - saida

        mensal = g.groupby(g["data"].dt.to_period("M"))["quantidade"].sum()
        media = mensal.mean() if not mensal.empty else 0
        proj = int(media * 6 * 1.2)

        status = "OK" if saldo >= proj else "COMPRAR"

        resultado.append({
            "ger":ger,
            "item":item,
            "entrada":int(entrada),
            "saida":int(saida),
            "saldo":int(saldo),
            "media":int(media),
            "proj":proj,
            "status":status
        })

    return resultado

# ==========================================
# SISTEMA
# ==========================================
@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    dados = calcular()
    grupos = {g:[] for g in GERENCIADORAS}

    for d in dados:
        grupos[d["ger"]].append(d)

    html = """
    <h1>ESTOQUE</h1>

    <form method="POST" action="/inserir">
    <select name="ger">
    <option>PRIME</option>
    <option>LINK</option>
    <option>NEO</option>
    <option>FITMOBY</option>
    <option>OUTROS</option>
    </select>

    <select name="tipo">
    <option value="ENTRADA">ENTRADA</option>
    <option value="SAIDA">SAIDA</option>
    </select>

    <input name="item" placeholder="ITEM (MAIÚSCULO)" required>
    <input name="qtd" type="number" required>
    <button>Inserir</button>
    </form>

    <br><a href='/excel'>EXPORTAR EXCEL</a><br>
    """

    if session["tipo"] == "admin":
        html += "<br><a href='/criar_usuario'>CRIAR USUARIO</a><br>"

    for nome, lista in grupos.items():
        html += f"<h3>{nome}</h3>"
        html += "<table border=1><tr><th>ITEM</th><th>ENT</th><th>SAI</th><th>SALDO</th><th>MEDIA</th><th>6M</th><th>STATUS</th></tr>"

        for d in lista:
            html += f"""
            <tr>
            <td>{d['item']}</td>
            <td>{d['entrada']}</td>
            <td>{d['saida']}</td>
            <td>{d['saldo']}</td>
            <td>{d['media']}</td>
            <td>{d['proj']}</td>
            <td>{d['status']}</td>
            </tr>
            """

        html += "</table><br>"

    return html

# ==========================================
# EXCEL
# ==========================================
@app.route("/excel")
def excel():
    df = pd.read_sql("SELECT * FROM movimentacao", engine)
    df["data"] = pd.to_datetime(df["data"])

    arquivo = "estoque.xlsx"

    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        for ger in df["gerenciadora"].unique():
            dfg = df[df["gerenciadora"]==ger]
            mensal = dfg.groupby(
                dfg["data"].dt.to_period("M")
            )["quantidade"].sum()
            mensal.to_excel(writer, sheet_name=ger)

    return send_file(arquivo, as_attachment=True)

# ==========================================
# START
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
