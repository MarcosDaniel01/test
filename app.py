from flask import Flask, request, redirect, session, send_file
import psycopg2
import os
from datetime import datetime, timedelta
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = "empresa_estoque"

DATABASE_URL = os.getenv("DATABASE_URL")

GERENCIADORAS = ["PRIME", "LINK", "NEO", "FITMOBY", "OUTROS"]

# ===============================
# CONEXÃO
# ===============================
def conectar():
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as e:
        print("Erro conexão:", e)
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
            return redirect("/home")

    return """
    <h2>🔐 Login</h2>
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

        # BLOQUEIO MAIUSCULO
        if item != item.upper():
            msg = "❌ Use apenas letras MAIÚSCULAS"

        # BLOQUEIO GERENCIADORA
        if ger != "OUTROS":
            for g in GERENCIADORAS:
                if g in item:
                    msg = f"❌ Não usar {g} no nome"

        if msg == "":
            conn = conectar()
            cur = conn.cursor()

            cur.execute("SELECT quantidade FROM estoque WHERE produto=%s",(item,))
            existe = cur.fetchone()

            if existe:
                if tipo == "ENTRADA":
                    cur.execute("UPDATE estoque SET quantidade=quantidade+%s WHERE produto=%s",(qtd,item))
                else:
                    cur.execute("UPDATE estoque SET quantidade=quantidade-%s WHERE produto=%s",(qtd,item))
            else:
                if tipo == "ENTRADA":
                    cur.execute("INSERT INTO estoque VALUES (DEFAULT,%s,%s,%s)",(item,qtd,ger))

            cur.execute("INSERT INTO movimentacoes VALUES (DEFAULT,%s,%s,%s,DEFAULT)",(item,tipo,qtd))

            conn.commit()
            cur.close()
            conn.close()

    # ===============================
    # DADOS
    # ===============================
    conn = conectar()
    df = pd.read_sql("SELECT * FROM estoque", conn)
    mov = pd.read_sql("SELECT * FROM movimentacoes", conn)

    hoje = datetime.now()
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

                entradas = mov[(mov["produto"]==produto)&(mov["tipo"]=="ENTRADA")]["quantidade"].sum()
                saidas = mov[(mov["produto"]==produto)&(mov["tipo"]=="SAIDA")]["quantidade"].sum()

                ult6 = mov[(mov["produto"]==produto)&(mov["tipo"]=="SAIDA")&(mov["data"]>=seis_meses)]
                total6 = ult6["quantidade"].sum()

                media_mensal = total6 / 6 if total6 else 0

                previsao = int((media_mensal * 6) * 1.2)

                tabela.append({
                    "ITEM": produto,
                    "ENTRADA_TOTAL": entradas,
                    "SAIDA_TOTAL": saidas,
                    "SAIDA_MENSAL_MEDIA": round(media_mensal,2),
                    "SAIDA_ULT_6_MESES": total6,
                    "PREVISAO_PROX_6_MESES(+20%)": previsao,
                    "SALDO": row["quantidade"]
                })

            pd.DataFrame(tabela).to_excel(writer, sheet_name=g, index=False)

    conn.close()

    alerta = df[df["quantidade"] < 5]

    return f"""
    <h2>🚀 Sistema Profissional de Estoque</h2>

    <p style='color:red;'>{msg}</p>

    <form method="post">
    <b>Item:</b><br><input name="item"><br>
    <b>Quantidade:</b><br><input name="qtd" type="number"><br>

    <b>Tipo:</b><br>
    <select name="tipo">
        <option>ENTRADA</option>
        <option>SAIDA</option>
    </select><br>

    <b>Gerenciadora:</b><br>
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
    <a href="/excel">📥 Baixar Excel Profissional</a>
    """

# ===============================
# EXCEL DOWNLOAD
# ===============================
@app.route("/excel")
def excel():
    return redirect("/home")

# ===============================
# START
# ===============================
if __name__ == "__main__":
    criar_tabelas()
    app.run(host="0.0.0.0", port=10000)
