from flask import Flask, request, redirect, session, send_file
import psycopg2
import os
from datetime import datetime, timedelta
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = "estoque_secret"

DATABASE_URL = os.getenv("DATABASE_URL")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# CONEXÃO SEGURA
# ===============================
def conectar():
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except:
        return None

# ===============================
# CRIAR TABELAS
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
        cur.close()
        conn.close()

        if u:
            session["user"] = user
            session["tipo"] = u[3]
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

        # 🔠 BLOQUEIO MINUSCULO
        if item != item.upper():
            msg = "ERRO: Use apenas MAIÚSCULO"
        else:
            # 🚫 BLOQUEIO GERENCIADORA (EXCETO OUTROS)
            if ger != "OUTROS":
                for g in GERENCIADORAS:
                    if g in item:
                        msg = f"ERRO: Não usar {g} no nome"
                        break

        if msg == "":
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
                    cur.execute("INSERT INTO estoque (produto,quantidade,gerenciadora) VALUES (%s,%s,%s)",
                                (item,qtd,ger))

            cur.execute("INSERT INTO movimentacoes (produto,tipo,quantidade) VALUES (%s,%s,%s)",
                        (item,tipo,qtd))

            conn.commit()
            cur.close()
            conn.close()

    # ===============================
    # EXCEL + PREVISÃO
    # ===============================
    conn = conectar()
    if not conn:
        return "Erro banco"

    df = pd.read_sql("SELECT * FROM estoque", conn)
    mov = pd.read_sql("SELECT * FROM movimentacoes", conn)

    previsao = {}

    for produto in df["produto"]:
        ultimos = mov[(mov["produto"]==produto) & (mov["tipo"]=="SAIDA")]
        media = ultimos["quantidade"].mean() if not ultimos.empty else 0
        previsao[produto] = int(media * 6)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for g in GERENCIADORAS:
            grupo = df[df["gerenciadora"]==g]
            if grupo.empty: continue

            dados = []
            for _,row in grupo.iterrows():
                p = row["produto"]
                entradas = mov[(mov["produto"]==p)&(mov["tipo"]=="ENTRADA")]["quantidade"].sum()
                saidas = mov[(mov["produto"]==p)&(mov["tipo"]=="SAIDA")]["quantidade"].sum()

                dados.append({
                    "ITEM":p,
                    "ENTRADA":entradas,
                    "SAIDA":saidas,
                    "SALDO":row["quantidade"],
                    "PREVISAO_6M":previsao[p]
                })

            pd.DataFrame(dados).to_excel(writer, sheet_name=g, index=False)

    conn.close()

    alerta = df[df["quantidade"] < 5]

    return f"""
    <h2>🚀 Sistema de Estoque</h2>

    <p style='color:red;'>{msg}</p>

    <form method="post">
    Item: <input name="item"><br>
    Quantidade: <input name="qtd" type="number"><br>

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

    <h3>🔔 ALERTA ESTOQUE BAIXO</h3>
    {alerta.to_html() if not alerta.empty else "OK"}

    <br><br>
    <a href="/excel">📥 Baixar Excel</a>
    """

# ===============================
# DOWNLOAD EXCEL
# ===============================
@app.route("/excel")
def excel():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM estoque", conn)
    conn.close()

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name="estoque.xlsx", as_attachment=True)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar_tabelas()
    app.run(host="0.0.0.0", port=10000)
