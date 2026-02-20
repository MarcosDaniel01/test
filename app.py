from flask import Flask, request, redirect
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

# =========================
# BANCO
# =========================
def conectar():
    return sqlite3.connect("estoque.db")


def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimentacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        gerenciadora TEXT,
        tipo TEXT,
        item TEXT,
        quantidade INTEGER
    )
    """)

    conn.commit()
    conn.close()


criar_tabela()


# =========================
# ESTOQUE + IA
# =========================
def calcular():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT gerenciadora, item,
    SUM(CASE WHEN tipo='ENTRADA' THEN quantidade ELSE 0 END),
    SUM(CASE WHEN tipo='SAIDA' THEN quantidade ELSE 0 END)
    FROM movimentacao
    GROUP BY gerenciadora, item
    """)

    dados = cursor.fetchall()
    conn.close()

    resultado = []

    for ger, item, entrada, saida in dados:
        entrada = entrada or 0
        saida = saida or 0
        saldo = entrada - saida

        conn = conectar()
        cursor = conn.cursor()

        data_limite = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        cursor.execute("""
        SELECT SUM(quantidade)
        FROM movimentacao
        WHERE tipo='SAIDA'
        AND gerenciadora=?
        AND item=?
        AND data >= ?
        """, (ger, item, data_limite))

        media = cursor.fetchone()[0] or 0
        conn.close()

        projecao = media * 6
        status = "PEDIR" if saldo < projecao else "OK"

        resultado.append({
            "ger": ger,
            "item": item,
            "entrada": entrada,
            "saida": saida,
            "saldo": saldo,
            "media": media,
            "proj": projecao,
            "status": status
        })

    return resultado


# =========================
# HOME
# =========================
@app.route("/")
def index():
    dados = calcular()

    html = """
    <html>
    <head>
        <title>Estoque Inteligente</title>
        <style>
            body { font-family: Arial; background: #f4f4f4; text-align:center; }

            h1 { background:#222; color:white; padding:10px; }

            form {
                background:white;
                padding:20px;
                margin:20px auto;
                width:500px;
                border-radius:10px;
                box-shadow:0 0 10px #ccc;
            }

            select, input {
                padding:10px;
                margin:5px;
                width:90%;
            }

            button {
                background:green;
                color:white;
                padding:15px;
                border:none;
                width:95%;
                font-size:18px;
                border-radius:8px;
            }

            table {
                width:95%;
                margin:auto;
                border-collapse:collapse;
                background:white;
            }

            th, td {
                padding:8px;
                border:1px solid #ccc;
            }

            th { background:black; color:white; }

            .PRIME { background:#2e7d32; color:white; }
            .LINK { background:#1565c0; color:white; }
            .NEO { background:#00897b; color:white; }
            .OUTROS { background:#ef6c00; color:white; }

        </style>
    </head>
    <body>

    <h1>📦 ESTOQUE INTELIGENTE</h1>

    <form method="POST" action="/inserir">
        <select name="gerenciadora">
            <option>PRIME</option>
            <option>LINK</option>
            <option>NEO</option>
            <option>OUTROS</option>
        </select>

        <select name="tipo">
            <option>ENTRADA</option>
            <option>SAIDA</option>
        </select>

        <input name="item" placeholder="ITEM" required>
        <input name="quantidade" type="number" placeholder="QUANTIDADE" required>

        <button type="submit">INSERIR</button>
    </form>

    <table>
    <tr>
        <th>GERENCIADORA</th>
        <th>ITEM</th>
        <th>ENTRADA</th>
        <th>SAIDA</th>
        <th>SALDO</th>
        <th>MÉDIA</th>
        <th>6 MESES</th>
        <th>STATUS</th>
    </tr>
    """

    for d in dados:
        html += f"""
        <tr class="{d['ger']}">
            <td>{d['ger']}</td>
            <td>{d['item']}</td>
            <td>{d['entrada']}</td>
            <td>{d['saida']}</td>
            <td>{d['saldo']}</td>
            <td>{d['media']}</td>
            <td>{d['proj']}</td>
            <td><b>{d['status']}</b></td>
        </tr>
        """

    html += "</table></body></html>"

    return html


# =========================
# INSERIR
# =========================
@app.route("/inserir", methods=["POST"])
def inserir():
    try:
        data = datetime.now().strftime("%Y-%m-%d")

        ger = request.form["gerenciadora"].upper()
        tipo = request.form["tipo"].upper()
        item = request.form["item"].upper()
        qtd = int(request.form["quantidade"])

        if tipo not in ["ENTRADA", "SAIDA"]:
            return "ERRO: tipo inválido"

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO movimentacao (data, gerenciadora, tipo, item, quantidade)
        VALUES (?, ?, ?, ?, ?)
        """, (data, ger, tipo, item, qtd))

        conn.commit()
        conn.close()

        return redirect("/")

    except Exception as e:
        return f"Erro: {e}"


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
