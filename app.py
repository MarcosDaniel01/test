from flask import Flask, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "estoque_secret"

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# USUARIOS
usuarios = {
    "admin": {"senha": "admin123", "tipo": "admin"},
    "operador": {"senha": "op123", "tipo": "operador"}
}

# TABELA ITEM
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)

# HISTORICO
class Movimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)
    tipo = db.Column(db.String(20))
    usuario = db.Column(db.String(50))
    data = db.Column(db.DateTime, default=datetime.utcnow)

# LOGIN
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form["user"]
        senha = request.form["senha"]

        if user in usuarios and usuarios[user]["senha"] == senha:
            session["user"] = user
            session["tipo"] = usuarios[user]["tipo"]
            return redirect("/estoque")

        return "Login inválido"

    return '''
    <h2>Login</h2>
    <form method="post">
    Usuario <input name="user"><br>
    Senha <input name="senha" type="password"><br>
    <button>Entrar</button>
    </form>
    '''

# ESTOQUE
@app.route("/estoque")
def estoque():
    if "user" not in session:
        return redirect("/")

    itens = Item.query.all()

    html = "<h1>Estoque</h1>"

    for i in itens:
        html += f"{i.nome} - {i.quantidade}<br>"

    html += '''
    <h2>Adicionar</h2>
    <form action="/confirmar_add" method="post">
    Item <input name="item"><br>
    Quantidade <input name="quantidade"><br>
    <button>Continuar</button>
    </form>

    <h2>Remover</h2>
    <form action="/confirmar_remover" method="post">
    Item <input name="item"><br>
    Quantidade <input name="quantidade"><br>
    <button>Continuar</button>
    </form>

    <br><a href="/historico">Ver histórico</a>
    <br><a href="/logout">Sair</a>
    '''

    return html

# CONFIRMAR ADIÇÃO
@app.route("/confirmar_add", methods=["POST"])
def confirmar_add():

    item = request.form["item"]
    quantidade = int(request.form["quantidade"])

    return f'''
    <h2>Confirmação</h2>

    Item: {item}<br>
    Quantidade: {quantidade}<br><br>

    É isso mesmo?

    <form action="/add" method="post">
    <input type="hidden" name="item" value="{item}">
    <input type="hidden" name="quantidade" value="{quantidade}">
    <button>Confirmar</button>
    </form>

    <a href="/estoque">Cancelar</a>
    '''

# ADICIONAR
@app.route("/add", methods=["POST"])
def add():

    item = request.form["item"]
    quantidade = int(request.form["quantidade"])

    registro = Item.query.filter_by(nome=item).first()

    if registro:
        registro.quantidade += quantidade
    else:
        registro = Item(nome=item, quantidade=quantidade)
        db.session.add(registro)

    mov = Movimento(
        item=item,
        quantidade=quantidade,
        tipo="entrada",
        usuario=session["user"]
    )

    db.session.add(mov)
    db.session.commit()

    return "Item adicionado com sucesso <br><a href='/estoque'>Voltar</a>"

# CONFIRMAR REMOÇÃO
@app.route("/confirmar_remover", methods=["POST"])
def confirmar_remover():

    item = request.form["item"]
    quantidade = int(request.form["quantidade"])

    return f'''
    <h2>Confirmação</h2>

    Item: {item}<br>
    Quantidade: {quantidade}<br><br>

    Tem certeza que deseja remover?

    <form action="/remover" method="post">
    <input type="hidden" name="item" value="{item}">
    <input type="hidden" name="quantidade" value="{quantidade}">
    <button>Confirmar</button>
    </form>

    <a href="/estoque">Cancelar</a>
    '''

# REMOVER
@app.route("/remover", methods=["POST"])
def remover():

    item = request.form["item"]
    quantidade = int(request.form["quantidade"])

    registro = Item.query.filter_by(nome=item).first()

    if not registro:
        return "Item não existe <br><a href='/estoque'>Voltar</a>"

    if registro.quantidade < quantidade:
        return "Estoque insuficiente <br><a href='/estoque'>Voltar</a>"

    registro.quantidade -= quantidade

    mov = Movimento(
        item=item,
        quantidade=quantidade,
        tipo="saida",
        usuario=session["user"]
    )

    db.session.add(mov)
    db.session.commit()

    return "Item removido com sucesso <br><a href='/estoque'>Voltar</a>"

# HISTORICO
@app.route("/historico")
def historico():

    movs = Movimento.query.order_by(Movimento.data.desc()).all()

    html = "<h1>Histórico</h1>"

    for m in movs:
        html += f"{m.data} - {m.usuario} - {m.tipo} - {m.item} - {m.quantidade}<br>"

    html += "<br><a href='/estoque'>Voltar</a>"

    return html

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# INICIAR
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
