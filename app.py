from flask import Flask, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

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
# LOGIN BONITO
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
# SISTEMA
# =========================
@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    criar_usuario_html = ""
    lista_usuarios_html = ""

    if session["tipo"] == "admin":

        usuarios = Usuario.query.all()

        linhas = ""
        for u in usuarios:
            if u.usuario == "admin":
                botao = "<b>ADMIN PRINCIPAL</b>"
            elif u.usuario == session["user"]:
                botao = "<b>VOCÊ</b>"
            else:
                botao = f"""
                <form method='POST' action='/excluir_usuario' style='display:inline;'>
                    <input type='hidden' name='usuario' value='{u.usuario}'>
                    <button style='background:#c0392b;'>Excluir</button>
                </form>
                """

            linhas += f"""
            <tr>
                <td>{u.usuario}</td>
                <td>{u.tipo}</td>
                <td>{botao}</td>
            </tr>
            """

        lista_usuarios_html = f"""
        <div class='card'>
        <h3>Usuários</h3>
        <table>
            <tr>
                <th>Usuário</th>
                <th>Tipo</th>
                <th>Ação</th>
            </tr>
            {linhas}
        </table>
        </div>
        """

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
            <button>Criar</button>
        </form>
        </div>
        """

    return f"""
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
    button{{padding:8px 15px;background:#2a5298;color:white;border:none;border-radius:8px;}}
    table{{width:100%;border-collapse:collapse;margin-top:15px;}}
    th{{background:#2a5298;color:white;padding:10px;}}
    td{{padding:10px;text-align:center;border-bottom:1px solid #eee;}}
    </style>
    </head>
    <body>

    <div class="topbar">
        📦 ESTOQUE | Usuário: {session["user"].upper()}
    </div>

    <div class="container">
        {criar_usuario_html}
        {lista_usuarios_html}
    </div>

    </body>
    </html>
    """

# =========================
# CRIAR USUARIO
# =========================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")

    usuario = request.form["usuario"]
    senha = request.form["senha"]
    tipo = request.form["tipo"]

    if Usuario.query.filter_by(usuario=usuario).first():
        return "Usuário já existe!"

    try:
        db.session.add(Usuario(usuario=usuario, senha=senha, tipo=tipo))
        db.session.commit()
    except:
        db.session.rollback()
        return "Erro ao criar usuário"

    return redirect("/sistema")

# =========================
# EXCLUIR USUARIO
# =========================
@app.route("/excluir_usuario", methods=["POST"])
def excluir_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")

    usuario = request.form["usuario"]

    if usuario == "admin":
        return "Não pode excluir o admin!"

    if usuario == session["user"]:
        return "Não pode excluir você mesmo!"

    try:
        user = Usuario.query.filter_by(usuario=usuario).first()
        if user:
            db.session.delete(user)
            db.session.commit()
    except:
        db.session.rollback()
        return "Erro ao excluir"

    return redirect("/sistema")
