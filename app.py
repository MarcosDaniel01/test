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

# =========================
# INIT BANCO
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
# ITENS EXISTENTES
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
        criar_usuario_html = """
        <div class='card'>
        <h3>Criar Usuário</h3>
        <form method="POST" action="/criar_usuario">
            <input name="usuario" placeholder="Usuário" required>
            <input name="senha" placeholder="Senha" required>
            <select name="tipo">
                <option value="admin">Admin</option>
                <option value="operador">Operador</option>
            </select>
            <button>Criar Usuário</button>
        </form>
        </div>
        """
    else:
        campo_item = '<select name="item" id="itemSelect"></select>'
        criar_usuario_html = ""

    html = f"""
    <html>
    <head>
    <style>
    body{{margin:0;font-family:Arial;background:#f1f4f9;}}
    .topbar{{background:linear-gradient(90deg,#1e3c72,#2a5298);
    color:white;padding:20px;text-align:center;font-size:22px;font-weight:bold;}}
    .container{{width:95%;margin:auto;}}
    .card{{background:white;padding:20px;margin:20px auto;
    border-radius:12px;box-shadow:0 5px 15px rgba(0,0,0,0.1);max-width:500px;}}
    select,input{{width:100%;padding:10px;margin:8px 0;
    border-radius:8px;border:1px solid #ccc;}}
    button{{width:100%;padding:12px;background:#2a5298;
    color:white;border:none;border-radius:8px;font-weight:bold;cursor:pointer;}}
    table{{width:100%;border-collapse:collapse;margin:20px 0;
    background:white;border-radius:12px;overflow:hidden;
    box-shadow:0 5px 15px rgba(0,0,0,0.1);}}
    th{{background:#2a5298;color:white;padding:10px;}}
    td{{padding:10px;text-align:center;border-bottom:1px solid #eee;}}
    .ok{{color:green;font-weight:bold;}}
    .comprar{{color:red;font-weight:bold;}}
    </style>
    </head>
    <body>

    <div class="topbar">
        📦 ESTOQUE | Usuário: {session["user"].upper()}
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

                <button>Inserir Movimentação</button>
            </form>
        </div>

        {criar_usuario_html}
    """

    for nome, lista in grupos.items():
        html += f"<h3>{nome}</h3><table><tr><th>ITEM</th><th>SALDO</th><th>STATUS</th></tr>"
        for d in lista:
            classe = "ok" if d["status"] == "OK" else "comprar"
            html += f"<tr><td>{d['item']}</td><td>{d['saldo']}</td><td class='{classe}'>{d['status']}</td></tr>"
        html += "</table>"

    html += """
    </div>
    <script>
    const itens = """ + json.dumps(itens_existentes) + """;
    const gerSelect = document.getElementById("gerSelect");
    const itemSelect = document.getElementById("itemSelect");

    function atualizarItens(){
        if(!itemSelect) return;
        let ger = gerSelect.value;
        itemSelect.innerHTML = "";
        if(itens[ger]){
            itens[ger].forEach(i=>{
                let opt=document.createElement("option");
                opt.value=i;
                opt.text=i;
                itemSelect.appendChild(opt);
            });
        }
    }
    gerSelect.addEventListener("change", atualizarItens);
    window.onload = atualizarItens;
    </script>
    </body>
    </html>
    """

    return html

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
# RESTANTE IGUAL
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
        proj = int(v["saida"] * 6 * 1.2)
        status = "OK" if saldo >= proj else "COMPRAR"

        final.append({"ger":ger,"item":item,"saldo":saldo,"status":status})

    return final
