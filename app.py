from flask import Flask, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = "123"

# ==============================
# CONFIG BANCO (Render + Local)
# ==============================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///banco.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==============================
# MODELS
# ==============================
class Usuario(db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(50))
    tipo = db.Column(db.String(20))


class Movimentacao(db.Model):
    __tablename__ = "movimentacao"

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(50))
    gerenciadora = db.Column(db.String(50))
    tipo = db.Column(db.String(20))
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

# ==============================
# RESET TOTAL (REMOVE TABELAS ANTIGAS)
# ==============================
with app.app_context():
    db.drop_all()      # remove estrutura antiga quebrada
    db.create_all()    # cria estrutura nova correta

    if not Usuario.query.filter_by(usuario="admin").first():
        admin = Usuario(usuario="admin", senha="123", tipo="admin")
        db.session.add(admin)
        db.session.commit()

# ==============================
# LOGIN
# ==============================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        user = Usuario.query.filter_by(usuario=usuario).first()

        if user and user.senha == senha:
            session["user"] = user.usuario
            session["tipo"] = user.tipo
            return redirect("/menu")

    return """
    <body style="background:white;text-align:center;margin-top:100px;">
        <h2>Login</h2>
        <form method="post">
            <input name="usuario" placeholder="Usuário"><br><br>
            <input name="senha" type="password" placeholder="Senha"><br><br>
            <button>Entrar</button>
        </form>
    </body>
    """

# ==============================
# MENU
# ==============================
@app.route("/menu")
def menu():
    if "user" not in session:
        return redirect("/")

    return f"""
    <body style="background:white;text-align:center;">
        <h2>Bem-vindo {session['user']}</h2>
        <a href="/entrada">Entrada</a><br><br>
        <a href="/saida">Saída</a><br><br>
        <a href="/usuarios">Criar Usuário</a><br><br>
        <a href="/logout">Sair</a>
    </body>
    """

# ==============================
# ENTRADA
# ==============================
@app.route("/entrada", methods=["GET", "POST"])
def entrada():
    if request.method == "POST":
        mov = Movimentacao(
            data=request.form["data"],
            gerenciadora=request.form["gerenciadora"],
            tipo="entrada",
            item=request.form["item"],
            quantidade=int(request.form["quantidade"])
        )
        db.session.add(mov)
        db.session.commit()
        return redirect("/menu")

    return """
    <body style="background:white;text-align:center;">
        <h2>Entrada</h2>
        <form method="post">
            <input name="data" placeholder="Data"><br><br>
            <input name="gerenciadora" placeholder="Gerenciadora"><br><br>
            <input name="item" placeholder="Item"><br><br>
            <input name="quantidade" placeholder="Quantidade"><br><br>
            <button>Salvar</button>
        </form>
    </body>
    """

# ==============================
# SAIDA
# ==============================
@app.route("/saida", methods=["GET", "POST"])
def saida():
    if request.method == "POST":
        mov = Movimentacao(
            data=request.form["data"],
            gerenciadora=request.form["gerenciadora"],
            tipo="saida",
            item=request.form["item"],
            quantidade=int(request.form["quantidade"])
        )
        db.session.add(mov)
        db.session.commit()
        return redirect("/menu")

    return """
    <body style="background:white;text-align:center;">
        <h2>Saída</h2>
        <form method="post">
            <input name="data" placeholder="Data"><br><br>
            <input name="gerenciadora" placeholder="Gerenciadora"><br><br>
            <input name="item" placeholder="Item"><br><br>
            <input name="quantidade" placeholder="Quantidade"><br><br>
            <button>Salvar</button>
        </form>
    </body>
    """

# ==============================
# CRIAR USUÁRIO
# ==============================
@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    if session.get("tipo") != "admin":
        return "Sem permissão"

    if request.method == "POST":
        novo = Usuario(
            usuario=request.form["usuario"],
            senha=request.form["senha"],
            tipo=request.form["tipo"]
        )
        db.session.add(novo)
        db.session.commit()
        return redirect("/menu")

    return """
    <body style="background:white;text-align:center;">
        <h2>Criar Usuário</h2>
        <form method="post">
            <input name="usuario" placeholder="Usuário"><br><br>
            <input name="senha" placeholder="Senha"><br><br>
            <select name="tipo">
                <option value="admin">Admin</option>
                <option value="operador">Operador</option>
            </select><br><br>
            <button>Criar</button>
        </form>
    </body>
    """

# ==============================
# LOGOUT
# ==============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
