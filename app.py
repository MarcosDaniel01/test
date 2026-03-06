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
    .gerenciadora{{margin-top:30px;border-radius:12px;overflow:hidden}}
    .titulo{{padding:12px;color:white;font-weight:bold}}

    .PRIME{{background:#fd7e14}}
    .NEO{{background:#28a745}}
    .LINK{{background:#004085}}
    .FITMOBY{{background:#6f42c1}}
    .OUTROS{{background:#dc3545}}

    </style>

    <div class="topbar">📦 CONTROLE DE ESTOQUE | {session["user"]}</div>

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
        <div class="card gerenciadora">
        <div class="titulo {g}">🏢 {g}</div>
        <table>
        <tr>
        <th>Item</th>
        <th>Entrada</th>
        <th>Saída</th>
        <th>Estoque Atual</th>
        <th>Média Mensal</th>
        <th>Previsão (6 Meses + 20%)</th>
        <th>Status</th>
        </tr>
        """

        for d in lista:
            cls = "ok" if d["status"]=="OK" else "comprar"

            html += f"""
            <tr>
            <td>{d['item']}</td>
            <td>{d['entrada']}</td>
            <td>{d['saida']}</td>
            <td style="font-weight:bold">{d['saldo']}</td>
            <td>{d['media']}</td>
            <td>{d['proj']}</td>
            <td class="{cls}">{d['status']}</td>
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

let msg="";

if(tipo=="ENTRADA"){{
msg="Confirmar ENTRADA no estoque?";
}}else{{
msg="Confirmar SAIDA do estoque?";
}}

return confirm(
msg+"\\n\\n"+
"Gerenciadora: "+ger+"\\n"+
"Item: "+item+"\\n"+
"Quantidade: "+qtd
);
}}

function filtrarItens(){{
let filtro=document.getElementById("buscarItem").value.toLowerCase();
let select=document.getElementById("itemSelect");
let options=select.options;

for(let i=0;i<options.length;i++){{

let txt=options[i].text.toLowerCase();

if(txt.includes(filtro)){{
options[i].style.display="";
}}else{{
options[i].style.display="none";
}}

}}
}}

</script>
</html>
"""

    return html
