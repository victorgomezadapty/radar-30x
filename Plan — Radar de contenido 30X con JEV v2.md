# Plan v2 — Radar de contenido 30X con JEV

Oct 17, 2026 · @Victor Gomez · Revisión de la v1 con datos verificados en docs.typesafe.ai

## Resumen

Construimos un radar que responde en una corrida, por centavos de JEV: **"¿Cuáles son los 10 temas de IA que más están creciendo esta semana, por qué funcionan y cómo los adapta 30X para líderes de Latinoamérica?"**

El prototipo resuelve las tres preguntas del reto:

- **Detectar temprano:** mide velocidad y aceleración de cada pieza con capturas repetidas, no su volumen total.
- **Explicar por qué funcionó:** JEV clasifica gancho, formato y tema de cada pieza; el código suma las señales de momento y autoridad.
- **Filtrar por audiencia:** JEV puntúa el ajuste a "ejecutivo LatAm aprendiendo IA" y el código combina todo con pesos visibles.

La tesis para el jurado: el scraping pago trae datos; nosotros traemos la decisión, con las cinco redes que importan a 30X (YouTube, LinkedIn, Instagram, TikTok y Reddit), cada una aportando solo las señales que de verdad puede medir, y un costo por corrida medido, no estimado.

## Cambios respecto a la v1

| Cambio | Motivo |
| --- | --- |
| Temas dinámicos: Claude propone 15–20 temas finos por corrida y JEV asigna cada pieza con un `choice` | La taxonomía fija de 7 categorías no alcanza para un top 10, y si Claude agrupa, Claude decide el ranking |
| Se eliminan `es_copia` y `fuente_original` | JEV solo ve el `state`: no sabe qué está "ampliamente cubierto" ni cuál es la fuente primaria. La saturación ya se calcula en código |
| `atado_a_noticia` pasa a `menciona_lanzamiento` | JEV puede detectar si el texto menciona un lanzamiento, no si coincide con una noticia que no conoce |
| "Fuente original" = pieza más temprana del grupo, calculada por fecha | Cero riesgo de inventar URLs; se elimina el rastreo con búsqueda web |
| Capturas programadas cada 3–6 h en SQLite desde el día 0 | Sin historia no hay aceleración |
| Saturación calculada hacia atrás con fechas de publicación | No depende de tener semanas de historia propia |
| Fórmula con todos los términos definidos y paso explícito de pieza a tema | La v1 dejaba `temprano` y la normalización sin definir, y puntuaba piezas cuando el entregable pide temas |
| Confianza de `noul` calculada en código con `\|2p − 1\|` | `noul` no devuelve `confidence`; solo `choice` y `score` lo traen |
| Las cinco redes entran en la demo con una matriz de señales por red | Son las redes que importan a 30X. LinkedIn y TikTok no dan métricas por pieza por vías permitidas, así que aportan presencia, saturación y ajuste, no crecimiento |
| Nueva señal "multired": un tema presente en 3 o más redes sube en el ranking | Convierte la falta de métricas en LinkedIn y TikTok en una señal útil |
| Hacker News y arXiv pasan a opcionales | Liberan tiempo para integrar las cinco redes |
| Los accesos (Reddit, Meta, búsqueda web) se piden hoy, en la Puerta 0 | Son los pasos con espera externa; no pueden empezar el 21 |
| Validación con 40 piezas etiquetadas a mano | La v1 no medía si JEV acierta en español |
| Cambio a fitness con corrida ya guardada | Quita riesgo a la demo sin perder el argumento de que generaliza |

## Decisión de nicho

Sin cambios: el motor es agnóstico al sector, la demo principal va en **IA para líderes LatAm** y **fitness** queda como segunda configuración. El sector vive en un archivo de configuración:

```yaml
sector: ia_latam
keywords: ["agentes IA", "IA generativa empresa", "AI agents", "Claude", "ChatGPT empresa", ...]
canales_semilla: ["<channel_id>", ...]
persona: "Ejecutivo o equipo en Latinoamérica aprendiendo a usar IA en su empresa"
pista_temas: "Temas de IA relevantes para negocio, no investigación pura"
pesos:
  pieza:  { crecimiento: 0.5, ajuste: 0.5 }
  tema:   { fuerza: 0.35, aceleracion: 0.20, temprano: 0.20, multired: 0.15, frescura: 0.10 }
redes:
  youtube:   { activa: true }
  reddit:    { activa: true, subreddits: ["artificial", "ChatGPT", "LocalLLaMA", "Emprendedores", ...] }
  instagram: { activa: true, hashtags: ["inteligenciaartificial", "iaparanegocios", ...], cuentas: ["crece30x", ...] }
  linkedin:  { activa: true, consultas: ["agentes IA empresa", ...] }
  tiktok:    { activa: true, paises: ["MX", "CO", "AR", "CL", "PE"] }
umbrales:
  es_ia: 0.6
  confianza_min: 0.6
```

## Arquitectura

Claude nunca decide el ranking y JEV nunca busca ni redacta: el código mide y combina, y cada paso registra el `usage` real de su respuesta para el contador de costo.

1. **Ingesta (código):** un conector por red (YouTube, Reddit, Instagram, LinkedIn, TikTok) que entrega piezas con el mismo esquema: red, URL, texto, cuenta pública, fecha y métricas si existen. Toda respuesta de API se guarda en caché.
2. **Capturas (código, programado cada 3–6 h):** métricas de las piezas de YouTube, Reddit e Instagram a SQLite; ranking de hashtags de TikTok una vez al día.
3. **Métricas (código):** velocidad, outlier ratio, aceleración y saturación.
4. **Temas de la corrida (Claude, modelo pequeño):** lee solo títulos y propone 15–20 temas con nombre corto y descripción de una línea. Es la lista de opciones del `choice` de JEV, más "otro".
5. **Clasificación (JEV):** una llamada por pieza con todas las preguntas (fan-out), unas 8 llamadas en paralelo.
6. **Score y ranking (código):** pesos del archivo de configuración; salida a JSON.
7. **Explicación e ideas (Claude):** una línea de "por qué funciona" para cada tema del top 10 y 3 ideas de carrusel o reel para el tema número 1.
8. **Panel (HTML estático):** lee el JSON, muestra el top 10, permite mover pesos y recalcula en el navegador; contador de costo visible.

## Fuentes de datos

Las cinco redes entran en la demo. Ninguna red se fuerza a dar lo que su vía permitida no da: cada una aporta las señales que puede medir y el panel muestra la cobertura por red con honestidad.

| Red | Vía permitida | Qué trae | Límite principal |
| --- | --- | --- | --- |
| YouTube | YouTube Data API v3 (oficial, cuota gratuita diaria) | Vistas, likes, comentarios, fecha, canal | 10.000 unidades/día; cada búsqueda cuesta 100, cada lectura 1 |
| Reddit | API oficial con app OAuth registrada | Score, comentarios, `upvote_ratio`, fecha, subreddit | Registrar la app hoy; el acceso nuevo puede requerir aprobación |
| Instagram | Graph API con una cuenta profesional propia: Business Discovery (cuentas business/creator por nombre) y búsqueda por hashtag | Likes, comentarios, fecha y texto de posts públicos | App de Meta en modo desarrollo; búsqueda por hashtag limitada a 30 hashtags distintos cada 7 días |
| LinkedIn | API de búsqueda web sobre posts públicos indexados (`site:linkedin.com/posts`) + links que envía la comunidad | URL, texto, autor, fecha aproximada | Sin métricas de engagement por pieza |
| TikTok | Creative Center (hashtags en tendencia por país, públicos) + búsqueda web (`site:tiktok.com`) + oEmbed para título y autor | Ranking diario de hashtags por país LatAm; videos por tema sin métricas | Research API solo para academia; revisar el día 0 qué se ve sin login |

**Matriz de señales por red**

| Señal | YouTube | Reddit | Instagram | LinkedIn | TikTok |
| --- | --- | --- | --- | --- | --- |
| Velocidad y outlier por pieza | Sí | Sí | Sí | No | No |
| Aceleración (capturas) | Sí | Sí | Sí | No | Por hashtag (ranking diario) |
| Presencia del tema y saturación | Sí | Sí | Sí | Sí | Sí |
| Ajuste a la audiencia (JEV) | Sí | Sí | Sí | Sí | Sí |
| Gancho y formato (JEV) | Sí | Sí | Sí | Sí | Solo si hay texto |

**Orden de integración:** YouTube y Reddit primero (APIs con métricas, menos riesgo), después Instagram (depende del acceso a Meta), y LinkedIn y TikTok al final (sin métricas, pero simples de conectar).

**Opcionales si sobra tiempo:** Hacker News (Algolia) y arXiv como señales tempranas para el sector IA.

Regla de oro sin cambios: nada detrás de login de terceros, nada de scraping que viole términos, y solo datos de piezas, nunca de personas. La cuenta de Instagram usada para la Graph API es una cuenta profesional del equipo (la de Optimo, la tuya o la de 30X si la autorizan).

## Modelo de señales

**1. Crecimiento (código, sin modelo)**

- **Velocidad:** vistas por hora desde la publicación.
- **Outlier ratio:** vistas de la pieza divididas por la mediana de las últimas 10–15 piezas del mismo canal (`playlistItems`, 1 unidad por lectura). Aísla el contenido del tamaño de la cuenta.
- **Aceleración:** cambio de velocidad entre las dos últimas capturas.
- **Saturación del tema:** cuentas distintas que publicaron sobre el tema en los últimos 7 días contra los 7 anteriores, calculado con la fecha de publicación en las cinco redes.
- **Multired:** en cuántas de las cinco redes aparece el tema esta semana. Un tema que salta de Reddit a YouTube y LinkedIn es más fuerte que uno que vive en una sola red.

Todas las métricas se convierten a **rango percentil dentro de la corrida y dentro de cada red** (0 a 1): las vistas de YouTube y el score de Reddit no se comparan en bruto. Velocidad, outlier y aceleración solo existen para YouTube, Reddit e Instagram, y para TikTok la aceleración se mide por hashtag.

**2. Por qué funcionó (JEV + código)**

JEV clasifica gancho, formato y si menciona un lanzamiento. El código agrega la autoridad del autor (suscriptores en percentil) y el momento (horas desde la publicación). Claude redacta la explicación de una línea a partir de esos rasgos ya agregados.

**3. Ajuste a la audiencia (JEV)**

Persona fija en el `state`. Dimensiones: aplicabilidad práctica, nivel técnico adecuado y relevancia regional.

## Preguntas JEV

Una sola llamada por pieza con todas las preguntas (patrón fan-out). `state` = título + descripción + transcripción recortada en idioma original; instrucciones y criterios en inglés.

| Clave | Tipo | Para qué | Opciones o niveles |
| --- | --- | --- | --- |
| `es_ia` | noul | Filtro de relevancia al sector | Probabilidad de sí |
| `tema` | choice | Agrupar por tema | Los 15–20 temas propuestos en el paso 4, más "otro" (límite de JEV: 255 opciones) |
| `gancho` | choice | Por qué funcionó | Pregunta, dato sorprendente, contraste, promesa, historia, polémica |
| `formato` | choice | Por qué funcionó | Tutorial, opinión, noticia, caso, demo, lista |
| `menciona_lanzamiento` | noul | Momento | ¿El texto menciona un lanzamiento, producto o anuncio concreto? |
| `aplicabilidad` | score | Ajuste a audiencia | 0 = teoría pura … 4 = aplicable mañana en una empresa |
| `nivel_tecnico` | score | Ajuste a audiencia | 0 = solo ingenieros … 4 = ideal para ejecutivos |
| `relevancia_latam` | score | Ajuste a audiencia | 0 = irrelevante … 4 = específico de la región |

**Score compuesto (código, pesos en la configuración)**

Por pieza, solo si `es_ia ≥ 0.6`:

```
ajuste      = media(aplicabilidad, nivel_tecnico, relevancia_latam) / 4
crecimiento = 0.5 · pct_red(velocidad) + 0.5 · pct_red(outlier)      # solo piezas con métricas
pieza       = 0.5 · crecimiento + 0.5 · ajuste                       # con métricas
pieza       = ajuste                                                 # LinkedIn, TikTok por búsqueda
```

Por tema:

```
fuerza      = media de las 3 mejores piezas con métricas del tema
aceleracion = pct(aceleración media de sus piezas y de sus hashtags de TikTok)
temprano    = aceleracion · (1 − pct(volumen total del tema))
multired    = redes donde aparece el tema / 5
frescura    = 1 − saturación
tema        = 0.35 · fuerza + 0.20 · aceleracion + 0.20 · temprano + 0.15 · multired + 0.10 · frescura
```

Las piezas sin métricas no inflan la fuerza de un tema, pero sí cuentan para multired, saturación y para elegir las ideas de adaptación.

**Etapa de cada tema (reglas en código)**

| Etapa | Regla |
| --- | --- |
| Emergente | Aceleración alta, volumen bajo, pocos canales |
| Creciendo | Aceleración alta, volumen medio o alto |
| Pico | Aceleración cercana a cero, volumen alto |
| Saturado | Muchos canales y aceleración negativa |

**Reglas de uso**

- Confianza: `choice` y `score` traen `confidence`; para `noul` se calcula `|2p − 1|`. Debajo de 0,6 la pieza sale del ranking y se cuenta como "baja confianza" en el panel. Opcional si sobra tiempo: revisión de esas piezas con Claude.
- Fijar `jev-1.13.0` en todas las llamadas. `jev-latest` pasará a `jev-1.14.0` alrededor del 21 de octubre, en pleno reto.
- Probar `jev-1.13.0` contra `jev-1.14.0` con las 40 piezas etiquetadas el día 0: 1.14 promete su mayor mejora en idiomas distintos del inglés. Se elige una versión y no se cambia.
- Opcional: puntuar las ideas de Claude con otra llamada JEV (ajuste a formato y a la voz de 30X). Cuesta fracciones de centavo; entra solo si el núcleo está listo.

## Validación

- Etiquetar a mano 40 piezas en español: `es_ia`, `tema`, `formato` y un "le sirve a la audiencia" de 0 a 4.
- Medir acierto de JEV por pregunta y calibrar los umbrales de `es_ia` y de confianza con esos datos.
- El número de acierto entra en el pitch, en el paso de transparencia.

## Costos por corrida

JEV: 0,042 USD por millón de tokens de entrada, salida gratis ([modelos TypeSafe](https://docs.typesafe.ai/models)). El costo dominante será Claude; ese número se mide el día 0 y la frase del cierre se ajusta al valor real.

| Paso | Volumen supuesto | Tokens estimados | Costo estimado |
| --- | --- | --- | --- |
| JEV: scoring de piezas | 300 piezas × \~2.000 tokens | \~600 mil entrada | \~0,025 USD |
| JEV: señales tempranas (opcional) | 200 ítems × \~1.500 tokens | \~300 mil entrada | \~0,013 USD |
| Claude: proponer temas | 500 títulos | \~25 mil entrada / \~2 mil salida | Medir con `usage` |
| Claude: explicar y redactar ideas | 10 temas + 3 ideas | \~60 mil entrada / \~10 mil salida | Medir con `usage` |
| YouTube Data API | \~20 búsquedas + lecturas | — | 0 USD dentro de la cuota |
| Reddit API e Instagram Graph API | Lecturas por subreddit, hashtag y cuenta | — | 0 USD dentro de sus límites |
| API de búsqueda web (LinkedIn, TikTok) | \~40 consultas | — | Según proveedor elegido; confirmar el día 0 |

El contador del panel suma el campo `usage` de cada respuesta de JEV y de Claude por el precio de cada modelo. Usar un modelo pequeño para proponer temas y uno mayor solo para redactar baja el total.

## Plan de trabajo

El calendario depende de si las reglas del reto permiten llegar con código o datos preparados. Se confirma antes de escribir una línea.

**Puerta 0 — antes del reto (17–20 oct)**

- Confirmar reglas del reto y criterios del jurado.
- API keys de TypeSafe (con créditos comprados: las cuentas nuevas ya no traen créditos gratis), YouTube, Claude y búsqueda web.
- **Pedir hoy los accesos con espera:** registrar la app de Reddit, crear la app de Meta y conectar una cuenta profesional de Instagram.
- Revisar qué muestra el Creative Center de TikTok sin login y sus términos de uso.
- Revisar límites de uso de TypeSafe en console.typesafe.ai/rate-limits.
- Si las reglas lo permiten: arrancar las capturas programadas de YouTube y Reddit, y etiquetar las 40 piezas (8 por red).

**Puerta 1 — día 1, mañana:** llamada real a JEV con las 40 piezas, comparación 1.13 contra 1.14, versión elegida. Capturas corriendo (si no empezaron antes).

**Puerta 2 — día 1, tarde:** pipeline YouTube + Reddit → SQLite → JEV → score → JSON de punta a punta, aunque sea feo.

**Puerta 3 — día 2, mañana:** conectores de Instagram, LinkedIn y TikTok con el mismo esquema de pieza; señal multired funcionando.

**Puerta 3b — día 2, tarde:** temas dinámicos con Claude, explicaciones e ideas, etapas, panel con pesos ajustables, cobertura por red y contador de costo.

**Puerta 4 — día 3, mañana:** corrida completa guardada de IA y de fitness, ensayo del pitch dos veces con cronómetro.

Si una puerta no se cruza, el paso siguiente arranca con el plan B de la tabla de riesgos en vez de esperar. El reparto por persona se define cuando confirmemos el equipo.

## Demo y pitch

La demo muestra la corrida guardada como base y lanza una corrida en vivo encima; si la corrida en vivo falla, la guardada ya está en pantalla. Guion de 5 minutos:

1. **El dolor (30 s):** cuánto paga hoy 30X por datos que no dicen por qué algo funciona. La cifra se confirma con 30X antes de usarla.
2. **La pregunta (15 s):** se escribe en pantalla la pregunta del entregable y se lanza la corrida.
3. **El top 10 (90 s):** cada tema con etapa (emergente, creciendo, pico, saturado), en qué redes aparece, el porqué en una línea y la pieza más temprana del grupo.
4. **La adaptación (60 s):** para el tema número 1, tres ideas de carrusel o reel.
5. **Transparencia (45 s):** se mueve un peso y el ranking cambia; se muestra la confianza de JEV y el acierto medido en las 40 piezas.
6. **Generaliza (30 s):** se abre la corrida de fitness con la misma interfaz y el archivo de configuración al lado.
7. **El cierre (30 s):** contador de costo real de la corrida y roadmap: métricas de LinkedIn y TikTok cuando haya acceso oficial.

## Riesgos y preguntas abiertas

| Riesgo | Impacto | Plan B |
| --- | --- | --- |
| Las reglas no permiten código previo | Se pierde el trabajo del 18 al 20 | Usar esos días solo para keys, etiquetado y diseño; recortar ideas puntuadas por JEV |
| Acceso a Reddit no aprobado a tiempo | Reddit sin métricas | Feeds RSS públicos de los subreddits: presencia y ajuste, sin crecimiento |
| App de Meta o cuenta profesional de Instagram no lista | Instagram sin datos | Búsqueda web `site:instagram.com` y links de la comunidad: presencia y ajuste |
| Creative Center de TikTok exige login | Sin ranking de hashtags | El equipo copia a mano el top de hashtags por país una vez al día (comunidad como sensor) |
| LinkedIn sin métricas | El jurado pregunta "¿y el engagement?" | Mostrarlo de frente en la matriz de señales: LinkedIn aporta presencia, saturación y ajuste |
| Cinco conectores en 3 días | No llegar al panel | Orden de integración fijo; un conector que no esté listo el día 2 a mediodía se apaga en la configuración |
| Pocas capturas antes de la demo | Aceleración ruidosa | Ponderar más velocidad y outlier; mostrar la aceleración como "con N capturas" |
| JEV menos preciso en español | Clasificaciones ruidosas | Instrucciones en inglés, umbral de confianza, elegir 1.13 o 1.14 con datos |
| `jev-latest` cambia durante el reto | Umbrales que dejan de valer | Versión fija en todas las llamadas |
| Límites de uso de TypeSafe no publicados | La corrida se corta | 8 llamadas en paralelo con reintentos; corrida guardada como respaldo |
| Cuota de YouTube agotada en desarrollo | Sin datos nuevos el día de la demo | Caché de toda respuesta desde la primera corrida |
| Costo de Claude mayor al esperado | El argumento de "centavos" se debilita | Modelo pequeño para temas; medir el día 0 y ajustar la frase |
| Temas propuestos por Claude inconsistentes entre corridas | El ranking cambia sin razón | Pasar los temas de la corrida anterior como pista; JEV asigna, Claude solo nombra |

**Preguntas abiertas**

- [ ] ¿Las reglas del reto permiten llegar con código o datos preparados?
- [ ] ¿Cuáles son los criterios de evaluación del jurado?
- [ ] ¿Cuántas personas tiene el equipo y qué roles?
- [ ] ¿Las API keys de TypeSafe (con créditos), YouTube, Claude y búsqueda web están listas antes del 21?
- [ ] ¿Qué cuenta profesional de Instagram usamos para la Graph API: Optimo, la tuya o la de 30X?
- [ ] ¿La app de Reddit quedó aprobada?
- [ ] ¿Qué subreddits, hashtags y cuentas semilla sigue hoy 30X?
- [ ] ¿Cuánto paga hoy 30X por datos de tendencias? (para el paso 1 del pitch)
