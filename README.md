# Radar 30X con JEV

Responde en una corrida: **¿cuáles son los 10 temas que más están creciendo esta semana, por qué funcionan y cómo los adapta 30X?**

- **Código:** mide velocidad, outlier, aceleración, saturación y multired, y decide el ranking.
- **JEV:** clasifica cada pieza (sector, tema, gancho, formato, lanzamiento, ajuste a la audiencia) en una sola llamada.
- **LLM (DeepSeek):** propone los nombres de los temas y redacta el porqué y las ideas.
- **Tavily:** búsqueda web de posts públicos de LinkedIn, TikTok e Instagram (las URLs vienen de la API, nadie las inventa).

## 1. Preparar (una vez)

1. Abre `.env` y pega tus claves: `TYPESAFE_API_KEY`, `YOUTUBE_API_KEY`, `DEEPSEEK_API_KEY` y `TAVILY_API_KEY`. Reddit e Instagram son opcionales.
2. Verifica las claves:

```bash
.venv/Scripts/python -m radar probar
```

Si `.venv` no existe: `uv venv .venv` y `uv pip install --python .venv -r requirements.txt`.

## 2. Usar la app (recomendado)

```bash
.venv/Scripts/python -m radar servir
```

Abre http://localhost:8765 y sigue estos pasos:

1. **Inicio:** elige el sector (IA para líderes o fitness) y marca las redes que quieres revisar. Cada red indica si aporta métricas de crecimiento o solo presencia y ajuste.
2. **Correr radar:** el progreso se ve en vivo, paso a paso (recolección, temas, JEV, score, ideas, lo que viene). Desmarca "Traer datos nuevos" para reanalizar lo ya recolectado en menos tiempo.
3. **Resultados**, en cinco pestañas:
   - **Tendencias hoy:** top 10 con etapa, porqué, ruta de propagación entre redes y pesos ajustables.
   - **Lo que viene:** temas que todavía no son tendencia pero las señales de hoy apuntan a que pueden serlo.
   - **Ideas para 30X:** tres piezas para el tema número 1, puntuadas por JEV.
   - **Origen de las tendencias:** en qué red nace cada tema, cuánto tarda en saltar y qué fuentes externas se citan.
   - **Costo y transparencia:** gasto real por paso, proyección mensual, historial y cobertura por red.

## 3. Correr el radar desde la terminal

```bash
.venv/Scripts/python -m radar correr --sector ia_latam
```

Esto recolecta las cinco redes, clasifica con JEV, calcula el score, redacta y escribe `out/ia_latam.json` y `web/data.js`. Para fitness, cambia a `--sector fitness`. Para elegir redes: `--redes youtube,reddit,linkedin`.

Para repetir el análisis sin volver a recolectar (no gasta cuota de YouTube):

```bash
.venv/Scripts/python -m radar correr --sector ia_latam --sin-recolectar
```

## 4. Aceleración: capturas repetidas

La aceleración necesita al menos dos capturas de métricas separadas por un rato. Después de la primera corrida, deja esto abierto en una terminal; toma una captura cada 3 horas:

```bash
.venv/Scripts/python -m radar capturar --sector ia_latam --cada 3
```

Sin capturas repetidas, el panel marca la aceleración como "estimada" y usa la velocidad como sustituto.

## 5. Publicar en Vercel (solo lectura)

La carpeta `web/` funciona sola: sin servidor, la app entra en modo de solo lectura y muestra la última corrida guardada en `web/data.js`.

Publicado en https://radar-30x-three.vercel.app (proyecto `radar-30x`). Para actualizarlo después de una corrida nueva, desde PowerShell:

```bash
cd web; vercel deploy --prod
```

Para actualizar la versión publicada, corre el radar en local y vuelve a desplegar. Solo se sube `web/`; el `.env` con las claves nunca sale de tu computadora.

## Fuentes y qué aporta cada una

| Red | Vía | Métricas |
| --- | --- | --- |
| YouTube | Data API v3 | Sí: vistas, likes, comentarios |
| Reddit | API OAuth (con claves) o RSS público | Con API sí; con RSS no |
| Instagram | Graph API (con cuenta profesional) o búsqueda web | Con Graph API sí; con búsqueda web no |
| LinkedIn | Búsqueda web de posts indexados + `data/comunidad.csv` | No |
| TikTok | `data/tiktok_hashtags.csv` (Creative Center) + búsqueda web | Aceleración por hashtag |
| Hacker News | Algolia (opcional) | Sí: puntos |

**Comunidad** (`data/comunidad.csv`): el equipo pega links que ve en su feed. Una fila por link: `sector,red,url,titulo,autor,fecha`.

**TikTok** (`data/tiktok_hashtags.csv`): copia una vez al día el top de hashtags por país desde el Creative Center de TikTok. Una fila por hashtag: `fecha,pais,hashtag,posicion,publicaciones`. Con dos o más fechas registradas, el radar mide la aceleración de cada hashtag.

## Configuración

- `config/ia_latam.yaml` y `config/fitness.yaml`: palabras clave, subreddits, cuentas, persona, pesos y umbrales.
- `config/global.yaml`: versión de JEV (fija en `jev-1.13.0`), modelos de DeepSeek y precios para el contador. Verifica los precios en api-docs.deepseek.com.

## Notas

- Las URLs de LinkedIn, TikTok e Instagram vienen directo de la API de búsqueda (Tavily) y solo se aceptan páginas de posts individuales.
- Las respuestas de las APIs se guardan en `data/cache/` durante unas horas, y las de JEV en `data/radar.db`, para no pagar dos veces.
