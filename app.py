from flask import Flask, request, jsonify, render_template_string
import psycopg2
import os
from datetime import datetime, timedelta

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
        <title>Estoque Inteligente</title>
        <style>
            body { font-family: Arial; background:#0f172a; color:white; text-align:center;}
            table { width:80%; margin:auto; border-collapse:collapse;}
            th, td { padding:10px; border:1px solid #334155;}
            th { background:#1e293b;}
            tr:nth-child(even){background:#1e293b;}
            input, select, button { padding:10px; margin:5px; border-radius:5px;}
            button { background:#22c55e; color:white; border:none;}
            .card { background:#1e293b; padding:20px; margin:20px; border-radius:10px;}
        </style>
    </head>
    <body>

    <h1>📦 Sistema de Estoque Inteligente</h1>

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
        <h2>📊 Estoque</h2>
        <button onclick="carregar()">Atualizar</button>
        <table id="tabela">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Produto</th>
                    <th>Quantidade</th>
                    <th>Gerenciadora</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    </div>

    <div class="card">
        <h2>🧠 Previsão (6 meses)</h2>
        <button onclick="previsao()">Calcular</button>
        <pre id="previsao"></pre>
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
        carregar()
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
        carregar()
    }

    async function carregar(){
        let res = await fetch('/estoque')
        let data = await res.json()

        let tbody = document.querySelector("#tabela tbody")
        tbody.innerHTML = ""

        data.forEach(item=>{
            tbody.innerHTML += `
            <tr>
                <td>${item[0]}</td>
                <td>${item[1]}</td>
                <td>${item[2]}</td>
                <td>${item[3]}</td>
            </tr>`
        })
    }

    async function previsao(){
        let res = await fetch('/previsao')
        let data = await res.json()
        document.getElementById('previsao').innerText = JSON.stringify(data,null,2)
    }

    carregar()
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
# SAÍDA
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

    cur.execute("SELECT * FROM estoque ORDER BY id DESC")
    dados = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(dados)

# ===============================
# PREVISÃO IA (6 MESES)
# ===============================
@app.route("/previsao")
def previsao():
    conn = conectar()
    cur = conn.cursor()

    seis_meses = datetime.now() - timedelta(days=180)

    cur.execute("""
        SELECT produto, SUM(quantidade)
        FROM movimentacoes
        WHERE tipo='SAIDA' AND data >= %s
        GROUP BY produto
    """, (seis_meses,))

    dados = cur.fetchall()

    resultado = []
    for produto, total in dados:
        media_mensal = total / 6
        previsao = media_mensal * 6

        resultado.append({
            "produto": produto,
            "media_mensal": round(media_mensal, 2),
            "previsao_6_meses": round(previsao, 2)
        })

    cur.close()
    conn.close()

    return jsonify(resultado)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    try:
        criar_tabelas()
        print("✅ Banco conectado")
    except Exception as e:
        print("❌ Erro banco:", e)

    app.run(host="0.0.0.0", port=10000)
