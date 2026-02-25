from flask import Flask, request, redirect, session, send_file
import os
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# CRIAR TABELAS
# ===============================
def criar():
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios(
            id SERIAL PRIMARY KEY,
            usuario TEXT UNIQUE,
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

        # cria admin se não existir
        res = conn.execute(text("SELECT * FROM usuarios WHERE usuario='admin'")).fetchone()
        if not res:
            conn.execute(text("""
            INSERT INTO usuarios (usuario, senha, tipo)
            VALUES ('admin','123','admin')
            """))

        conn.commit()

# ===============================
# LOGIN
# ===============================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        with engine.connect() as conn:
            user = conn.execute(text("""
                SELECT * FROM usuarios WHERE usuario=:u AND senha=:s
            """), {"u":u,"s":s}).fetchone()

        if user:
            session["user"] = u
            session["tipo"] = user[3]
            return redirect("/sistema")

    return """
    <h2>Login</h2>
    <form method="post">
    <input name="usuario"><br>
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
    body{font-family:Arial;background:#ffffff;text-align:center;}
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

    <h1>📦 ESTOQUE PROFISSIONAL</h1>

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
        html += """
        <h3>CRIAR USUÁRIO</h3>
        <form method="POST" action="/criar_usuario">
        <input name="usuario" placeholder="usuario">
        <input name="senha" placeholder="senha">
        <select name="tipo">
        <option>admin</option>
        <option>operador</option>
        </select>
        <button>Criar</button>
        </form>

        <br><a href="/backup">💾 Backup</a>
        """

    for nome, lista in grupos.items():
        html += f"<div class='{nome}'>{nome}</div>"
        html += """
        <table>
        <tr>
        <th>ITEM</th><th>ENTRADA</th><th>SAIDA</th>
        <th>SALDO</th><th>MÉDIA</th><th>6M +20%</th><th>STATUS</th>
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

    if item != item.upper():
        return "ERRO: MAIÚSCULO APENAS"

    for g in GERENCIADORAS:
        if g in item:
            return "ERRO: NÃO USE GERENCIADORA NO NOME"

    with engine.connect() as conn:
        conn.execute(text("""
        INSERT INTO movimentacao (data, gerenciadora, tipo, item, quantidade)
        VALUES (:d,:g,:t,:i,:q)
        """), {"d":datetime.now(),"g":ger,"t":tipo,"i":item,"q":qtd})

        conn.commit()

    return redirect("/sistema")

# ===============================
# IA / CALCULO
# ===============================
def calcular():
    df = pd.read_sql("SELECT * FROM movimentacao", engine)

    if df.empty:
        return []

    resultado = []

    for (ger, item), grupo in df.groupby(["gerenciadora","item"]):

        entrada = grupo[grupo["tipo"]=="ENTRADA"]["quantidade"].sum()
        saida = grupo[grupo["tipo"]=="SAIDA"]["quantidade"].sum()

        saldo = entrada - saida

        media = saida / max(len(grupo["data"].unique()),1)

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

# ===============================
# CRIAR USUARIO
# ===============================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session["tipo"] != "admin":
        return "Sem permissão"

    u = request.form["usuario"]
    s = request.form["senha"]
    t = request.form["tipo"]

    with engine.connect() as conn:
        conn.execute(text("""
        INSERT INTO usuarios (usuario, senha, tipo)
        VALUES (:u,:s,:t)
        """), {"u":u,"s":s,"t":t})
        conn.commit()

    return redirect("/sistema")

# ===============================
# BACKUP
# ===============================
@app.route("/backup")
def backup():
    df = pd.read_sql("SELECT * FROM movimentacao", engine)
    df.to_excel("backup.xlsx", index=False)
    return send_file("backup.xlsx", as_attachment=True)

# ===============================
# EXCEL COMPLETO
# ===============================
@app.route("/excel")
def excel():
    dados = calcular()
    df = pd.DataFrame(dados)

    writer = pd.ExcelWriter("estoque.xlsx", engine="openpyxl")

    for g in GERENCIADORAS:
        df_g = df[df["ger"]==g]
        df_g.to_excel(writer, sheet_name=g, index=False)

    writer.close()

    return send_file("estoque.xlsx", as_attachment=True)

# ===============================
# START
# ===============================
criar()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
