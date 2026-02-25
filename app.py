import os
from flask import Flask, render_template_string, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from datetime import datetime
import shutil

app = Flask(__name__)
app.secret_key = "segredo"

# Banco persistente (arquivo)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///estoque.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------ MODELOS ------------------

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(10))  # admin ou operador

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)
    gerenciadora = db.Column(db.String(100))
    imagem = db.Column(db.String(200))

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100))
    tipo = db.Column(db.String(10))  # entrada / saída
    quantidade = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------ BACKUP ------------------

def fazer_backup():
    if os.path.exists("estoque.db"):
        shutil.copy("estoque.db", "backup_estoque.db")

# ------------------ LOGIN PADRÃO ------------------

@app.before_first_request
def criar_admin():
    db.create_all()
    if not Usuario.query.filter_by(username="admin").first():
        admin = Usuario(username="admin", senha="123", tipo="admin")
        db.session.add(admin)
        db.session.commit()

# ------------------ ROTAS ------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Usuario.query.filter_by(
            username=request.form["user"],
            senha=request.form["senha"]
        ).first()

        if user:
            session["user"] = user.username
            session["tipo"] = user.tipo
            return redirect("/estoque")

    return """
    <h2>Login</h2>
    <form method="post">
        Usuário: <input name="user"><br>
        Senha: <input name="senha"><br>
        <button>Entrar</button>
    </form>
    """

# ------------------ CRIAR USUÁRIO ------------------

@app.route("/criar_usuario", methods=["GET", "POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return "Apenas admin"

    if request.method == "POST":
        novo = Usuario(
            username=request.form["user"],
            senha=request.form["senha"],
            tipo=request.form["tipo"]
        )
        db.session.add(novo)
        db.session.commit()
        return redirect("/estoque")

    return """
    <h2>Criar Usuário</h2>
    <form method="post">
        Usuário: <input name="user"><br>
        Senha: <input name="senha"><br>
        Tipo:
        <select name="tipo">
            <option value="admin">Admin</option>
            <option value="operador">Operador</option>
        </select><br>
        <button>Criar</button>
    </form>
    """

# ------------------ ESTOQUE ------------------

@app.route("/estoque", methods=["GET", "POST"])
def estoque():
    if "user" not in session:
        return redirect("/")

    if request.method == "POST":
        img = request.files["imagem"]
        path = ""

        if img:
            path = os.path.join(UPLOAD_FOLDER, img.filename)
            img.save(path)

        item = Item(
            nome=request.form["nome"],
            quantidade=int(request.form["quantidade"]),
            gerenciadora=request.form["gerenciadora"],
            imagem=path
        )
        db.session.add(item)

        mov = Movimentacao(
            item=item.nome,
            tipo="entrada",
            quantidade=item.quantidade
        )
        db.session.add(mov)

        db.session.commit()
        fazer_backup()

    itens = Item.query.all()

    html = """
    <h2>Estoque</h2>
    <a href='/criar_usuario'>Criar usuário</a> |
    <a href='/excel'>Exportar Excel</a><br><br>

    <form method="post" enctype="multipart/form-data">
        Nome: <input name="nome">
        Qtd: <input name="quantidade">
        Gerenciadora: <input name="gerenciadora">
        Imagem: <input type="file" name="imagem">
        <button>Adicionar</button>
    </form>

    <table border=1>
    <tr style="background-color: lightblue;">
        <th>Nome</th>
        <th>Qtd</th>
        <th>Gerenciadora</th>
        <th>Imagem</th>
    </tr>
    """

    for i in itens:
        html += f"""
        <tr>
            <td>{i.nome}</td>
            <td>{i.quantidade}</td>
            <td>{i.gerenciadora}</td>
            <td><img src='/{i.imagem}' width=50></td>
        </tr>
        """

    html += "</table>"
    return html

# ------------------ EXCEL ------------------

@app.route("/excel")
def excel():
    itens = Item.query.all()
    movs = Movimentacao.query.all()

    df1 = pd.DataFrame([{
        "Nome": i.nome,
        "Qtd": i.quantidade,
        "Gerenciadora": i.gerenciadora
    } for i in itens])

    df2 = pd.DataFrame([{
        "Item": m.item,
        "Tipo": m.tipo,
        "Qtd": m.quantidade,
        "Mes": m.data.strftime("%Y-%m")
    } for m in movs])

    arquivo = "estoque.xlsx"

    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        df1.to_excel(writer, sheet_name="Estoque", index=False)

        resumo = df2.groupby(["Mes", "Tipo"]).sum().reset_index()
        resumo.to_excel(writer, sheet_name="Movimentacao", index=False)

    return send_file(arquivo, as_attachment=True)

# ------------------ RENDER PORTA ------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
