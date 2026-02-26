from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os
import json

# =========================
# APP (PRIMEIRO!)
# =========================
app = Flask(__name__)
app.secret_key = "segredo"

# =========================
# BANCO (RENDER OK)
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
else:
    DATABASE_URL = "sqlite:///local.db"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELS
# =========================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(20))

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)
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
        db.session.add(Usuario(usuario="admin", senha="123", tipo="admin"))
        db.session.commit()

# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = Usuario.query.filter_by(
            usuario=request.form["usuario"],
            senha=request.form["senha"]
        ).first()

        if user:
            session["user"] = user.usuario
            session["tipo"] = user.tipo
            return redirect("/sistema")

    return """
    <html>
    <style>
    body{font-family:Arial;background:linear-gradient(120deg,#2980b9,#6dd5fa);
    display:flex;justify-content:center;align-items:center;height:100vh;}
    .box{background:white;padding:40px;border-radius:12px;width:300px;text-align:center;}
    input{width:100%;padding:10px;margin:10px 0;border-radius:8px;border:1px solid #ccc;}
    button{background:#2980b9;color:white;padding:10px;width:100%;border:none;border-radius:8px;}
    </style>
    <div class="box">
    <h2>Login</h2>
    <form method="post">
    <input name="usuario" placeholder="Usuário">
    <input name="senha" type="password" placeholder="Senha">
    <button>Entrar</button>
    </form>
    </div>
    </html>
    """

# =========================
# SISTEMA (CORRIGIDO)
# =========================
@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    dados = calcular()

    # separar por gerenciadora
    grupos = {}
    for d in dados:
        grupos.setdefault(d["ger"], []).append(d)

    # itens para operador
    itens = {}
    for d in Movimentacao.query.all():
        itens.setdefault(d.gerenciadora, set()).add(d.item)

    itens = {k:list(v) for k,v in itens.items()}

    # campo item
    if session["tipo"] == "admin":
        campo_item = "<input name='item' required>"
    else:
        campo_item = "<select name='item' id='itemSelect'></select>"

    html = f"""
    <html>
    <style>
    body{{margin:0;font-family:Arial;background:#eef2f7}}
    .topbar{{background:linear-gradient(90deg,#1e3c72,#2a5298);
    color:white;padding:20px;text-align:center;font-size:22px}}
    .card{{background:white;margin:20px;padding:20px;border-radius:10px}}
    table{{width:100%;border-collapse:collapse}}
    th{{background:#2a5298;color:white}}
    td,th{{padding:8px;text-align:center;border-bottom:1px solid #ddd}}
    button{{padding:8px;background:#2a5298;color:white;border:none;border-radius:6px}}
    input,select{{padding:8px;margin:5px;width:100%}}
    .ok{{color:green}} .comprar{{color:red}}
    </style>

    <div class="topbar">📦 ESTOQUE | {session["user"]}</div>

    <div class="card">
    <form method="POST" action="/inserir">
    <select name="ger" id="gerSelect">
    {"".join([f"<option>{g}</option>" for g in GERENCIADORAS])}
    </select>

    <select name="tipo">
    <option>ENTRADA</option>
    <option>SAIDA</option>
    </select>

    {campo_item}

    <input name="qtd" type="number" required>
    <button>Salvar</button>
    </form>
    </div>
    """

    # estoque separado
    for g in GERENCIADORAS:
        lista = grupos.get(g, [])

        html += f"<div class='card'><h3>{g}</h3><table>"
        html += "<tr><th>Item</th><th>Entrada</th><th>Saída</th><th>Saldo</th><th>Média</th><th>6M+20%</th><th>Status</th></tr>"

        for d in lista:
            cls = "ok" if d["status"]=="OK" else "comprar"
            html += f"<tr><td>{d['item']}</td><td>{d['entrada']}</td><td>{d['saida']}</td><td>{d['saldo']}</td><td>{d['media']}</td><td>{d['proj']}</td><td class='{cls}'>{d['status']}</td></tr>"

        html += "</table></div>"

    # ADMIN
    if session["tipo"] == "admin":
        usuarios = Usuario.query.all()
        linhas=""

        for u in usuarios:
            if u.usuario=="admin":
                acao="ADMIN"
            elif u.usuario==session["user"]:
                acao="VOCÊ"
            else:
                acao=f"""
                <form method='POST' action='/excluir_usuario'>
                <input type='hidden' name='usuario' value='{u.usuario}'>
                <button style='background:red'>Excluir</button>
                </form>
                """

            linhas += f"<tr><td>{u.usuario}</td><td>{u.tipo}</td><td>{acao}</td></tr>"

        html += f"""
        <div class='card'>
        <h3>Usuários</h3>
        <table><tr><th>Nome</th><th>Tipo</th><th>Ação</th></tr>{linhas}</table>

        <h3>Criar</h3>
        <form method="POST" action="/criar_usuario">
        <input name="usuario" required>
        <input name="senha" required>
        <select name="tipo">
        <option value="admin">Admin</option>
        <option value="operador">Operador</option>
        </select>
        <button>Criar</button>
        </form>
        </div>
        """

    # JS corrigido
    html += f"""
    <script>
    const itens = {json.dumps(itens)};
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
    </html>
    """

    return html

# =========================
# INSERIR
# =========================
@app.route("/inserir", methods=["POST"])
def inserir():
    db.session.add(Movimentacao(
        gerenciadora=request.form["ger"],
        tipo=request.form["tipo"],
        item=request.form["item"].upper(),
        quantidade=int(request.form["qtd"])
    ))
    db.session.commit()
    return redirect("/sistema")

# =========================
# CRIAR USUARIO
# =========================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")

    try:
        db.session.add(Usuario(
            usuario=request.form["usuario"],
            senha=request.form["senha"],
            tipo=request.form["tipo"]
        ))
        db.session.commit()
    except:
        db.session.rollback()

    return redirect("/sistema")

# =========================
# EXCLUIR USUARIO
# =========================
@app.route("/excluir_usuario", methods=["POST"])
def excluir_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")

    user = request.form["usuario"]

    if user == "admin" or user == session["user"]:
        return redirect("/sistema")

    u = Usuario.query.filter_by(usuario=user).first()
    if u:
        db.session.delete(u)
        db.session.commit()

    return redirect("/sistema")

# =========================
# CALCULO
# =========================
def calcular():
    dados = Movimentacao.query.all()
    res = {}

    for d in dados:
        chave = (d.gerenciadora, d.item)
        if chave not in res:
            res[chave] = {"entrada":0,"saida":0}

        if d.tipo == "ENTRADA":
            res[chave]["entrada"] += d.quantidade
        else:
            res[chave]["saida"] += d.quantidade

    final = []

    for (g,i),v in res.items():
        saldo = v["entrada"] - v["saida"]
        media = v["saida"]
        proj = int(media * 6 * 1.2)

        status = "OK" if saldo >= proj else "COMPRAR"

        final.append({
            "ger":g,
            "item":i,
            "entrada":v["entrada"],
            "saida":v["saida"],
            "saldo":saldo,
            "media":media,
            "proj":proj,
            "status":status
        })

    return final

# =========================
# START (RENDER)
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
