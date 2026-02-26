@app.route("/sistema")
def sistema():
    if "user" not in session:
        return redirect("/")

    dados = calcular()

    # separar por gerenciadora
    grupos = {}
    for d in dados:
        grupos.setdefault(d["gerenciadora"], []).append(d)

    # itens para operador
    itens = {}
    for d in Movimentacao.query.all():
        itens.setdefault(d.gerenciadora, set()).add(d.item)

    itens = {k:list(v) for k,v in itens.items()}

    # campo item
    if session["tipo"] == "admin":
        campo_item = "<input name='item' placeholder='ITEM (MAIÚSCULO)' required>"
    else:
        campo_item = "<select name='item' id='itemSelect'></select>"

    html = f"""
    <html>
    <head>
    <style>
    body{{margin:0;font-family:Arial;background:#eef2f7}}
    .topbar{{background:linear-gradient(90deg,#1e3c72,#2a5298);
    color:white;padding:20px;text-align:center;font-size:22px;font-weight:bold}}
    .container{{width:95%;margin:auto}}
    .card{{background:white;margin:20px auto;padding:20px;border-radius:12px;
    box-shadow:0 5px 15px rgba(0,0,0,0.1);max-width:900px}}
    h3{{margin-top:0}}
    input,select{{width:100%;padding:10px;margin:8px 0;border-radius:8px;border:1px solid #ccc}}
    button{{padding:10px 15px;background:#2a5298;color:white;border:none;border-radius:8px}}
    table{{width:100%;border-collapse:collapse;margin-top:15px}}
    th{{background:#2a5298;color:white;padding:10px}}
    td{{padding:10px;text-align:center;border-bottom:1px solid #eee}}
    .ok{{color:green;font-weight:bold}}
    .comprar{{color:red;font-weight:bold}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
    </style>
    </head>
    <body>

    <div class="topbar">
        📦 CONTROLE DE ESTOQUE | {session["user"].upper()}
    </div>

    <div class="container">

    <div class="card">
    <h3>Nova Movimentação</h3>
    <form method="POST" action="/inserir">

    <select name="ger" id="gerSelect">
    {"".join([f"<option value='{g}'>{g}</option>" for g in GERENCIADORAS])}
    </select>

    <select name="tipo">
    <option value="ENTRADA">ENTRADA</option>
    <option value="SAIDA">SAIDA</option>
    </select>

    {campo_item}

    <input name="qtd" type="number" placeholder="Quantidade" required>

    <button>Salvar</button>
    </form>
    </div>
    """

    # ========= ESTOQUE SEPARADO =========
    for ger in GERENCIADORAS:
        lista = grupos.get(ger, [])

        html += f"""
        <div class="card">
        <h3>🏢 {ger}</h3>
        <table>
        <tr>
        <th>Item</th>
        <th>Entrada</th>
        <th>Saída</th>
        <th>Saldo</th>
        <th>Média Mensal</th>
        <th>Previsão 6M +20%</th>
        <th>Status</th>
        </tr>
        """

        for d in lista:
            cls = "ok" if d["status"] == "OK" else "comprar"

            html += f"""
            <tr>
            <td>{d['item']}</td>
            <td>{d['entrada']}</td>
            <td>{d['saida']}</td>
            <td>{d['saldo']}</td>
            <td>{d['media']}</td>
            <td>{d['proj']}</td>
            <td class="{cls}">{d['status']}</td>
            </tr>
            """

        html += "</table></div>"

    # ========= ADMIN USUARIOS =========
    if session["tipo"] == "admin":
        usuarios = Usuario.query.all()
        linhas = ""

        for u in usuarios:
            if u.usuario == "admin":
                acao = "ADMIN"
            elif u.usuario == session["user"]:
                acao = "VOCÊ"
            else:
                acao = f"""
                <form method='POST' action='/excluir_usuario'>
                <input type='hidden' name='usuario' value='{u.usuario}'>
                <button style='background:red'>Excluir</button>
                </form>
                """

            linhas += f"<tr><td>{u.usuario}</td><td>{u.tipo}</td><td>{acao}</td></tr>"

        html += f"""
        <div class="card">
        <h3>👥 Usuários</h3>
        <table>
        <tr><th>Usuário</th><th>Tipo</th><th>Ação</th></tr>
        {linhas}
        </table>

        <h3>Criar Usuário</h3>
        <form method="POST" action="/criar_usuario">
        <input name="usuario" placeholder="Usuário" required>
        <input name="senha" placeholder="Senha" required>
        <select name="tipo">
        <option value="admin">Admin</option>
        <option value="operador">Operador</option>
        </select>
        <button>Criar</button>
        </form>
        </div>
        """

    # ========= JS =========
    html += f"""
    </div>

    <script>
    const itens = {json.dumps(itens)};
    const ger = document.getElementById("gerSelect");
    const item = document.getElementById("itemSelect");

    function atualizar(){{
        if(!item) return;
        item.innerHTML="";
        (itens[ger.value] || []).forEach(i => {{
            let o = document.createElement("option");
            o.text = i;
            item.add(o);
        }});
    }}

    ger.onchange = atualizar;
    window.onload = atualizar;
    </script>

    </body></html>
    """

    return html
