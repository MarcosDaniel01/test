from flask import Flask, request, jsonify, render_template_string, redirect
import psycopg2
import os
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# ===============================
# CONEXÃO
# ===============================
def conectar():
    return psycopg2.connect(DATABASE_URL)

# ===============================
# CRIAR TABELAS
# ===============================
def criar_tabelas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        usuario TEXT UNIQUE,
        senha TEXT,
        tipo TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS estoque (
        id SERIAL PRIMARY KEY,
        produto TEXT,
        quantidade INTEGER,
        gerenciadora TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimentacoes (
        id SERIAL PRIMARY KEY,
        produto TEXT,
        tipo TEXT,
        quantidade INTEGER,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# HOME (TELA)
# ===============================
@app.route("/")
def home():
    return render_template_string("""
    <html>
    <head>
        <title>Sistema de Estoque</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: Arial; background:#0f172a; color:white; text-align:center;}
            .card { background:#1e293b; padding:20px; margin:20px; border-radius:10px;}
            input, select, button { padding:10px; margin:5px; border-radius:5px;}
            button { background:#22c55e; color:white; border:none;}
        </style>
    </head>
    <body>

    <h1>🚀 Sistema de Estoque</h1>

    <div class="card">
        <h2>Adicionar Produto</h2>
        <input id="produto" placeholder="PRODUTO (MAIÚSCULO)">
        <input id="quantidade" type="number" placeholder="Quantidade">
        <select id="gerenciadora">
            <option>PRIME</option>
            <option>LINK</option>
            <option>NEO</option>
            <option>FITMOBY</option>
            <option>OUTROS</option>
        </select>
        <button onclick="add()">Adicionar</button>
    </div>

    <div class="card">
        <h2>Saída</h2>
        <input id="produto_saida" placeholder="PRODUTO">
        <input id="qtd_saida" type="number" placeholder="Quantidade">
        <button onclick="saida()">Registrar</button>
    </div>

    <div class="card">
        <h2>Estoque</h2>
        <button onclick="carregar()">Atualizar</button>
        <pre id="estoque"></pre>
    </div>

    <div class="card">
        <h2>Dashboard</h2>
        <canvas id="grafico"></canvas>
    </div>

    <script>
    async function add(){
        await fetch('/adicionar',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
                produto:document.getElementById('produto').value,
                quantidade:document.getElementById('quantidade').value,
                gerenciadora:document.getElementById('gerenciadora').value
            })
        })
        alert("Adicionado")
    }

    async function saida(){
        await fetch('/saida',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
                produto:document.getElementById('produto_saida').value,
                quantidade:document.getElementById('qtd_saida').value
            })
        })
        alert("Saída registrada")
    }

    async function carregar(){
        let res = await fetch('/estoque')
        let data = await res.json()
        document.getElementById('estoque').innerText = JSON.stringify(data,null,2)
    }

    async function dashboard(){
        let res = await fetch('/dashboard')
        let data = await res.json()

        new Chart(document.getElementById('grafico'),{
            type:'bar',
            data:{
                labels:data.map(x=>x[0]),
                datasets:[{
                    label:'Quantidade',
                    data:data.map(x=>x[1])
                }]
            }
        })
    }

    dashboard()
    </script>

    </body>
    </html>
    """)

# ===============================
# ADICIONAR
# ===============================
@app.route("/adicionar", methods=["POST"])
def adicionar():
    data = request.json

    produto = data["produto"].upper()
    quantidade = int(data["quantidade"])
    gerenciadora = data["gerenciadora"].upper()

    if gerenciadora not in GERENCIADORAS:
        return jsonify({"erro": "Gerenciadora inválida"}), 400

    conn = conectar()
    cur = conn.cursor()

    cur.execute("INSERT INTO estoque (produto, quantidade, gerenciadora) VALUES (%s,%s,%s)",
                (produto, quantidade, gerenciadora))

    cur.execute("INSERT INTO movimentacoes (produto,tipo,quantidade) VALUES (%s,'ENTRADA',%s)",
                (produto, quantidade))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"msg":"ok"})

# ===============================
# SAIDA
# ===============================
@app.route("/saida", methods=["POST"])
def saida():
    data = request.json

    produto = data["produto"].upper()
    quantidade = int(data["quantidade"])

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE estoque SET quantidade = quantidade - %s WHERE produto=%s",
                (quantidade, produto))

    cur.execute("INSERT INTO movimentacoes (produto,tipo,quantidade) VALUES (%s,'SAIDA',%s)",
                (produto, quantidade))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"msg":"ok"})

# ===============================
# ESTOQUE
# ===============================
@app.route("/estoque")
def estoque():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT * FROM estoque")
    dados = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(dados)

# ===============================
# DASHBOARD
# ===============================
@app.route("/dashboard")
def dash():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT gerenciadora, SUM(quantidade) FROM estoque GROUP BY gerenciadora")
    dados = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(dados)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar_tabelas()
    app.run(host="0.0.0.0", port=10000)
