import os
from flask import Flask, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import pandas as pd
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersegredo"

# ===============================
# DATABASE (RENDER)
# ===============================

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"

db = SQLAlchemy(app)

if not os.path.exists("static/uploads"):
    os.makedirs("static/uploads")

# ===============================
# MODELOS
# ===============================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    role = db.Column(db.String(20))

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True)
    gerenciadora = db.Column(db.String(50))
    quantidade = db.Column(db.Integer, default=0)
    imagem = db.Column(db.String(200))

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100))
    tipo = db.Column(db.String(10))
    quantidade = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)

# ===============================
# INIT
# ===============================

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="ADMIN").first():
        admin = User(username="ADMIN", password="ADMIN", role="admin")
        db.session.add(admin)
        db.session.commit()

# ===============================
# FUNÇÕES
# ===============================

def validar_nome(nome, gerenciadora):
    nome = nome.upper()
    proibidas = ["PRIME", "LINK", "NEO", "FITMOB"]

    if gerenciadora != "OUTROS":
        for p in proibidas:
            if p in nome:
                return False
    return nome

def backup_auto():
    itens = Item.query.all()
    data = []
    for i in itens:
        data.append({
            "Item": i.nome,
            "Gerenciadora": i.gerenciadora,
            "Quantidade": i.quantidade
        })
    df = pd.DataFrame(data)
    df.to_excel("backup.xlsx", index=False)

# ===============================
# LOGIN
# ===============================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["user"].upper()
        senha = request.form["senha"]
        u = User.query.filter_by(username=user, password=senha).first()
        if u:
            session["user"] = u.username
            session["role"] = u.role
            return redirect("/estoque")

    return """
    <body style='background:#f5f7fa;font-family:Arial'>
    <div style='width:400px;margin:100px auto;background:white;padding:30px;border-radius:10px;box-shadow:0 0 10px #ccc'>
    <h2>Sistema de Estoque</h2>
    <form method='post'>
    Usuário:<br><input name='user' style='width:100%'><br><br>
    Senha:<br><input type='password' name='senha' style='width:100%'><br><br>
    <button style='width:100%;padding:10px;background:#007bff;color:white;border:none'>Entrar</button>
    </form></div></body>
    """

# ===============================
# CRIAR USUÁRIO
# ===============================

@app.route("/criar_usuario", methods=["GET", "POST"])
def criar_usuario():
    if session.get("role") != "admin":
        return "Apenas ADMIN"

    if request.method == "POST":
        novo = User(
            username=request.form["user"].upper(),
            password=request.form["senha"],
            role=request.form["role"]
        )
        db.session.add(novo)
        db.session.commit()
        return redirect("/estoque")

    return """
    <h2>Novo Usuário</h2>
    <form method="post">
    Usuário:<input name="user"><br>
    Senha:<input name="senha"><br>
    Tipo:
    <select name="role">
        <option value="admin">Admin</option>
        <option value="operador">Operador</option>
    </select><br>
    <button>Criar</button>
    </form>
    """

# ===============================
# ESTOQUE
# ===============================

@app.route("/estoque", methods=["GET", "POST"])
def estoque():
    if "user" not in session:
        return redirect("/")

    if request.method == "POST":
        nome = request.form["nome"]
        ger = request.form["gerenciadora"]
        qtd = int(request.form["qtd"])
        tipo = request.form["tipo"]

        nome = validar_nome(nome, ger)
        if not nome:
            return "Nome inválido!"

        imagem_path = None
        if "imagem" in request.files:
            img = request.files["imagem"]
            if img.filename != "":
                filename = secure_filename(img.filename)
                imagem_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                img.save(imagem_path)

        item = Item.query.filter_by(nome=nome).first()
        if not item:
            item = Item(nome=nome, gerenciadora=ger, quantidade=0, imagem=imagem_path)
            db.session.add(item)

        if tipo == "entrada":
            item.quantidade += qtd
        else:
            item.quantidade -= qtd

        mov = Movimentacao(item=nome, tipo=tipo, quantidade=qtd)
        db.session.add(mov)

        db.session.commit()
        backup_auto()

    itens = Item.query.all()

    cores = {
        "PRIME": "#007bff",
        "LINK": "#28a745",
        "NEO": "#ffc107",
        "FITMOB": "#6f42c1",
        "OUTROS": "#6c757d"
    }

    html = "<body style='background:#f5f7fa;font-family:Arial'>"
    html += "<h1 style='text-align:center'>Controle de Estoque</h1>"

    grupos = {"PRIME": [], "LINK": [], "NEO": [], "FITMOB": [], "OUTROS": []}
    for i in itens:
        grupos[i.gerenciadora].append(i)

    for g in grupos:
        html += f"<h2 style='color:{cores[g]}'>{g}</h2>"
        for i in grupos[g]:
            html += f"""
            <div style='background:white;padding:10px;margin:5px;border-radius:8px'>
            <b>{i.nome}</b><br>
            Estoque: {i.quantidade}<br>
            """
            if i.imagem:
                html += f"<a href='/{i.imagem}' target='_blank'>Ver Imagem</a>"
            html += "</div>"

    html += """
    <h2>Movimentar Item</h2>
    <form method="post" enctype="multipart/form-data">
    Nome:<input name="nome"><br>
    Gerenciadora:
    <select name="gerenciadora">
    <option>PRIME</option>
    <option>LINK</option>
    <option>NEO</option>
    <option>FITMOB</option>
    <option>OUTROS</option>
    </select><br>
    Quantidade:<input name="qtd"><br>
    Tipo:
    <select name="tipo">
    <option value="entrada">Entrada</option>
    <option value="saida">Saída</option>
    </select><br>
    Imagem:<input type="file" name="imagem"><br><br>
    <button>Salvar</button>
    </form>
    <br><a href="/excel">Exportar Excel</a>
    """

    if session.get("role") == "admin":
        html += "<br><a href='/criar_usuario'>Criar Usuário</a>"
        html += "<br><a href='/backup'>Baixar Backup</a>"

    html += "</body>"
    return html

# ===============================
# EXCEL COMPLETO
# ===============================

@app.route("/excel")
def excel():

    writer = pd.ExcelWriter("estoque.xlsx", engine="openpyxl")

    gerenciadoras = ["PRIME", "LINK", "NEO", "FITMOB", "OUTROS"]

    for g in gerenciadoras:
        itens = Item.query.filter_by(gerenciadora=g).all()
        data = []

        for i in itens:
            movs = Movimentacao.query.filter_by(item=i.nome).all()

            entradas = sum(m.quantidade for m in movs if m.tipo == "entrada")
            saidas = sum(m.quantidade for m in movs if m.tipo == "saida")

            ultimos_6 = datetime.utcnow() - timedelta(days=180)
            saidas_6 = sum(m.quantidade for m in movs if m.tipo == "saida" and m.data >= ultimos_6)

            media = saidas_6 / 6 if saidas_6 else 0
            previsao = media * 6 * 1.2

            data.append({
                "Item": i.nome,
                "Estoque Atual": i.quantidade,
                "Entradas Total": entradas,
                "Saídas Total": saidas,
                "Saídas Últimos 6M": saidas_6,
                "Estimativa Próx 6M +20%": round(previsao)
            })

        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name=g, index=False)

    writer.close()
    return send_file("estoque.xlsx", as_attachment=True)

# ===============================
# BACKUP
# ===============================

@app.route("/backup")
def backup():
    return send_file("backup.xlsx", as_attachment=True)

# ===============================
# RUN
# ===============================

if __name__ == "__main__":
    app.run(debug=True)
