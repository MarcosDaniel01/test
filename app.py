from flask import Flask, request, redirect, session, send_file
import psycopg2
import os
from datetime import datetime, timedelta
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = "empresa_top"

DATABASE_URL = os.getenv("DATABASE_URL")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# CONEXÃO
# ===============================
def conectar():
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as e:
        print("ERRO DB:", e)
        return None

# ===============================
# TABELAS
# ===============================
def criar_tabelas():
    conn = conectar()
    if not conn: return
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
        produto TEXT PRIMARY KEY,
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
# LOGIN
# ===============================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form["user"]
        senha = request.form["senha"]

        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario=%s AND senha=%s",(user,senha))
        u = cur.fetchone()

        if u:
            session["user"] = user
            return redirect("/home")

    return """
    <h2>Login</h2>
    <form method="post">
    <input name="user" placeholder="Usuário"><br>
    <input name="senha" type="password"><br>
    <button>Entrar</button>
    </form>
    """

# ===============================
# HOME
# ===============================
@app.route("/home", methods=["GET","POST"])
def home():
    if "user" not in session:
        return redirect("/")

    msg = ""

    if request.method == "POST":
        item = request.form["item"]
        qtd = int(request.form["qtd"])
        tipo = request.form["tipo"]
        ger = request.form["ger"]

        # 🔠 BLOQUEIO MAIUSCULO
        if item != item.upper():
            msg = "ERRO: SOMENTE MAIÚSCULO"

        # 🚫 BLOQUEIO GERENCIADORA NO NOME
        elif ger != "OUTROS":
            for g in GERENCIADORAS:
                if g in item:
                    msg = f"ERRO: NÃO USAR {g} NO NOME"

        else:
            conn = conectar()
            cur = conn.cursor()

            cur.execute("SELECT quantidade FROM estoque WHERE produto=%s",(item,))
            existe = cur.fetchone()

            if existe:
                if tipo == "ENTRADA":
                    cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE produto=%s",(qtd,item))
                else:
                    cur.execute("UPDATE estoque SET quantidade = quantidade - %s WHERE produto=%s",(qtd,item))
            else:
                if tipo == "ENTRADA":
                    cur.execute("INSERT INTO estoque VALUES (%s,%s,%s)",(item,qtd,ger))

            cur.execute("INSERT INTO movimentacoes (produto,tipo,quantidade) VALUES (%s,%s,%s)",
                        (item,tipo,qtd))

            conn.commit()
            cur.close()
            conn.close()

    return """
    <h2>🚀 Sistema Profissional</h2>

    <form method="post">
    Item: <input name="item"><br>
    Qtd: <input name="qtd" type="number"><br>

    Tipo:
    <select name="tipo">
        <option>ENTRADA</option>
        <option>SAIDA</option>
    </select><br>

    Gerenciadora:
    <select name="ger">
        <option>PRIME</option>
        <option>LINK</option>
        <option>NEO</option>
        <option>FITMOBY</option>
        <option>OUTROS</option>
    </select><br><br>

    <button>Salvar</button>
    </form>

    <br>
    <a href="/excel">📊 BAIXAR PLANILHA PROFISSIONAL</a>
    """

# ===============================
# EXCEL PROFISSIONAL
# ===============================
@app.route("/excel")
def excel():

    conn = conectar()
    df = pd.read_sql("SELECT * FROM estoque", conn)
    mov = pd.read_sql("SELECT * FROM movimentacoes", conn)

    hoje = datetime.now()
    inicio_mes = hoje.replace(day=1)
    seis_meses = hoje - timedelta(days=180)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        for g in GERENCIADORAS:

            grupo = df[df["gerenciadora"] == g]

            if grupo.empty:
                continue

            tabela = []

            for _, row in grupo.iterrows():

                produto = row["produto"]

                entrada_mes = mov[
                    (mov["produto"] == produto) &
                    (mov["tipo"] == "ENTRADA") &
                    (mov["data"] >= inicio_mes)
                ]["quantidade"].sum()

                saida_mes = mov[
                    (mov["produto"] == produto) &
                    (mov["tipo"] == "SAIDA") &
                    (mov["data"] >= inicio_mes)
                ]["quantidade"].sum()

                saida_6m = mov[
                    (mov["produto"] == produto) &
                    (mov["tipo"] == "SAIDA") &
                    (mov["data"] >= seis_meses)
                ]["quantidade"].sum()

                media = saida_6m / 6 if saida_6m else 0
                previsao = int(media * 6 * 1.2)

                tabela.append({
                    "ITEM": produto,
                    "ENTRADA_MES": entrada_mes,
                    "SAIDA_MES": saida_mes,
                    "SAIDA_6_MESES": saida_6m,
                    "SALDO": row["quantidade"],
                    "PREVISAO_6M+20%": previsao
                })

            df_final = pd.DataFrame(tabela)

            df_final.to_excel(writer, sheet_name=g, index=False)

    conn.close()

    output.seek(0)

    return send_file(output, download_name="relatorio_profissional.xlsx", as_attachment=True)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar_tabelas()
    app.run(host="0.0.0.0", port=10000)
