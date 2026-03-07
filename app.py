```python
from flask import Flask, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json

app = Flask(__name__)
app.secret_key = "segredo"

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
# INIT
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
# SISTEMA
# =========================
@app.route("/sistema")
def sistema():

    if "user" not in session:
        return redirect("/")

    msg_html = ""
    if "msg" in session:
        msg_html = f"""
        <div style="background:#d4edda;color:#155724;padding:15px;
        margin:20px;border-radius:8px;text-align:center;font-weight:bold;">
        {session["msg"]}
        </div>
        """
        session.pop("msg")

    dados = calcular()

    grupos = {}
    for d in dados:
        grupos.setdefault(d["ger"], []).append(d)

    itens = {}
    for d in Movimentacao.query.all():
        itens.setdefault(d.gerenciadora, set()).add(d.item)

    itens = {k:list(v) for k,v in itens.items()}

    if session["tipo"] == "admin":
        campo_item = "<input name='item' required placeholder='Novo item'>"
    else:
        campo_item = """
        <input type='text' id='buscarItem' placeholder='🔎 Buscar item...' onkeyup='filtrarItens()'>
        <select name='item' id='itemSelect'></select>
        """

    botao_usuarios = ""
    if session["tipo"] == "admin":
        botao_usuarios = """
        <div style="margin-top:10px">
        <a href="/usuarios"><button>👥 Usuários</button></a>
        </div>
        """

    html = f"""
    <html>
    <style>
    body{{margin:0;font-family:Arial;background:#eef2f7}}
    .topbar{{background:linear-gradient(90deg,#1e3c72,#2a5298);
    color:white;padding:20px;text-align:center;font-size:22px}}
    .card{{background:white;margin:20px;padding:20px;border-radius:12px;
    box-shadow:0 4px 10px rgba(0,0,0,0.1)}}
    table{{width:100%;border-collapse:collapse}}
    th{{background:#2a5298;color:white}}
    td,th{{padding:10px;text-align:center;border-bottom:1px solid #ddd}}
    button{{padding:10px;background:#2a5298;color:white;border:none;border-radius:8px;cursor:pointer}}
    input,select{{padding:10px;margin:5px;width:100%;border-radius:6px;border:1px solid #ccc}}
    .ok{{color:green;font-weight:bold}}
    .comprar{{color:red;font-weight:bold}}
    </style>

    <div class="topbar">
    📦 CONTROLE DE ESTOQUE | {session["user"]}
    {botao_usuarios}
    </div>

    {msg_html}

    <div class="card">
    <form method="POST" action="/inserir" onsubmit="return confirmarMov()">

    <select name="ger" id="gerSelect">
    {"".join([f"<option>{g}</option>" for g in GERENCIADORAS])}
    </select>

    <select name="tipo">
    <option value="ENTRADA">ENTRADA</option>
    <option value="SAIDA">SAIDA</option>
    </select>

    {campo_item}

    <input name="qtd" type="number" required placeholder="Quantidade">

    <button>Salvar Movimentação</button>

    </form>
    </div>
    """

    for g in GERENCIADORAS:

        lista = grupos.get(g, [])

        html += f"""
        <div class="card">
        <h3>{g}</h3>
        <table>
        <tr>
        <th>Item</th>
        <th>Entrada</th>
        <th>Saída</th>
        <th>Estoque</th>
        <th>Status</th>
        <th>Ação</th>
        </tr>
        """

        for d in lista:

            cls = "ok" if d["status"]=="OK" else "comprar"

            remover = ""

            if session["tipo"] == "admin":
                remover = f"""
                <form method='POST' action='/remover_item' onsubmit="return confirm('Remover item {d['item']}?')">
                <input type='hidden' name='ger' value='{d["ger"]}'>
                <input type='hidden' name='item' value='{d["item"]}'>
                <button style='background:#dc3545'>Remover</button>
                </form>
                """

            html += f"""
            <tr>
            <td>{d['item']}</td>
            <td>{d['entrada']}</td>
            <td>{d['saida']}</td>
            <td>{d['saldo']}</td>
            <td class="{cls}">{d['status']}</td>
            <td>{remover}</td>
            </tr>
            """

        html += "</table></div>"

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

function confirmarMov(){{
let tipo=document.querySelector("select[name='tipo']").value;
let item=document.querySelector("[name='item']").value;
let qtd=document.querySelector("[name='qtd']").value;
let ger=document.querySelector("[name='ger']").value;

return confirm(
"Confirmar movimentação?\\n\\n"+
"Tipo: "+tipo+"\\n"+
"Gerenciadora: "+ger+"\\n"+
"Item: "+item+"\\n"+
"Quantidade: "+qtd
);
}}

</script>
</html>
"""

    return html


# =========================
# REMOVER ITEM
# =========================
@app.route("/remover_item", methods=["POST"])
def remover_item():

    if session.get("tipo") != "admin":
        return redirect("/sistema")

    Movimentacao.query.filter_by(
        gerenciadora=request.form["ger"],
        item=request.form["item"]
    ).delete()

    db.session.commit()

    return redirect("/sistema")


# =========================
# GERENCIAR USUÁRIOS
# =========================
@app.route("/usuarios")
def usuarios():

    if session.get("tipo") != "admin":
        return redirect("/sistema")

    usuarios = Usuario.query.all()

    html="<h2>Usuários</h2>"

    for u in usuarios:
        html+=f"{u.usuario} - {u.tipo}<br>"

    return html


# =========================
# INSERIR MOVIMENTAÇÃO
# =========================
@app.route("/inserir", methods=["POST"])
def inserir():

    try:

        db.session.add(Movimentacao(
            gerenciadora=request.form["ger"],
            tipo=request.form["tipo"],
            item=request.form["item"].upper(),
            quantidade=int(request.form["qtd"])
        ))

        db.session.commit()

        session["msg"] = "✅ Movimentação registrada com sucesso"

    except:

        session["msg"] = "❌ Erro ao registrar movimentação"

    return redirect("/sistema")


# =========================
# CALCULAR ESTOQUE
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

        estoque_atual = v["entrada"] - v["saida"]

        media = v["saida"]

        proj = int(media * 6 * 1.2)

        status = "OK" if estoque_atual >= proj else "COMPRAR"

        final.append({
            "ger":g,
            "item":i,
            "entrada":v["entrada"],
            "saida":v["saida"],
            "saldo":estoque_atual,
            "media":media,
            "proj":proj,
            "status":status
        })

    return final


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
```
