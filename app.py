from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "segredo"

# ===============================
# DATABASE (RENDER POSTGRES)
# ===============================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

GERENCIADORAS = ["PRIME", "LINK", "NEO", "OUTROS"]

# ===============================
# TABELAS
# ===============================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(20))  # admin ou operador

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime)
    gerenciadora = db.Column(db.String(50))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)
    imagem = db.Column(db.String(200))

# ===============================
# INIT
# ===============================
with app.app_context():
    db.create_all()

    if not Usuario.query.filter_by(usuario="admin").first():
        db.session.add(Usuario(usuario="admin", senha="123", tipo="admin"))
        db.session.commit()

# ===============================
# LOGIN
# ===============================
@app.route("/", methods=["GET","POST"])
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
    body{font-family:Arial;background:#f4f4f4;text-align:center;}
    table{width:95%;margin:20px auto;border-collapse:collapse;background:white;}
    th,td{padding:8px;border:1px solid #ccc;}
    th{background:black;color:white;}
    .PRIME{background:#2e7d32;color:white;padding:10px;}
    .LINK{background:#1565c0;color:white;padding:10px;}
    .NEO{background:#00897b;color:white;padding:10px;}
    .OUTROS{background:#ef6c00;color:white;padding:10px;}
    form{background:white;padding:20px;width:400px;margin:auto;border-radius:10px;}
    button{background:green;color:white;padding:10px;width:100%;}
    </style>
    </head>
    <body>

    <h1>📦 ESTOQUE INTELIGENTE</h1>

    <form method="POST" action="/inserir" enctype="multipart/form-data">
    <select name="ger">
    <option>PRIME</option>
    <option>LINK</option>
    <option>NEO</option>
    <option>OUTROS</option>
    </select>

    <select name="tipo">
    <option>ENTRADA</option>
    <option>SAIDA</option>
    </select>

    <input name="item" required>
    <input name="qtd" type="number" required>
    <input type="file" name="img">

    <button>INSERIR</button>
    </form>

    <br><a href="/excel">📊 EXPORTAR EXCEL</a><br>
    <br><a href="/backup">💾 BACKUP</a><br>
    """

    if session["tipo"] == "admin":
        html += """
        <h3>Criar Usuário</h3>
        <form method="POST" action="/criar_usuario">
        <input name="usuario" required>
        <input name="senha" required>
        <select name="tipo">
        <option value="operador">Operador</option>
        <option value="admin">Admin</option>
        </select>
        <button>Criar</button>
        </form>
        """

    for nome, lista in grupos.items():
        html += f"<div class='{nome}'>{nome}</div>"
        html += "<table><tr><th>ITEM</th><th>ENTRADA</th><th>SAIDA</th><th>SALDO</th><th>STATUS</th></tr>"

        for d in lista:
            html += f"""
            <tr>
            <td>{d['item']}</td>
            <td>{d['entrada']}</td>
            <td>{d['saida']}</td>
            <td>{d['saldo']}</td>
            <td>{d['status']}</td>
            </tr>
            """

        html += "</table>"

    return html + "</body></html>"

# ===============================
# INSERIR
# ===============================
@app.route("/inserir", methods=["POST"])
def inserir():
    if "user" not in session:
        return redirect("/")

    ger = request.form["ger"]
    tipo = request.form["tipo"]
    item = request.form["item"].upper()
    qtd = int(request.form["qtd"])

    img = request.files.get("img")
    nome_img = None

    if img:
        nome_img = img.filename
        img.save("static/" + nome_img)

    db.session.add(Movimentacao(
        data=datetime.now(),
        gerenciadora=ger,
        tipo=tipo,
        item=item,
        quantidade=qtd,
        imagem=nome_img
    ))
    db.session.commit()

    backup_auto()

    return redirect("/sistema")

# ===============================
# CALCULO
# ===============================
def calcular():
    dados = Movimentacao.query.all()
    resultado = {}

    for d in dados:
        key = (d.gerenciadora, d.item)

        if key not in resultado:
            resultado[key] = {"entrada":0,"saida":0}

        if d.tipo == "ENTRADA":
            resultado[key]["entrada"] += d.quantidade
        else:
            resultado[key]["saida"] += d.quantidade

    lista = []
    for (ger,item), v in resultado.items():
        saldo = v["entrada"] - v["saida"]
        status = "COMPRAR" if saldo < 50 else "OK"

        lista.append({
            "ger":ger,
            "item":item,
            "entrada":v["entrada"],
            "saida":v["saida"],
            "saldo":saldo,
            "status":status
        })

    return lista

# ===============================
# EXCEL COMPLETO
# ===============================
@app.route("/excel")
def excel():
    dados = calcular()
    df = pd.DataFrame(dados)

    writer = pd.ExcelWriter("estoque.xlsx", engine="openpyxl")

    for g in GERENCIADORAS:
        df[df["ger"]==g].to_excel(writer, sheet_name=g, index=False)

    df.to_excel(writer, sheet_name="RESUMO", index=False)

    writer.close()
    return send_file("estoque.xlsx", as_attachment=True)

# ===============================
# USUARIO
# ===============================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session["tipo"] != "admin":
        return "Acesso negado"

    db.session.add(Usuario(
        usuario=request.form["usuario"],
        senha=request.form["senha"],
        tipo=request.form["tipo"]
    ))
    db.session.commit()

    return redirect("/sistema")

# ===============================
# BACKUP
# ===============================
def backup_auto():
    df = pd.read_sql(db.session.query(Movimentacao).statement, db.session.bind)
    df.to_excel("backup.xlsx", index=False)

@app.route("/backup")
def backup():
    return send_file("backup.xlsx", as_attachment=True)

# ===============================
# START (RENDER)
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
