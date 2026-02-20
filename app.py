from flask import Flask, request, jsonify, render_template_string, redirect, send_file
import psycopg2
import os
import pandas as pd
from datetime import datetime
import io

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# CONEXÃO
# ===============================
def conectar():
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except:
        return None

# ===============================
# CRIAR TABELA
# ===============================
def criar():
    conn = conectar()
    if not conn: return
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS estoque (
        id SERIAL PRIMARY KEY,
        produto TEXT UNIQUE,
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
        gerenciadora TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

# ===============================
# HOME
# ===============================
@app.route("/")
def home():
    return render_template_string("""
    <h1>🚀 ESTOQUE EMPRESARIAL</h1>

    <form method="post" action="/mov">
        Produto: <input name="produto"><br>
        Quantidade: <input type="number" name="quantidade"><br>

        Tipo:
        <select name="tipo">
            <option>ENTRADA</option>
            <option>SAIDA</option>
        </select><br>

        Gerenciadora:
        <select name="gerenciadora">
            <option>PRIME</option>
            <option>LINK</option>
            <option>NEO</option>
            <option>FITMOBY</option>
            <option>OUTROS</option>
        </select><br><br>

        <button>Salvar</button>
    </form>

    <br>
    <a href="/estoque">📊 Ver Estoque</a><br>
    <a href="/excel">📥 Exportar Excel Geral</a><br>
    <a href="/excel/PRIME">📥 Excel PRIME</a><br>
    <a href="/excel/LINK">📥 Excel LINK</a><br>
    <a href="/excel/NEO">📥 Excel NEO</a><br>
    <a href="/excel/FITMOBY">📥 Excel FITMOBY</a><br>
    <a href="/excel/OUTROS">📥 Excel OUTROS</a>
    """)

# ===============================
# MOVIMENTAÇÃO
# ===============================
@app.route("/mov", methods=["POST"])
def mov():
    produto = request.form["produto"].upper()
    qtd = int(request.form["quantidade"])
    tipo = request.form["tipo"]
    ger = request.form["gerenciadora"].upper()

    if ger not in GERENCIADORAS:
        return "Gerenciadora inválida"

    # BLOQUEIO DE NOME
    if ger != "OUTROS":
        for g in GERENCIADORAS:
            if g in produto:
                return "Erro: nome contém gerenciadora"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT quantidade FROM estoque WHERE produto=%s", (produto,))
    existe = cur.fetchone()

    if existe:
        if tipo == "ENTRADA":
            cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE produto=%s", (qtd, produto))
        else:
            cur.execute("UPDATE estoque SET quantidade = quantidade - %s WHERE produto=%s", (qtd, produto))
    else:
        if tipo == "SAIDA":
            return "Erro: não existe no estoque"
        cur.execute("INSERT INTO estoque VALUES (DEFAULT,%s,%s,%s)", (produto, qtd, ger))

    cur.execute("INSERT INTO movimentacoes (produto,tipo,quantidade,gerenciadora) VALUES (%s,%s,%s,%s)",
                (produto, tipo, qtd, ger))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")

# ===============================
# ESTOQUE (TIPO PLANILHA)
# ===============================
@app.route("/estoque")
def estoque():
    conn = conectar()

    df = pd.read_sql("""
    SELECT produto, gerenciadora,
    SUM(CASE WHEN tipo='ENTRADA' THEN quantidade ELSE 0 END) entrada,
    SUM(CASE WHEN tipo='SAIDA' THEN quantidade ELSE 0 END) saida
    FROM movimentacoes
    GROUP BY produto, gerenciadora
    ORDER BY gerenciadora, produto
    """, conn)

    if df.empty:
        return "Sem dados"

    df["saldo"] = df["entrada"] - df["saida"]

    # IA previsão 6 meses
    df["media_saida"] = df["saida"] / 6
    df["previsao_6m"] = df["media_saida"] * 6

    html = "<h2>📊 ESTOQUE POR GERENCIADORA</h2>"

    for g in GERENCIADORAS:
        sub = df[df["gerenciadora"] == g]
        if not sub.empty:
            html += f"<h3>{g}</h3>"
            html += sub.to_html(index=False)

    conn.close()
    return html

# ===============================
# EXPORTAR EXCEL
# ===============================
@app.route("/excel")
def excel():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM estoque", conn)

    output = io.BytesIO()
    df.to_excel(output, index=False)

    output.seek(0)
    return send_file(output, download_name="estoque.xlsx", as_attachment=True)

# ===============================
# EXCEL POR GERENCIADORA
# ===============================
@app.route("/excel/<ger>")
def excel_ger(ger):
    ger = ger.upper()

    conn = conectar()

    df = pd.read_sql("""
    SELECT produto,
    SUM(CASE WHEN tipo='ENTRADA' THEN quantidade ELSE 0 END) entrada,
    SUM(CASE WHEN tipo='SAIDA' THEN quantidade ELSE 0 END) saida
    FROM movimentacoes
    WHERE gerenciadora=%s
    GROUP BY produto
    """, conn, params=(ger,))

    df["saldo"] = df["entrada"] - df["saida"]

    output = io.BytesIO()
    df.to_excel(output, index=False)

    output.seek(0)
    return send_file(output, download_name=f"{ger}.xlsx", as_attachment=True)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar()
    app.run(host="0.0.0.0", port=10000)
