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

with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(usuario="admin").first():
        db.session.add(Usuario(usuario="admin", senha="123", tipo="admin"))
        db.session.commit()


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


@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    dados = calcular()

    grupos = {{}}
    for d in dados:
        grupos.setdefault(d["ger"], []).append(d)

    itens = {{}}
    for d in Movimentacao.query.all():
        itens.setdefault(d.gerenciadora, set()).add(d.item)

    itens = {{k:list(v) for k,v in itens.items()}}

    if session["tipo"] == "admin":
        campo_item = "<input name='item' required placeholder='Novo item'>"
    else:
        campo_item = "<select name='item' id='itemSelect'></select>"

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

button{{padding:10px;background:#2a5298;color:white;border:none;border-radius:8px}}

input,select{{padding:10px;margin:5px;width:100%;border-radius:6px;border:1px solid #ccc}}

.ok{{color:green;font-weight:bold}}
.comprar{{color:red;font-weight:bold}}

.gerenciadora{{margin-top:30px;border-radius:12px;overflow:hidden}}

.titulo{{padding:12px;color:white;font-weight:bold}}

.PRIME{{background:#28a745}}
.NEO{{background:#fd7e14}}
.LINK{{background:#004085}}
.FITMOBY{{background:#6f42c1}}
.OUTROS{{background:#dc3545}}
</style>

<div class="topbar">📦 CONTROLE DE ESTOQUE | {session["user"]}</div>

<div style="padding:20px">
<input type="text" id="filtro" placeholder="🔎 Buscar item..."
style="width:100%;padding:12px;border-radius:8px;border:1px solid #ccc">
</div>

<div class="card">

<form method="POST" action="/inserir" onsubmit="return confirmarMov()">

<select name="ger" id="gerSelect">
{"".join([f"<option>{{g}}</option>" for g in GERENCIADORAS])}
</select>

<select name="tipo">
<option value="ENTRADA">ENTRADA</option>
<option value="SAIDA">SAÍDA</option>
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
<th>Média</th>
<th>Projeção</th>
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
<td>{d['saldo']}</td>
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

let o=document.createElement("option");
o.text=i;
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
"Gerenciadora: "+ger+"\\n"+
"Tipo: "+tipo+"\\n"+
"Item: "+item+"\\n"+
"Quantidade: "+qtd
);

}}

document.getElementById("filtro").addEventListener("keyup",function(){{

let texto=this.value.toLowerCase();

let linhas=document.querySelectorAll("table tr");

linhas.forEach((linha,i)=>{{

if(i==0)return;

let item=linha.children[0].innerText.toLowerCase();

if(item.includes(texto)){{

linha.style.display="";

}}else{{

linha.style.display="none";

}}

}});

}});

</script>

</html>
"""

    return html


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


def calcular():

    dados = Movimentacao.query.all()

    res = {{}}

    for d in dados:

        chave = (d.gerenciadora, d.item)

        if chave not in res:
            res[chave] = {{"entrada":0,"saida":0}}

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

        final.append({{
            "ger":g,
            "item":i,
            "entrada":v["entrada"],
            "saida":v["saida"],
            "saldo":estoque_atual,
            "media":media,
            "proj":proj,
            "status":status
        }})

    return final


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
