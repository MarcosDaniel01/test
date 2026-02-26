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

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(usuario="admin").first():
        admin = Usuario(usuario="admin", senha="123", tipo="admin")
        db.session.add(admin)
        db.session.commit()

# =========================
# LOGIN BONITO
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
    <html>
    <head>
    <style>
    body{
        margin:0;
        font-family:Arial;
        background:linear-gradient(135deg,#1e3c72,#2a5298);
        display:flex;
        justify-content:center;
        align-items:center;
        height:100vh;
    }
    .login-box{
        background:white;
        padding:40px;
        border-radius:15px;
        width:350px;
        text-align:center;
        box-shadow:0 10px 30px rgba(0,0,0,0.3);
    }
    h2{margin-bottom:20px;}
    input{
        width:100%;
        padding:10px;
        margin:10px 0;
        border-radius:8px;
        border:1px solid #ccc;
    }
    button{
        width:100%;
        padding:12px;
        background:#2a5298;
        color:white;
        border:none;
        border-radius:8px;
        font-weight:bold;
        cursor:pointer;
    }
    button:hover{background:#1e3c72;}
    </style>
    </head>
    <body>
    <div class="login-box">
        <h2>📦 ESTOQUE INTELIGENTE</h2>
        <form method="post">
            <input name="usuario" placeholder="Usuário" required>
            <input name="senha" type="password" placeholder="Senha" required>
            <button>ENTRAR</button>
        </form>
    </div>
    </body>
    </html>
    """

# =========================
# FUNÇÃO ITENS EXISTENTES
# =========================
def itens_por_gerenciadora():
    dados = Movimentacao.query.all()
    itens = {}
    for d in dados:
        if d.gerenciadora not in itens:
            itens[d.gerenciadora] = set()
        itens[d.gerenciadora].add(d.item)
    return {g: sorted(list(v)) for g, v in itens.items()}

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
    body{{font-family:Arial;background:#f4f4f4;text-align:center;}}
    table{{width:95%;margin:20px auto;border-collapse:collapse;background:white;}}
    th,td{{padding:8px;border:1px solid #ccc;}}
    th{{background:black;color:white;}}
    form{{background:white;padding:20px;width:400px;margin:auto;border-radius:10px;}}
    button{{background:green;color:white;padding:10px;width:100%;}}
    </style>
    </head>
    <body>

    <h1>📦 ESTOQUE INTELIGENTE</h1>

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

    <button>INSERIR</button>
    </form>

    <br><a href="/excel">📊 EXPORTAR EXCEL</a>
    <br><a href="/backup">💾 BACKUP</a>
    <br><a href="/">🚪 SAIR</a>
    """

    for nome, lista in grupos.items():
        html += f"<h2>{nome}</h2>"
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

    html += f"""
    <script>
    const itens = {json.dumps(itens_existentes)};
    const gerSelect = document.getElementById("gerSelect");
    const itemSelect = document.getElementById("itemSelect");

    function atualizarItens(){{
        if(!itemSelect) return;
        let ger = gerSelect.value;
        itemSelect.innerHTML = "";
        if(itens[ger]){{
            itens[ger].forEach(i=>{{
                let opt=document.createElement("option");
                opt.value=i;
                opt.text=i;
                itemSelect.appendChild(opt);
            }});
        }}
    }}

    gerSelect.addEventListener("change", atualizarItens);
    window.onload = atualizarItens;
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

    if session.get("tipo") == "operador":
        itens = itens_por_gerenciadora()
        if item not in itens.get(ger, []):
            return "Operador não pode criar item novo"

    if item != item.upper():
        return "USE MAIÚSCULO"

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
        media = v["saida"]
        proj = int(media * 6 * 1.2)
        status = "OK" if saldo >= proj else "COMPRAR"

        final.append({
            "ger":ger,
            "item":item,
            "entrada":v["entrada"],
            "saida":v["saida"],
            "saldo":saldo,
            "media":media,
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
