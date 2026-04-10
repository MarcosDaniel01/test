const { Client } = require("pg");

async function connect() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false }
  });
  await client.connect();
  return client;
}

exports.handler = async (event) => {
  const path = event.path;
  const method = event.httpMethod;
  const body = event.body ? JSON.parse(event.body) : {};

  const db = await connect();

  try {

    if (path.includes("login") && method === "POST") {
      const res = await db.query(
        "SELECT * FROM usuario WHERE usuario=$1 AND senha=$2",
        [body.usuario, body.senha]
      );

      return {
        statusCode: res.rows.length ? 200 : 401,
        body: JSON.stringify({ ok: res.rows.length > 0, user: res.rows[0] })
      };
    }

    if (path.includes("inserir") && method === "POST") {
      await db.query(
        `INSERT INTO movimentacao (gerenciadora, tipo, item, quantidade)
         VALUES ($1,$2,$3,$4)`,
        [body.ger, body.tipo, body.item.toUpperCase(), body.qtd]
      );

      return { statusCode: 200, body: JSON.stringify({ ok: true }) };
    }

    if (path.includes("dados")) {
      const res = await db.query("SELECT * FROM movimentacao");

      const dados = {};

      res.rows.forEach(d => {
        const chave = d.gerenciadora + "|" + d.item;

        if (!dados[chave]) dados[chave] = { entrada: 0, saida: 0 };

        if (d.tipo === "ENTRADA") dados[chave].entrada += d.quantidade;
        else dados[chave].saida += d.quantidade;
      });

      const final = [];

      Object.keys(dados).forEach(key => {
        const [ger, item] = key.split("|");
        const v = dados[key];

        const saldo = v.entrada - v.saida;
        const media = v.saida;
        const proj = Math.floor(media * 6 * 1.2);
        const status = saldo >= proj ? "OK" : "COMPRAR";

        final.push({ ger, item, ...v, saldo, media, proj, status });
      });

      return { statusCode: 200, body: JSON.stringify(final) };
    }

    return { statusCode: 404, body: "rota nao encontrada" };

  } catch (e) {
    return { statusCode: 500, body: e.message };
  } finally {
    await db.end();
  }
};