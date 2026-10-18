// POST /api/correr {sector, redes[], recolectar, clave, nicho?, audiencia?} -> lanza "radar.yml" en GitHub Actions.
const { WORKFLOW, config, gh, ultimaCorrida, usoHoy, limpiar, claveRequerida } = require("./_github");
const REDES = ["youtube", "reddit", "instagram", "linkedin", "tiktok", "hn"];

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "usa POST" });
  try {
    const b = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    const esperado = claveRequerida();
    if (esperado && limpiar(b.clave) !== esperado) return res.status(401).json({ error: "Código de acceso incorrecto" });
    const sector = String(b.sector || "ia_latam");
    if (!/^[a-z0-9_]{2,60}$/.test(sector)) return res.status(400).json({ error: "sector inválido" });
    const nicho = String(b.nicho || "").replace(/[\r\n]+/g, " ").trim().slice(0, 140);
    const audiencia = String(b.audiencia || "").replace(/[\r\n]+/g, " ").trim().slice(0, 140);
    const redes = (Array.isArray(b.redes) ? b.redes : []).filter(r => REDES.includes(r));
    const recolectar = b.recolectar !== false || !!nicho;  // un nicho nuevo siempre necesita datos
    const previa = await ultimaCorrida();
    if (previa && previa.status !== "completed") return res.status(409).json({ error: "Ya hay una corrida en curso" });
    const uso = await usoHoy();
    if (recolectar && uso.completas >= uso.limites.completas)
      return res.status(429).json({ error: `Se alcanzó el límite de ${uso.limites.completas} corridas con datos nuevos por hoy. Desmarca "Traer datos nuevos" para reanalizar lo ya recolectado.` });
    if (!recolectar && uso.reanalisis >= uso.limites.reanalisis)
      return res.status(429).json({ error: `Se alcanzó el límite de ${uso.limites.reanalisis} reanálisis por hoy. Vuelve a intentarlo mañana.` });
    await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: config().ref, inputs: { sector, redes: redes.join(","), recolectar: recolectar ? "true" : "false", nicho, audiencia } }),
    });
    res.status(202).json({ ok: true, desde: Date.now() / 1000 });
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
};
