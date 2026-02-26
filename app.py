from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "segredo"

# =========================
# BANCO (RENDER)
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# TABELAS
# =========================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50))
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(20))

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(50))
    gerenciadora = db.Column(db.String(50))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

# =========================
# GERENCIADORAS
# =========================
GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# =========================
# INIT BANCO (SEM QUEBRAR)
# =========================
with app.app_context():
    db.create_all()

    if not Usuario.query.filter_by(usuario="admin").first():
        admin = Usuario(usuario="admin", senha="123", tipo="admin")
        db.session.add(admin)
        db.session.commit()

# =========================
# LOGIN
# =========================
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
    <h2>Login</h2>
    <form method="post">
    <input name="usuario" placeholder="Usuario"><br>
    <input name="senha" type="password"><br>
    <button>Entrar</button>
    </form>
    """

# =========================
# SISTEMA
# =========================
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
    """ + "".join([f"<option>{g}</option>" for g in GERENCIADORAS]) + """
    </select>

    <select name="tipo">
    <option>ENTRADA</option>
    <option>SAIDA</option>
    </select>

    <input name="item" placeholder="ITEM (MAIÚSCULO)" required>
    <input name="qtd" type="number" required>

    <button>INSERIR</button>
    </form>

    <br><a href="/excel">📊 EXPORTAR EXCEL</a>
    <br><a href="/backup">💾 BACKUP</a>
    """

    if session["tipo"] == "admin":
        html += """
        <h3>Criar Usuário</h3>
        <form method="POST" action="/criar_usuario">
        <input name="usuario" placeholder="Usuario"><br>
        <input name="senha" placeholder="Senha"><br>
        <select name="tipo">
        <option value="admin">Admin</option>
        <option value="operador">Operador</option>
        </select>
        <button>Criar</button>
        </form>
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

# =========================
# INSERIR
# =========================
@app.route("/inserir", methods=["POST"])
def inserir():
    ger = request.form["ger"]
    tipo = request.form["tipo"]
    item = request.form["item"]
    qtd = int(request.form["qtd"])

    if item != item.upper():
        return "USE MAIÚSCULO"

    if ger != "OUTROS":
        for g in GERENCIADORAS:
            if g in item:
                return "NÃO USAR GERENCIADORA NO NOME"

    mov = Movimentacao(
        data=str(datetime.now()),
        gerenciadora=ger,
        tipo=tipo,
        item=item,
        quantidade=qtd
    )

    db.session.add(mov)
    db.session.commit()

    return redirect("/sistema")

# =========================
# CRIAR USUARIO
# =========================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Sem permissão"

    u = request.form["usuario"]
    s = request.form["senha"]
    t = request.form["tipo"]

    novo = Usuario(usuario=u, senha=s, tipo=t)
    db.session.add(novo)
    db.session.commit()

    return redirect("/sistema")

# =========================
# CALCULO
# =========================
def calcular():
    dados = Movimentacao.query.all()

    resultado = {}
    for d in dados:
        chave = (d.gerenciadora, d.item)
        if chave not in resultado:
            resultado[chave] = {"entrada":0,"saida":0}

        if d.tipo == "ENTRADA":
            resultado[chave]["entrada"] += d.quantidade
        else:
            resultado[chave]["saida"] += d.quantidade

    final = []
    for (ger,item), v in resultado.items():
        saldo = v["entrada"] - v["saida"]
        media = v["saida"] / 1
        proj = int(media * 6 * 1.2)

        status = "OK"
        if saldo < proj:
            status = "COMPRAR"

        final.append({
            "ger":ger,
            "item":item,
            "entrada":v["entrada"],
            "saida":v["saida"],
            "saldo":saldo,
            "media":int(media),
            "proj":proj,
            "status":status
        })

    return final

# =========================
# EXCEL
# =========================
@app.route("/excel")
def excel():
    dados = calcular()
    df = pd.DataFrame(dados)

    arquivo = "estoque.xlsx"
    df.to_excel(arquivo, index=False)

    return send_file(arquivo, as_attachment=True)

# =========================
# BACKUP
# =========================
@app.route("/backup")
def backup():
    dados = Movimentacao.query.all()
    lista = []

    for d in dados:
        lista.append({
            "data": d.data,
            "ger": d.gerenciadora,
            "tipo": d.tipo,
            "item": d.item,
            "qtd": d.quantidade
        })

    df = pd.DataFrame(lista)
    arquivo = "backup.xlsx"
    df.to_excel(arquivo, index=False)

    return send_file(arquivo, as_attachment=True)
