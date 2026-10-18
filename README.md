# Radar 30X con JEV

**Pruébalo:** https://radar-30x-three.vercel.app

Responde en una corrida, en 1 a 3 minutos y por unos 5 centavos de dólar:

> **¿Cuáles son los 10 temas que más están creciendo esta semana, por qué funcionan y cómo los adapta 30X para líderes de Latinoamérica?**

Funciona para IA (la demo principal), fitness o **cualquier temática libre** que escriba el usuario.

## Qué hace

1. **Detecta temprano.** Recolecta piezas públicas de YouTube, Reddit, Instagram, LinkedIn, TikTok y Hacker News, y mide la velocidad, la aceleración (con capturas cada 3 horas), el *outlier ratio* frente al canal, la saturación y en cuántas redes aparece cada tema.
2. **Explica por qué funciona.** JEV clasifica cada pieza (tema, gancho, formato, si menciona un lanzamiento) y el radar calcula qué gancho crece más, en qué red nació cada tema y cómo saltó entre redes.
3. **Filtra por audiencia.** JEV puntúa el ajuste a la audiencia (aplicabilidad, nivel técnico, relevancia para LatAm) y el código combina todo en un score con pesos visibles y ajustables.
4. **Adapta y anticipa.** Propone tres piezas listas para copiar (carrusel, reel y post de LinkedIn) y una lista de **lo que viene**: temas que todavía no son tendencia pero las señales apuntan a que lo serán.

## Cómo se reparten el trabajo

| Quién | Qué hace | Por qué |
| --- | --- | --- |
| **Código** | Recolecta, mide y **decide el ranking** | Reproducible y auditable: la IA no decide el orden |
| **JEV** (TypeSafe, `jev-1.13.0`) | Clasifica cada pieza con 8 preguntas tipadas en una sola llamada (fan-out); puntúa ideas y predicciones | Respuestas estructuradas con probabilidad y confianza, por fracciones de centavo |
| **DeepSeek** | Nombra los temas de la corrida, redacta el porqué y las ideas, y crea la configuración de una temática libre | Solo redacta; no toca el ranking |
| **Tavily** | Búsqueda web de posts públicos de LinkedIn, TikTok e Instagram | Las URLs vienen de la búsqueda; ningún modelo las inventa |

Cada respuesta con confianza baja de JEV se excluye del ranking. Los temas con menos de 3 piezas quedan como señal temprana y no entran al top 10.

## Costo real por corrida

Medido con el campo `usage` de cada respuesta, no estimado. Una corrida típica de IA (unas 300 piezas):

| Paso | Costo |
| --- | --- |
| JEV: clasificar unas 300 piezas | ~0,025 USD |
| DeepSeek: temas, redacción y predicciones | ~0,02 USD |
| YouTube, Reddit (RSS), Hacker News y Tavily | 0 USD (cuotas gratuitas) |
| **Total** | **~0,05 USD** |

La app muestra el costo exacto de cada corrida, su desglose y el historial.

## Arquitectura

```
Navegador ──► Vercel (web/ + api/)
                 │  POST /api/correr  ──►  GitHub Actions (radar.yml)
                 │  GET  /api/estado  ◄──  pasos de la corrida
                 │                           │  python -m radar recolectar / correr
                 │                           │  JEV + DeepSeek + Tavily + YouTube API
                 ◄── Vercel se redespliega ◄─┘  commit de resultados (out/, web/datos.json)

Cada 3 horas, GitHub Actions toma una captura nueva de métricas para medir la aceleración real.
```

- `radar/`: motor en Python (conectores por red, cliente JEV, scoring, LLM y servidor local).
- `api/`: funciones de Vercel que lanzan la corrida y leen su progreso.
- `web/index.html`: la app (landing, configuración de la corrida y resultados).
- `config/`: un archivo YAML por sector (palabras clave, persona, pesos y umbrales).
- `.github/workflows/radar.yml`: ejecución en la nube y capturas programadas.

## Correrlo en local

```bash
uv venv .venv
uv pip install --python .venv -r requirements.txt
cp .env.example .env        # y completa TYPESAFE_API_KEY, YOUTUBE_API_KEY, DEEPSEEK_API_KEY, TAVILY_API_KEY
.venv/Scripts/python -m radar probar     # verifica cada clave
.venv/Scripts/python -m radar servir     # app en http://localhost:8765
```

Desde la terminal:

```bash
.venv/Scripts/python -m radar correr --sector ia_latam
.venv/Scripts/python -m radar sector-nuevo --sector libre_cafe --nicho "café de especialidad"
```

## Fuentes y reglas

| Red | Vía | Métricas de crecimiento |
| --- | --- | --- |
| YouTube | Data API v3 (oficial) | Sí: vistas, likes y comentarios |
| Reddit | RSS público (o API oficial con claves) | Con API sí; con RSS, presencia y ajuste |
| Instagram | Búsqueda web (o Graph API con cuenta profesional) | Con Graph API sí |
| LinkedIn | Búsqueda web de posts indexados | Presencia y ajuste |
| TikTok | Búsqueda web + ranking de hashtags del Creative Center | Aceleración por hashtag |
| Hacker News | API de Algolia | Sí: puntos |

Nada detrás de login de terceros ni scraping que viole términos de uso, y solo datos de piezas públicas, nunca de personas. Las claves viven en `.env` (local) o en los secretos de GitHub; nunca en el repositorio.
