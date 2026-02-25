from flask import Flask, render_template, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
import os
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo123"

# 🔥 PostgreSQL Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =========================
# MODELOS
# =========================

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(20))  # admin ou operador

class Estoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)
    gerenciadora = db.Column(db.String(100))
    imagem = db.Column(db.String(200))

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(50))
    gerenciadora = db.Column(db.String(100))
    tipo = db.Column(db.String(10))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

# =========================
# CRIA BANCO AUTOMÁTICO
# =========================
with app.app_context():
    db.create_all()

    # cria admin padrão se não existir
    if not Usuario.query.filter_by(username="admin").first():
        admin = Usuario(username="admin", senha="admin123", tipo="admin")
        db.session.add(admin)
        db.session.commit()

# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["user"]
        senha = request.form["senha"]

        u = Usuario.query.filter_by(username=user, senha=senha).first()

        if u:
            session["user"] = u.username
            session["tipo"] = u.tipo
            return redirect("/dashboard")

    return """
    <h2>Login</h2>
    <form method="post">
    Usuário <input name="user"><br>
    Senha <input name="senha"><br>
    <button>Entrar</button>
    </form>
    """

# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    itens = Estoque.query.all()
    return render_template("dashboard.html", itens=itens, tipo=session["tipo"])

# =========================
# ADD ITEM
# =========================
@app.route("/add", methods=["POST"])
def add():
    nome = request.form["nome"]
    qtd = int(request.form["qtd"])
    ger = request.form["gerenciadora"]
    img = request.form["imagem"]

    item = Estoque(nome=nome, quantidade=qtd, gerenciadora=ger, imagem=img)
    db.session.add(item)
    db.session.commit()

    return redirect("/dashboard")

# =========================
# MOVIMENTAÇÃO
# =========================
@app.route("/mov", methods=["POST"])
def mov():
    item_id = int(request.form["id"])
    tipo = request.form["tipo"]
    qtd = int(request.form["qtd"])

    item = Estoque.query.get(item_id)

    if tipo == "entrada":
        item.quantidade += qtd
    else:
        item.quantidade -= qtd

    mov = Movimentacao(
        data=str(datetime.now()),
        gerenciadora=item.gerenciadora,
        tipo=tipo,
        item=item.nome,
        quantidade=qtd
    )

    db.session.add(mov)
    db.session.commit()

    return redirect("/dashboard")

# =========================
# CRIAR USUÁRIO (ADMIN)
# =========================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Sem permissão"

    user = request.form["user"]
    senha = request.form["senha"]
    tipo = request.form["tipo"]

    novo = Usuario(username=user, senha=senha, tipo=tipo)
    db.session.add(novo)
    db.session.commit()

    return redirect("/dashboard")

# =========================
# EXPORTAR EXCEL
# =========================
@app.route("/excel")
def excel():
    dados = Movimentacao.query.all()

    lista = []
    for d in dados:
        lista.append({
            "Data": d.data,
            "Gerenciadora": d.gerenciadora,
            "Tipo": d.tipo,
            "Item": d.item,
            "Quantidade": d.quantidade
        })

    df = pd.DataFrame(lista)

    arquivo = "estoque.xlsx"
    df.to_excel(arquivo, index=False)

    return send_file(arquivo, as_attachment=True)

# =========================
# BACKUP
# =========================
@app.route("/backup")
def backup():
    if session.get("tipo") != "admin":
        return "Sem permissão"

    dados = Movimentacao.query.all()

    lista = []
    for d in dados:
        lista.append(d.__dict__)

    df = pd.DataFrame(lista)
    df.to_excel("backup.xlsx")

    return send_file("backup.xlsx", as_attachment=True)

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =========================
# RENDER PORTA
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
