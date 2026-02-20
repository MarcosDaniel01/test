from flask import Flask, render_template_string, request, redirect, session, send_file
import psycopg2
import os
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo123"

DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# CONEXÃO
# =========================
def conectar():
    return psycopg2.connect(DATABASE_URL)

# =========================
# CRIAR TABELAS
# =========================
def criar_tabelas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        senha TEXT,
        tipo TEXT
    )
    """)

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
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

    try:
        cur.execute("INSERT INTO usuarios (username, senha, tipo) VALUES ('ADMIN','123','admin')")
        conn.commit()
    except:
        pass

    conn.close()

criar_tabelas()

# =========================
# VALIDAÇÃO
# =========================
def validar_maiusculo(texto):
    return texto == texto.upper()

# =========================
# IA PREVISÃO AVANÇADA
# =========================
def previsao_inteligente(df_mov):
    if df_mov.empty:
        return "Sem dados ainda"

    saidas = df_mov[df_mov["tipo"] == "saida"]

    if saidas.empty:
        return "Sem saídas registradas"

    saidas["mes"] = pd.to_datetime(saidas["data"]).dt.to_period("M")

    consumo_mensal = saidas.groupby(["produto","mes"])["quantidade"].sum().reset_index()

    previsao_texto = ""

    for produto in consumo_mensal["produto"].unique():
        dados = consumo_mensal[consumo_mensal["produto"] == produto]

        media = dados["quantidade"].mean()

        # tendência simples
        if len(dados) > 1:
            tendencia = dados["quantidade"].iloc[-1] - dados["quantidade"].iloc[0]
        else:
            tendencia = 0

        previsao_6m = int((media + (tendencia/len(dados))) * 6)

        previsao_texto += f"<b>{produto}</b>: {previsao_6m} unidades<br>"

    return previsao_texto

# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form["user"].upper()
        senha = request.form["senha"]

        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND senha=%s", (user, senha))
        usuario = cur.fetchone()
        conn.close()

        if usuario:
            session["user"] = user
            session["tipo"] = usuario[3]
            return redirect("/estoque")

    return """
    <h2>🔐 Login</h2>
    <form method="post">
        Usuário: <input name="user"><br>
        Senha: <input type="password" name="senha"><br>
        <button>Entrar</button>
    </form>
    """

# =========================
# ESTOQUE
# =========================
@app.route("/estoque", methods=["GET","POST"])
def estoque():
    if "user" not in session:
        return redirect("/")

    mensagem = ""

    if request.method == "POST":
        produto = request.form["produto"].upper()
        quantidade = int(request.form["quantidade"])
        tipo = request.form["tipo"]
        gerenciadora = request.form["gerenciadora"].upper()

        if not validar_maiusculo(produto):
            mensagem = "❌ Apenas MAIÚSCULAS!"
        else:
            conn = conectar()
            cur = conn.cursor()

            cur.execute("SELECT quantidade FROM estoque WHERE produto=%s", (produto,))
            resultado = cur.fetchone()

            if tipo == "entrada":
                if resultado:
                    cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE produto=%s",
                                (quantidade, produto))
                else:
                    cur.execute("INSERT INTO estoque VALUES (DEFAULT,%s,%s,%s)",
                                (produto, quantidade, gerenciadora))

            elif tipo == "saida":
                if resultado and resultado[0] >= quantidade:
                    cur.execute("UPDATE estoque SET quantidade = quantidade - %s WHERE produto=%s",
                                (quantidade, produto))
                else:
                    mensagem = "❌ Estoque insuficiente!"

            cur.execute("INSERT INTO movimentacoes (produto,tipo,quantidade) VALUES (%s,%s,%s)",
                        (produto, tipo, quantidade))

            conn.commit()
            conn.close()

    conn = conectar()
    df = pd.read_sql("SELECT * FROM estoque ORDER BY gerenciadora, produto", conn)
    mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
    conn.close()

    alerta = df[df["quantidade"] < 5]

    previsao = previsao_inteligente(mov)

    tabela = ""
    for _, row in df.iterrows():
        cor = "red" if row["quantidade"] < 5 else "green"
        tabela += f"""
        <tr>
            <td>{row['produto']}</td>
            <td>{row['quantidade']}</td>
            <td>{row['gerenciadora']}</td>
            <td style='color:{cor}'>●</td>
        </tr>
        """

    return f"""
    <style>
    body {{ font-family: Arial; background:#f4f6f9; }}
    .card {{ background:white; padding:20px; border-radius:10px; margin:10px; box-shadow:0 0 10px #ccc; }}
    table {{ width:100%; border-collapse: collapse; }}
    td,th {{ padding:10px; border-bottom:1px solid #ddd; }}
    button {{ padding:10px; background:#007bff; color:white; border:none; }}
    </style>

    <h2>📦 Sistema de Estoque</h2>

    <div class="card">
    <form method="post">
        Produto: <input name="produto" required>
        Quantidade: <input type="number" name="quantidade" required>

        <select name="tipo">
            <option value="entrada">Entrada</option>
            <option value="saida">Saída</option>
        </select>

        <select name="gerenciadora">
            <option value="VERDE">VERDE</option>
            <option value="AZUL">AZUL</option>
            <option value="OUTROS">OUTROS</option>
        </select>

        <button>Salvar</button>
    </form>
    </div>

    <div class="card">
    <h3>⚠️ Estoque Baixo</h3>
    {alerta.to_html(index=False)}
    </div>

    <div class="card">
    <h3>🧠 Previsão Inteligente (6 meses)</h3>
    {previsao}
    </div>

    <div class="card">
    <h3>📋 Estoque</h3>
    <table>
        <tr><th>Produto</th><th>Quantidade</th><th>Gerenciadora</th><th>Status</th></tr>
        {tabela}
    </table>
    </div>

    <br>
    <a href="/excel">📊 Exportar Excel</a>

    <p>{mensagem}</p>
    """

# =========================
# EXCEL
# =========================
@app.route("/excel")
def excel():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM estoque", conn)
    caminho = "estoque.xlsx"
    df.to_excel(caminho, index=False)
    conn.close()
    return send_file(caminho, as_attachment=True)

# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
