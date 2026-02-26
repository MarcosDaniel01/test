from flask import Flask, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import os
import urllib.parse

app = Flask(__name__)
app.secret_key = "segredo_super_sistema"

# =========================
# CONFIG BANCO (RENDER FIX DEFINITIVO)
# =========================

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    url = urllib.parse.urlparse(DATABASE_URL)

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql+psycopg2://{url.username}:{url.password}@{url.hostname}:{url.port}{url.path}"
    )
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///banco.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
}

db = SQLAlchemy(app)

# =========================
# MODELOS
# =========================

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(20))  # admin ou operador

class Estoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer, default=0)

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(50))
    usuario = db.Column(db.String(50))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

# =========================
# CRIA BANCO AUTOMÁTICO
# =========================
with app.app_context():
    db.create_all()

    if not db.session.query(Usuario).filter(Usuario.usuario == "admin").first():
        admin = Usuario(usuario="admin", senha="123", tipo="admin")
        db.session.add(admin)
        db.session.commit()

# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["usuario"]
        senha = request.form["senha"]

        u = db.session.query(Usuario).filter(
            Usuario.usuario == user,
            Usuario.senha == senha
        ).first()

        if u:
            session["user"] = u.usuario
            session["tipo"] = u.tipo
            return redirect("/sistema")

        return "Login inválido"

    return """
    <h2>LOGIN</h2>
    <form method="post">
        <input name="usuario" placeholder="Usuário"><br><br>
        <input name="senha" type="password" placeholder="Senha"><br><br>
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

    estoque = db.session.query(Estoque).all()

    html = """
    <h1>SISTEMA DE ESTOQUE</h1>

    <h3>ENTRADA / SAÍDA</h3>
    <form method="post" action="/movimentar">
        <input name="item" placeholder="Item" required>
        <input name="qtd" type="number" required>
        <select name="tipo">
            <option value="entrada">Entrada</option>
            <option value="saida">Saída</option>
        </select>
        <button>Confirmar</button>
    </form>

    <h3>ESTOQUE ATUAL</h3>
    <table border=1 cellpadding=5>
    <tr><th>Item</th><th>Quantidade</th></tr>
    """

    for e in estoque:
        html += f"<tr><td>{e.item}</td><td>{e.quantidade}</td></tr>"

    html += "</table>"

    html += """
    <br><br>
    <a href='/excel'>Exportar Excel</a><br>
    <a href='/backup'>Backup</a><br>
    """

    if session["tipo"] == "admin":
        html += """
        <h3>Criar Usuário</h3>
        <form method="post" action="/criar_usuario">
            <input name="usuario" placeholder="Usuário">
            <input name="senha" placeholder="Senha">
            <select name="tipo">
                <option value="admin">Admin</option>
                <option value="operador">Operador</option>
            </select>
            <button>Criar</button>
        </form>
        """

    html += "<br><a href='/logout'>Sair</a>"

    return html

# =========================
# MOVIMENTAÇÃO
# =========================
@app.route("/movimentar", methods=["POST"])
def movimentar():
    if "user" not in session:
        return redirect("/")

    item = request.form["item"]
    qtd = int(request.form["qtd"])
    tipo = request.form["tipo"]

    estoque = db.session.query(Estoque).filter(Estoque.item == item).first()

    if not estoque:
        estoque = Estoque(item=item, quantidade=0)
        db.session.add(estoque)

    if tipo == "entrada":
        estoque.quantidade += qtd
    else:
        if estoque.quantidade < qtd:
            return "Estoque insuficiente"
        estoque.quantidade -= qtd

    mov = Movimentacao(
        data=str(datetime.now()),
        usuario=session["user"],
        tipo=tipo,
        item=item,
        quantidade=qtd
    )

    db.session.add(mov)
    db.session.commit()

    return redirect("/sistema")

# =========================
# CRIAR USUÁRIO
# =========================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Sem permissão"

    user = request.form["usuario"]
    senha = request.form["senha"]
    tipo = request.form["tipo"]

    if db.session.query(Usuario).filter(Usuario.usuario == user).first():
        return "Usuário já existe"

    novo = Usuario(usuario=user, senha=senha, tipo=tipo)
    db.session.add(novo)
    db.session.commit()

    return redirect("/sistema")

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =========================
# EXCEL
# =========================
@app.route("/excel")
def excel():
    movs = db.session.query(Movimentacao).all()

    lista = []
    for m in movs:
        lista.append({
            "Data": m.data,
            "Usuário": m.usuario,
            "Tipo": m.tipo,
            "Item": m.item,
            "Quantidade": m.quantidade
        })

    df = pd.DataFrame(lista)
    df.to_excel("estoque.xlsx", index=False)

    return send_file("estoque.xlsx", as_attachment=True)

# =========================
# BACKUP
# =========================
@app.route("/backup")
def backup():
    estoque = db.session.query(Estoque).all()

    lista = []
    for e in estoque:
        lista.append({
            "Item": e.item,
            "Quantidade": e.quantidade
        })

    df = pd.DataFrame(lista)
    df.to_excel("backup.xlsx", index=False)

    return send_file("backup.xlsx", as_attachment=True)

# =========================
# START
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
