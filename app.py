from flask import Flask, request, jsonify
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

# ===============================
# CONFIG
# ===============================
GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

def validar_maiusculo(texto):
    return texto.isupper()

# ===============================
# LOGIN
# ===============================
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    usuario = data["usuario"]
    senha = data["senha"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT tipo FROM usuarios WHERE usuario=%s AND senha=%s", (usuario, senha))
    res = cur.fetchone()

    cur.close()
    conn.close()

    if res:
        return jsonify({"status": "ok", "tipo": res[0]})
    else:
        return jsonify({"erro": "Login inválido"}), 401

# ===============================
# CRIAR USUÁRIO
# ===============================
@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    data = request.json

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO usuarios (usuario, senha, tipo)
        VALUES (%s, %s, %s)
    """, (data["usuario"], data["senha"], data["tipo"]))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"msg": "Usuário criado"})

# ===============================
# ADICIONAR PRODUTO
# ===============================
@app.route("/adicionar", methods=["POST"])
def adicionar():
    data = request.json

    produto = data["produto"].upper()
    quantidade = int(data["quantidade"])
    gerenciadora = data["gerenciadora"].upper()

    if not validar_maiusculo(produto):
        return jsonify({"erro": "Use letras maiúsculas"}), 400

    if gerenciadora not in GERENCIADORAS:
        return jsonify({"erro": "Gerenciadora inválida"}), 400

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO estoque (produto, quantidade, gerenciadora)
        VALUES (%s, %s, %s)
    """, (produto, quantidade, gerenciadora))

    cur.execute("""
        INSERT INTO movimentacoes (produto, tipo, quantidade)
        VALUES (%s, 'ENTRADA', %s)
    """, (produto, quantidade))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"msg": "Adicionado"})

# ===============================
# SAÍDA DE PRODUTO
# ===============================
@app.route("/saida", methods=["POST"])
def saida():
    data = request.json

    produto = data["produto"].upper()
    quantidade = int(data["quantidade"])

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE estoque SET quantidade = quantidade - %s
        WHERE produto = %s
    """, (quantidade, produto))

    cur.execute("""
        INSERT INTO movimentacoes (produto, tipo, quantidade)
        VALUES (%s, 'SAIDA', %s)
    """, (produto, quantidade))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"msg": "Saída registrada"})

# ===============================
# LISTAR ESTOQUE
# ===============================
@app.route("/estoque", methods=["GET"])
def estoque():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT * FROM estoque")
    dados = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(dados)

# ===============================
# ALERTA ESTOQUE BAIXO
# ===============================
@app.route("/alerta", methods=["GET"])
def alerta():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT produto, quantidade FROM estoque WHERE quantidade < 5")
    dados = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(dados)

# ===============================
# DASHBOARD
# ===============================
@app.route("/dashboard", methods=["GET"])
def dashboard():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT gerenciadora, SUM(quantidade) FROM estoque GROUP BY gerenciadora")
    dados = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(dados)

# ===============================
# RELATÓRIO EXCEL
# ===============================
@app.route("/relatorio", methods=["GET"])
def relatorio():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM movimentacoes", conn)

    caminho = "relatorio.xlsx"
    df.to_excel(caminho, index=False)

    conn.close()

    return jsonify({"msg": "Relatório gerado", "arquivo": caminho})

# ===============================
# PREVISÃO SIMPLES (IA)
# ===============================
@app.route("/previsao", methods=["GET"])
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

    previsoes = []
    for produto, total in dados:
        media_mensal = total / 6
        previsoes.append({
            "produto": produto,
            "media_mensal": round(media_mensal, 2)
        })

    cur.close()
    conn.close()

    return jsonify(previsoes)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar_tabelas()
    app.run(host="0.0.0.0", port=10000)
