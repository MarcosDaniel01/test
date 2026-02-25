from flask import Flask, request, redirect, session, send_file
from datetime import datetime
import pandas as pd
import os
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.secret_key = "segredo"

# ==========================================
# BANCO (Render ou Local)
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine("sqlite:///estoque.db")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ==========================================
# CRIAR BANCO
# ==========================================
def criar():
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            gerenciadora TEXT,
            tipo TEXT,
            item TEXT,
            quantidade INTEGER
        )
        """))

        conn.execute(text("""
        INSERT INTO usuarios (usuario, senha, tipo)
        VALUES ('admin','123','admin')
        ON CONFLICT(usuario) DO NOTHING
        """))

criar()

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

    return """
    <h2>Login</h2>
    <form method="post">
    <input name="usuario"><br>
    <input name="senha" type="password"><br>
    <button>Entrar</button>
    </form>
    """

# ==========================================
# CRIAR USUARIO (ADMIN)
# ==========================================
@app.route("/criar_usuario", methods=["GET","POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Acesso negado"

    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]
        t = request.form["tipo"]

        with engine.begin() as conn:
            conn.execute(text("""
            INSERT INTO usuarios VALUES (:u,:s,:t)
            """), {"u":u,"s":s,"t":t})

        return redirect("/sistema")

    return """
    <h2>Criar Usuário</h2>
    <form method="post">
    <input name="usuario"><br>
    <input name="senha"><br>
    <select name="tipo">
    <option>admin</option>
    <option>operador</option>
    </select>
    <button>Criar</button>
    </form>
    """

# ==========================================
# INSERIR
# ==========================================
@app.route("/inserir", methods=["POST"])
def inserir():

    ger = request.form["ger"].upper()
    tipo = request.form["tipo"].upper()
    item = request.form["item"]
    qtd = int(request.form["qtd"])

    if item != item.upper():
        return "ERRO: Use MAIÚSCULO"

    for g in GERENCIADORAS:
        if g in item:
            return f"ERRO: Não usar {g} no item"

    with engine.begin() as conn:
        conn.execute(text("""
        INSERT INTO movimentacao VALUES (NULL,:d,:g,:t,:i,:q)
        """), {
            "d": str(datetime.now()),
            "g": ger,
            "t": tipo,
            "i": item,
            "q": qtd
        })

    return redirect("/sistema")

# ==========================================
# IA CALCULO
# ==========================================
def calcular():
    df = pd.read_sql("SELECT * FROM movimentacao", engine)

    if df.empty:
        return []

    df["data"] = pd.to_datetime(df["data"])

    resultado = []

    for (ger, item), grupo in df.groupby(["gerenciadora","item"]):

        entrada = grupo[grupo["tipo"]=="ENTRADA"]["quantidade"].sum()
        saida = grupo[grupo["tipo"]=="SAIDA"]["quantidade"].sum()

        entrada = entrada if not pd.isna(entrada) else 0
        saida = saida if not pd.isna(saida) else 0

        saldo = entrada - saida

        mensal = grupo.groupby(grupo["data"].dt.to_period("M"))["quantidade"].sum()
        media = mensal.mean() if not mensal.empty else 0

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
            "media": int(media),
            "proj": int(proj),
            "status": status
        })

    return resultado

# ==========================================
# SISTEMA (MESMO VISUAL)
# ==========================================
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

    <br><a href="/excel">📊 EXPORTAR EXCEL</a><br>
    """

    if session["tipo"] == "admin":
        html += "<br><a href='/criar_usuario'>👤 CRIAR USUARIO</a><br>"

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
            df[df["gerenciadora"] == ger].to_excel(writer, sheet_name=ger)

    return send_file(arquivo, as_attachment=True)

# ==========================================
# START
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
