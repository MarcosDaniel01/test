from flask import Flask, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json

app = Flask(name)
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

GERENCIADORAS = ["PRIME","LINK","NEO","FITMOBY","OUTROS"]

with app.app_context():
db.create_all()
if not Usuario.query.filter_by(usuario="admin").first():
db.session.add(Usuario(usuario="admin",senha="123",tipo="admin"))
db.session.commit()

@app.route("/",methods=["GET","POST"])
def login():

if request.method=="POST":  

    user=Usuario.query.filter_by(  
        usuario=request.form["usuario"],  
        senha=request.form["senha"]  
    ).first()  

    if user:  
        session["user"]=user.usuario  
        session["tipo"]=user.tipo  
        return redirect("/sistema")  

return """  
<html>  
<style>  
body{font-family:Arial;background:linear-gradient(120deg,#2980b9,#6dd5fa);display:flex;justify-content:center;align-items:center;height:100vh;}  
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

msg=""  
if "msg" in session:  
    msg=session["msg"]  
    session.pop("msg")  

dados=calcular()  

grupos={}  
for d in dados:  
    grupos.setdefault(d["ger"],[]).append(d)  

html=f"""  
<html>  
<body style="font-family:Arial;background:#eef2f7">  

<h2>CONTROLE DE ESTOQUE | {session["user"]}</h2>  
{msg}  

<form method="POST" action="/inserir" onsubmit="return confirmarMov()">  

<select name="ger">  
{"".join([f"<option>{g}</option>" for g in GERENCIADORAS])}  
</select>  

<select name="tipo">  
<option value="ENTRADA">ENTRADA</option>  
<option value="SAIDA">SAIDA</option>  
</select>  

<input name="item" placeholder="Item">  
<input name="qtd" type="number" placeholder="Quantidade">  

<button>Salvar</button>  

</form>  
"""  

for g in GERENCIADORAS:  

    lista=grupos.get(g,[])  

    html+=f"<h3>{g}</h3><table border=1>"  

    for d in lista:  

        remover=""  

        if session["tipo"]=="admin":  

            remover=f"""  
            <form method='POST' action='/remover_item'>  
            <input type='hidden' name='ger' value='{d["ger"]}'>  
            <input type='hidden' name='item' value='{d["item"]}'>  
            <button>Remover</button>  
            </form>  
            """  

        html+=f"""  
        <tr>  
        <td>{d['item']}</td>  
        <td>{d['entrada']}</td>  
        <td>{d['saida']}</td>  
        <td>{d['saldo']}</td>  
        <td>{remover}</td>  
        </tr>  
        """  

    html+="</table>"  

html+="""
<script> function confirmarMov(){ let tipo=document.querySelector("select[name='tipo']").value let item=document.querySelector("[name='item']").value let qtd=document.querySelector("[name='qtd']").value let ger=document.querySelector("[name='ger']").value return confirm( "Confirmar movimentação?\n\n"+ "Tipo: "+tipo+"\n"+ "Gerenciadora: "+ger+"\n"+ "Item: "+item+"\n"+ "Quantidade: "+qtd ) } </script> </body> </html> """
return html

@app.route("/remover_item",methods=["POST"])
def remover_item():

if session.get("tipo")!="admin":
    return redirect("/sistema")

Movimentacao.query.filter_by(
    gerenciadora=request.form["ger"],
    item=request.form["item"]
).delete()

db.session.commit()

return redirect("/sistema")

@app.route("/usuarios")
def usuarios():

if session.get("tipo")!="admin":
    return redirect("/sistema")

usuarios=Usuario.query.all()

html="<h2>Usuarios</h2>"

for u in usuarios:
    html+=f"{u.usuario} - {u.tipo}<br>"

return html

@app.route("/inserir",methods=["POST"])
def inserir():

try:

    db.session.add(Movimentacao(
        gerenciadora=request.form["ger"],
        tipo=request.form["tipo"],
        item=request.form["item"].upper(),
        quantidade=int(request.form["qtd"])
    ))

    db.session.commit()

    session["msg"]="Movimentacao registrada com sucesso"

except:

    session["msg"]="Erro ao registrar movimentacao"

return redirect("/sistema")

def calcular():

dados=Movimentacao.query.all()

res={}

for d in dados:

    chave=(d.gerenciadora,d.item)

    if chave not in res:
        res[chave]={"entrada":0,"saida":0}

    if d.tipo=="ENTRADA":
        res[chave]["entrada"]+=d.quantidade
    else:
        res[chave]["saida"]+=d.quantidade

final=[]

for (g,i),v in res.items():

    saldo=v["entrada"]-v["saida"]

    final.append({
        "ger":g,
        "item":i,
        "entrada":v["entrada"],
        "saida":v["saida"],
        "saldo":saldo
    })

return final

if name=="main":
app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
