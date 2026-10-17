// POST /api/correr {sector, redes[], recolectar, clave} -> lanza el flujo "radar.yml" en GitHub Actions.
const { WORKFLOW, config, gh, ultimaCorrida } = require("./_github");
const REDES = ["youtube", "reddit", "instagram", "linkedin", "tiktok", "hn"];

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "usa POST" });
  try {
    const b = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    // se ignoran espacios y comillas sobrantes, que suelen colarse al copiar y pegar
    const limpiar = v => String(v || "").trim().replace(/^["']+|["']+$/g, "").trim();
    const esperado = limpiar(process.env.RADAR_CLAVE_ACCESO);
    if (!esperado) return res.status(500).json({ error: "Falta RADAR_CLAVE_ACCESO en Vercel" });
    if (limpiar(b.clave) !== esperado) return res.status(401).json({ error: "Código de acceso incorrecto" });
    const sector = String(b.sector || "ia_latam");
    if (!/^[a-z_]{2,40}$/.test(sector)) return res.status(400).json({ error: "sector inválido" });
    const redes = (Array.isArray(b.redes) ? b.redes : []).filter(r => REDES.includes(r));
    const previa = await ultimaCorrida();
    if (previa && previa.status !== "completed") return res.status(409).json({ error: "Ya hay una corrida en curso" });
    await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: config().ref, inputs: { sector, redes: redes.join(","), recolectar: b.recolectar === false ? "false" : "true" } }),
    });
    res.status(202).json({ ok: true, desde: Date.now() / 1000 });
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
};
