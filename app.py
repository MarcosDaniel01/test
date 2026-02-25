from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os
import shutil

app = Flask(__name__)
app.secret_key = "segredo"

# ===============================
# 🔥 CORREÇÃO RENDER DATABASE
# ===============================
database_url = os.environ.get("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///estoque.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# BANCO
# ===============================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(10))

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime)
    gerenciadora = db.Column(db.String(20))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

# ===============================
# CRIAR BANCO AUTOMATICO
# ===============================
with app.app_context():
    db.create_all()

    if not Usuario.query.filter_by(usuario="admin").first():
        db.session.add(Usuario(usuario="admin", senha="123", tipo="admin"))
        db.session.commit()

# ===============================
# BACKUP AUTOMATICO
# ===============================
def backup():
    if "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]:
        if os.path.exists("estoque.db"):
            shutil.copy("estoque.db", "backup.db")

# ===============================
# LOGIN
# ===============================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        user = Usuario.query.filter_by(usuario=u, senha=s).first()

        if user:
            session["user"] = u
            session["tipo"] = user.tipo
            return redirect("/sistema")

    return """
    <body style='font-family:Arial;text-align:center;background:#f4f4f4'>
    <h2>Login</h2>
    <form method="post">
    <input name="usuario" placeholder="Usuario"><br><br>
    <input name="senha" type="password"><br><br>
    <button>Entrar</button>
    </form>
    </body>
    """

# ===============================
# CRIAR USUARIO (ADMIN)
# ===============================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Apenas admin"

    u = request.form["usuario"]
    s = request.form["senha"]
    t = request.form["tipo"]

    if Usuario.query.filter_by(usuario=u).first():
        return "Usuário já existe"

    db.session.add(Usuario(usuario=u, senha=s, tipo=t))
    db.session.commit()

    return redirect("/sistema")

# ===============================
# INSERIR (ENTRADA/SAIDA)
# ===============================
@app.route("/inserir", methods=["POST"])
def inserir():

    ger = request.form["ger"].upper()
    tipo = request.form["tipo"].upper()
    item = request.form["item"]
    qtd = int(request.form["qtd"])

    # BLOQUEIO MAIUSCULO
    if item != item.upper():
        return "ERRO: SOMENTE MAIÚSCULO"

    # BLOQUEIO GERENCIADORA NO NOME
    for g in GERENCIADORAS:
        if g in item and ger != "OUTROS":
            return "ERRO: NÃO COLOCAR GERENCIADORA NO ITEM"

    nova = Movimentacao(
        data=datetime.now(),
        gerenciadora=ger,
        tipo=tipo,
        item=item,
        quantidade=qtd
    )

    db.session.add(nova)
    db.session.commit()

    backup()

    return redirect("/sistema")

# ===============================
# CALCULO INTELIGENTE
# ===============================
def calcular():
    dados = Movimentacao.query.all()

    if not dados:
        return []

    df = pd.DataFrame([{
        "data": d.data,
        "ger": d.gerenciadora,
        "tipo": d.tipo,
        "item": d.item,
        "qtd": d.quantidade
    } for d in dados])

    resultado = []

    for (ger, item), grupo in df.groupby(["ger","item"]):
        entrada = grupo[grupo["tipo"]=="ENTRADA"]["qtd"].sum()
        saida = grupo[grupo["tipo"]=="SAIDA"]["qtd"].sum()

        entrada = entrada if not pd.isna(entrada) else 0
        saida = saida if not pd.isna(saida) else 0

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
            "media": int(media),
            "proj": int(proj),
            "status": status
        })

    return resultado

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
    </style>

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

    <input name="item" placeholder="ITEM MAIUSCULO">
    <input name="qtd" type="number">
    <button>INSERIR</button>
    </form>

    <br><a href="/excel">EXPORTAR EXCEL</a><br><br>
    """

    if session.get("tipo") == "admin":
        html += """
        <h3>Criar Usuario</h3>
        <form method="POST" action="/criar_usuario">
        <input name="usuario" placeholder="usuario">
        <input name="senha" placeholder="senha">
        <select name="tipo">
        <option value="admin">ADMIN</option>
        <option value="operador">OPERADOR</option>
        </select>
        <button>Criar</button>
        </form>
        """

    for nome, lista in grupos.items():
        html += f"<div class='{nome}'>{nome}</div><table>"
        html += "<tr><th>ITEM</th><th>ENTRADA</th><th>SAIDA</th><th>SALDO</th><th>MÉDIA</th><th>6M+20%</th><th>STATUS</th></tr>"

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

        html += "</table>"

    return html

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
# START RENDER
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

