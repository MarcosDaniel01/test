from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os
import shutil

app = Flask(__name__)
app.secret_key = "segredo"

# ===============================
# CONFIG BANCO (PERSISTENTE)
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "estoque.db")

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

GERENCIADORAS = ["PRIME", "LINK", "NEO", "OUTROS"]

# ===============================
# TABELAS
# ===============================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(20))

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(50))
    gerenciadora = db.Column(db.String(20))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)
    imagem = db.Column(db.String(200))

# ===============================
# CRIAR BANCO + ADMIN (FLASK 3 OK)
# ===============================
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(username="admin").first():
        admin = Usuario(username="admin", senha="123", tipo="admin")
        db.session.add(admin)
        db.session.commit()

# ===============================
# BACKUP AUTOMATICO
# ===============================
def backup():
    if os.path.exists(DB_PATH):
        nome = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy(DB_PATH, nome)

# ===============================
# LOGIN
# ===============================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        user = Usuario.query.filter_by(username=u, senha=s).first()

        if user:
            session["user"] = u
            session["tipo"] = user.tipo
            return redirect("/sistema")

    return """
    <body style='background:white;text-align:center;font-family:Arial'>
    <h2>Login</h2>
    <form method="post">
    <input name="usuario" placeholder="Usuario"><br><br>
    <input name="senha" type="password"><br><br>
    <button>Entrar</button>
    </form>
    </body>
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
    body{font-family:Arial;background:white;text-align:center;}
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

    <input name="item" placeholder="ITEM (MAIÚSCULO)" required>
    <input name="qtd" type="number" required>
    <input type="file" name="imagem">

    <button>INSERIR</button>
    </form>

    <br><a href="/excel">📊 EXPORTAR EXCEL</a><br>
    """

    if session["tipo"] == "admin":
        html += """
        <h3>Criar Usuário</h3>
        <form method="POST" action="/criar_usuario">
        <input name="usuario" placeholder="usuario"><br>
        <input name="senha" placeholder="senha"><br>
        <select name="tipo">
        <option value="admin">admin</option>
        <option value="operador">operador</option>
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
        <th>SALDO</th><th>MÉDIA</th><th>6 MESES</th><th>STATUS</th><th>IMG</th>
        </tr>
        """

        for d in lista:
            cor = "red" if d["saldo"] < 50 else "black"

            img_html = f"<img src='{d['img']}' width='50'>" if d["img"] else ""

            html += f"""
            <tr>
            <td>{d['item']}</td>
            <td>{d['entrada']}</td>
            <td>{d['saida']}</td>
            <td style='color:{cor}'>{d['saldo']}</td>
            <td>{d['media']}</td>
            <td>{d['proj']}</td>
            <td>{d['status']}</td>
            <td>{img_html}</td>
            </tr>
            """

        html += "</table>"

    html += "</body></html>"
    return html

# ===============================
# CRIAR USUARIO
# ===============================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Acesso negado"

    u = request.form["usuario"]
    s = request.form["senha"]
    t = request.form["tipo"]

    novo = Usuario(username=u, senha=s, tipo=t)
    db.session.add(novo)
    db.session.commit()

    return redirect("/sistema")

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
        return "Use MAIÚSCULO"

    imagem = None
    file = request.files.get("imagem")

    if file and file.filename != "":
        pasta = "static"
        os.makedirs(pasta, exist_ok=True)
        caminho = os.path.join(pasta, file.filename)
        file.save(caminho)
        imagem = caminho

    mov = Movimentacao(
        data=str(datetime.now()),
        gerenciadora=ger,
        tipo=tipo,
        item=item,
        quantidade=qtd,
        imagem=imagem
    )

    db.session.add(mov)
    db.session.commit()

    backup()  # 🔥 backup automático

    return redirect("/sistema")

# ===============================
# CALCULO
# ===============================
def calcular():
    dados = Movimentacao.query.all()

    if not dados:
        return []

    df = pd.DataFrame([{
        "data": d.data,
        "gerenciadora": d.gerenciadora,
        "tipo": d.tipo,
        "item": d.item,
        "quantidade": d.quantidade,
        "imagem": d.imagem
    } for d in dados])

    resultado = []

    for (ger, item), grupo in df.groupby(["gerenciadora","item"]):

        entrada = grupo[grupo["tipo"]=="ENTRADA"]["quantidade"].sum()
        saida = grupo[grupo["tipo"]=="SAIDA"]["quantidade"].sum()

        saldo = entrada - saida
        meses = max(len(grupo["data"].unique()),1)
        media = saida / meses
        proj = int(media * 6)

        status = "OK" if saldo >= proj else "COMPRAR"

        img = grupo["imagem"].dropna().iloc[-1] if not grupo["imagem"].dropna().empty else None

        resultado.append({
            "ger": ger,
            "item": item,
            "entrada": int(entrada),
            "saida": int(saida),
            "saldo": int(saldo),
            "media": int(media),
            "proj": int(proj),
            "status": status,
            "img": img
        })

    return resultado

# ===============================
# EXCEL (SEM XlsxWriter)
# ===============================
@app.route("/excel")
def excel():
    dados = calcular()
    df = pd.DataFrame(dados)

    arquivo = "estoque.xlsx"
    df.to_excel(arquivo, index=False)  # usa openpyxl

    return send_file(arquivo, as_attachment=True)

# ===============================
# START (RENDER OK)
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
