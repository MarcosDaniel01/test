from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "segredo_super"

# =========================
# CONFIG BANCO (RENDER + LOCAL)
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///banco.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# CONFIG
# =========================
GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# =========================
# MODELOS
# =========================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(20))  # admin ou operador


class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    gerenciadora = db.Column(db.String(50))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

# =========================
# INIT BANCO (SEM ERRO)
# =========================
with app.app_context():
    db.create_all()

    # cria admin padrão se não existir
    if not Usuario.query.filter_by(usuario="admin").first():
        admin = Usuario(usuario="admin", senha="123", tipo="admin")
        db.session.add(admin)
        db.session.commit()

# =========================
# LOGIN
# =========================
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

        return "Login inválido"

    return """
    <body style="background:#f4f4f4;text-align:center;font-family:Arial;">
    <h2>🔐 Login</h2>
    <form method="post" style="background:white;padding:20px;width:300px;margin:auto;border-radius:10px;">
    <input name="usuario" placeholder="Usuário"><br><br>
    <input name="senha" type="password" placeholder="Senha"><br><br>
    <button>Entrar</button>
    </form>
    </body>
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

    <h1>📦 ESTOQUE PROFISSIONAL</h1>

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

    <br><a href="/excel">📊 EXPORTAR EXCEL</a><br>
    """

    if session["tipo"] == "admin":
        html += """
        <br><a href="/criar_usuario">👤 Criar Usuário</a>
        """

    for nome, lista in grupos.items():
        html += f"<div class='{nome}'>{nome}</div>"
        html += """
        <table>
        <tr>
        <th>ITEM</th><th>ENTRADA</th><th>SAIDA</th>
        <th>SALDO</th><th>MÉDIA</th><th>6M+20%</th><th>STATUS</th>
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

    ger = request.form["ger"].upper()
    tipo = request.form["tipo"].upper()
    item = request.form["item"]
    qtd = int(request.form["qtd"])

    # BLOQUEIO MAIÚSCULO
    if item != item.upper():
        return "ERRO: Use MAIÚSCULO"

    # BLOQUEIO GERENCIADORA NO NOME
    if ger != "OUTROS":
        for g in GERENCIADORAS:
            if g in item:
                return f"ERRO: Não usar {g} no item"

    mov = Movimentacao(
        gerenciadora=ger,
        tipo=tipo,
        item=item,
        quantidade=qtd
    )

    db.session.add(mov)
    db.session.commit()

    return redirect("/sistema")

# =========================
# IA PREVISÃO
# =========================
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

        entrada = 0 if pd.isna(entrada) else entrada
        saida = 0 if pd.isna(saida) else saida

        saldo = entrada - saida

        meses = max(len(grupo["data"].astype(str).str[:7].unique()),1)
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

# =========================
# EXCEL (SEM ERRO)
# =========================
@app.route("/excel")
def excel():
    dados = calcular()
    df = pd.DataFrame(dados)

    arquivo = "estoque.xlsx"
    df.to_excel(arquivo, index=False)

    return send_file(arquivo, as_attachment=True)

# =========================
# CRIAR USUÁRIO (ADMIN)
# =========================
@app.route("/criar_usuario", methods=["GET","POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Acesso negado"

    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]
        t = request.form["tipo"]

        novo = Usuario(usuario=u, senha=s, tipo=t)
        db.session.add(novo)
        db.session.commit()

        return redirect("/sistema")

    return """
    <h2>Criar Usuário</h2>
    <form method="post">
    <input name="usuario" placeholder="Usuário"><br>
    <input name="senha" placeholder="Senha"><br>
    <select name="tipo">
    <option>admin</option>
    <option>operador</option>
    </select>
    <button>Criar</button>
    </form>
    """

# =========================
# START (RENDER OK)
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
