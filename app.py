from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os
import json

app = Flask(__name__)
app.secret_key = "segredo_super"

# =========================
# BANCO (Render compatível)
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
    data = db.Column(db.DateTime, default=datetime.utcnow)
    gerenciadora = db.Column(db.String(50))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# =========================
# INICIALIZAÇÃO
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
        user = Usuario.query.filter_by(
            usuario=request.form["usuario"],
            senha=request.form["senha"]
        ).first()

        if user:
            session["user"] = user.usuario
            session["tipo"] = user.tipo
            return redirect("/sistema")
        else:
            erro = "Usuário ou senha inválidos"

    return f"""
    <html>
    <head>
    <style>
    body{{margin:0;font-family:Arial;background:linear-gradient(135deg,#1e3c72,#2a5298);
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
# CÁLCULO ESTOQUE
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

    for (ger,item),v in resultado.items():
        saldo = v["entrada"] - v["saida"]

        entrada_mensal = v["entrada"]
        saida_mensal = v["saida"]

        previsao6 = int((saida_mensal * 6) * 1.2)

        status = "OK"
        if saldo < previsao6:
            status = "COMPRAR"

        final.append({
            "ger":ger,
            "item":item,
            "saldo":saldo,
            "entrada_mensal":entrada_mensal,
            "saida_mensal":saida_mensal,
            "previsao6":previsao6,
            "status":status
        })

    return final

# =========================
# SISTEMA
# =========================
@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    dados = calcular()
    grupos = {g:[] for g in GERENCIADORAS}
    for d in dados:
        grupos[d["ger"]].append(d)

    html = f"""
    <html>
    <head>
    <style>
    body{{margin:0;font-family:Arial;background:#f1f4f9;}}
    .topbar{{background:#2a5298;color:white;padding:20px;text-align:center;font-size:22px;}}
    .container{{width:95%;margin:auto;}}
    .card{{background:white;padding:20px;margin:20px auto;border-radius:12px;
    box-shadow:0 5px 15px rgba(0,0,0,0.1);max-width:1100px;}}
    input,select{{padding:8px;margin:5px;border-radius:6px;border:1px solid #ccc;}}
    button{{padding:8px 12px;background:#2a5298;color:white;border:none;border-radius:6px;}}
    table{{width:100%;border-collapse:collapse;margin-top:15px;}}
    th{{background:#2a5298;color:white;padding:8px;}}
    td{{padding:8px;text-align:center;border-bottom:1px solid #eee;}}
    .ok{{color:green;font-weight:bold}}
    .comprar{{color:red;font-weight:bold}}
    </style>
    </head>
    <body>
    <div class="topbar">📦 ESTOQUE | {session["user"]}</div>
    <div class="container">

    <div class="card">
    <form method="POST" action="/inserir">
    <select name="ger">{''.join([f"<option>{g}</option>" for g in GERENCIADORAS])}</select>
    <select name="tipo"><option>ENTRADA</option><option>SAIDA</option></select>
    <input name="item" placeholder="ITEM" required>
    <input name="qtd" type="number" required>
    <button>Inserir</button>
    </form>
    <br><a href="/excel">📊 Exportar Excel</a>
    </div>
    """

    # ===== TABELAS ESTOQUE =====
    for nome,lista in grupos.items():
        html += f"<div class='card'><h3>{nome}</h3><table>"
        html += """
        <tr>
        <th>Item</th>
        <th>Saldo</th>
        <th>Entrada Mensal</th>
        <th>Saída Mensal</th>
        <th>Previsão 6M +20%</th>
        <th>Status</th>
        </tr>
        """

        for d in lista:
            cls = "ok" if d["status"]=="OK" else "comprar"
            html += f"""
            <tr>
            <td>{d['item']}</td>
            <td>{d['saldo']}</td>
            <td>{d['entrada_mensal']}</td>
            <td>{d['saida_mensal']}</td>
            <td>{d['previsao6']}</td>
            <td class='{cls}'>{d['status']}</td>
            </tr>
            """

        html += "</table></div>"

    # ===== ADMIN GERENCIAMENTO =====
    if session["tipo"] == "admin":
        usuarios = Usuario.query.all()
        linhas = ""
        for u in usuarios:
            if u.usuario in ["admin", session["user"]]:
                botao = "-"
            else:
                botao = f"""
                <form method='POST' action='/excluir_usuario'>
                <input type='hidden' name='usuario' value='{u.usuario}'>
                <button style='background:red'>Excluir</button>
                </form>
                """
            linhas += f"<tr><td>{u.usuario}</td><td>{u.tipo}</td><td>{botao}</td></tr>"

        html += f"""
        <div class='card'>
        <h3>Usuários</h3>
        <table>
        <tr><th>Usuário</th><th>Tipo</th><th>Ação</th></tr>
        {linhas}
        </table>
        </div>

        <div class='card'>
        <h3>Criar Usuário</h3>
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

    html += "</div></body></html>"
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
# USUÁRIOS
# =========================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")

    if Usuario.query.filter_by(usuario=request.form["usuario"]).first():
        return "Usuário já existe"

    db.session.add(Usuario(
        usuario=request.form["usuario"],
        senha=request.form["senha"],
        tipo=request.form["tipo"]
    ))
    db.session.commit()
    return redirect("/sistema")

@app.route("/excluir_usuario", methods=["POST"])
def excluir_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")

    u = request.form["usuario"]
    if u in ["admin", session["user"]]:
        return "Não permitido"

    user = Usuario.query.filter_by(usuario=u).first()
    if user:
        db.session.delete(user)
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
