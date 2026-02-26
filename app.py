from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os
import json

app = Flask(__name__)
app.secret_key = "segredo"

# =========================
# BANCO
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
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    senha = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(50))
    gerenciadora = db.Column(db.String(50))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# =========================
# INIT
# =========================
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(usuario="admin").first():
        db.session.add(Usuario(usuario="admin", senha="123", tipo="admin"))
        db.session.commit()

# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    erro = ""

    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]

        user = Usuario.query.filter_by(usuario=u, senha=s).first()

        if user:
            session["user"] = u
            session["tipo"] = user.tipo
            return redirect("/sistema")
        else:
            erro = "Usuário ou senha inválidos"

    return f"""
    <html>
    <head>
    <style>
    body{{margin:0;font-family:Arial;
    background:linear-gradient(135deg,#1e3c72,#2a5298);
    display:flex;justify-content:center;align-items:center;height:100vh;}}
    .box{{background:white;padding:40px;border-radius:15px;width:350px;text-align:center;}}
    input{{width:100%;padding:10px;margin:10px 0;border-radius:8px;border:1px solid #ccc;}}
    button{{width:100%;padding:12px;background:#2a5298;color:white;border:none;border-radius:8px;font-weight:bold;}}
    .erro{{color:red;}}
    </style>
    </head>
    <body>
    <div class="box">
        <h2>📦 ESTOQUE INTELIGENTE</h2>
        <div class="erro">{erro}</div>
        <form method="post">
            <input name="usuario" placeholder="Usuário" required>
            <input name="senha" type="password" placeholder="Senha" required>
            <button>Entrar</button>
        </form>
    </div>
    </body>
    </html>
    """

# =========================
# CALCULO
# =========================
def calcular():
    dados = Movimentacao.query.all()
    resultado = {}

    for d in dados:
        chave = (d.gerenciadora, d.item)

        if chave not in resultado:
            resultado[chave] = {"entrada": 0, "saida": 0}

        if d.tipo == "ENTRADA":
            resultado[chave]["entrada"] += d.quantidade
        else:
            resultado[chave]["saida"] += d.quantidade

    final = []

    for (ger, item), v in resultado.items():
        saldo = v["entrada"] - v["saida"]
        media = v["saida"] or 1
        proj = int(media * 6 * 1.2)

        status = "OK"
        if saldo < proj:
            status = "COMPRAR"

        final.append({
            "ger": ger,
            "item": item,
            "saldo": saldo,
            "status": status
        })

    return final

# =========================
# ITENS
# =========================
def itens_por_gerenciadora():
    dados = Movimentacao.query.all()
    itens = {g: set() for g in GERENCIADORAS}

    for d in dados:
        itens[d.gerenciadora].add(d.item)

    return {k: list(v) for k, v in itens.items()}

# =========================
# SISTEMA
# =========================
@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    dados = calcular()
    itens_existentes = itens_por_gerenciadora()

    grupos = {g: [] for g in GERENCIADORAS}
    for d in dados:
        grupos[d["ger"]].append(d)

    if session["tipo"] == "admin":
        campo_item = '<input name="item" placeholder="ITEM (MAIÚSCULO)" required>'
    else:
        campo_item = '<select name="item" id="itemSelect"></select>'

    html = f"""
    <html>
    <head>
    <style>
    body{{margin:0;font-family:Arial;background:#f1f4f9;}}
    .topbar{{background:linear-gradient(90deg,#1e3c72,#2a5298);
    color:white;padding:20px;text-align:center;font-size:22px;font-weight:bold;}}
    .container{{width:95%;margin:auto;}}
    .card{{background:white;padding:20px;margin:20px auto;
    border-radius:12px;box-shadow:0 5px 15px rgba(0,0,0,0.1);max-width:700px;}}
    input,select{{width:100%;padding:10px;margin:8px 0;border-radius:8px;border:1px solid #ccc;}}
    button{{padding:10px;background:#2a5298;color:white;border:none;border-radius:8px;}}
    table{{width:100%;border-collapse:collapse;margin-top:20px;}}
    th{{background:#2a5298;color:white;padding:10px;}}
    td{{padding:10px;text-align:center;border-bottom:1px solid #eee;}}
    .ok{{color:green;font-weight:bold}}
    .comprar{{color:red;font-weight:bold}}
    </style>
    </head>
    <body>

    <div class="topbar">
        📦 ESTOQUE | {session["user"].upper()}
    </div>

    <div class="container">

    <div class="card">
    <form method="POST" action="/inserir">
    <select name="ger" id="gerSelect">
    {''.join([f"<option>{g}</option>" for g in GERENCIADORAS])}
    </select>

    <select name="tipo">
    <option>ENTRADA</option>
    <option>SAIDA</option>
    </select>

    {campo_item}

    <input name="qtd" type="number" required>
    <button>Inserir</button>
    </form>

    <br><a href="/excel">📊 Exportar Excel</a>
    </div>
    """

    # ===== TABELAS =====
    for nome, lista in grupos.items():
        html += f"<div class='card'><h3>{nome}</h3><table>"
        html += "<tr><th>ITEM</th><th>SALDO</th><th>STATUS</th></tr>"

        for d in lista:
            cls = "ok" if d["status"] == "OK" else "comprar"
            html += f"<tr><td>{d['item']}</td><td>{d['saldo']}</td><td class='{cls}'>{d['status']}</td></tr>"

        html += "</table></div>"

    # ===== SCRIPT CORRIGIDO =====
    html += f"""
    </div>

    <script>
    const itens = {json.dumps(itens_existentes)};
    const ger = document.getElementById("gerSelect");
    const item = document.getElementById("itemSelect");

    function atualizar(){{
        if(!item) return;
        item.innerHTML="";
        (itens[ger.value] || []).forEach(i => {{
            let o = document.createElement("option");
            o.text = i;
            item.add(o);
        }});
    }}

    ger.onchange = atualizar;
    window.onload = atualizar;
    </script>

    </body></html>
    """

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

    if session["tipo"] == "admin":
        if item != item.upper():
            return "Use MAIÚSCULO"

    db.session.add(Movimentacao(
        data=str(datetime.now()),
        gerenciadora=ger,
        tipo=tipo,
        item=item,
        quantidade=qtd
    ))

    db.session.commit()
    return redirect("/sistema")

# =========================
# EXCEL
# =========================
@app.route("/excel")
def excel():
    df = pd.DataFrame(calcular())
    arquivo = "estoque.xlsx"
    df.to_excel(arquivo, index=False)
    return send_file(arquivo, as_attachment=True)
