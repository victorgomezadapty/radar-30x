# Radar 30X with JEV

**Try it:** https://radar-30x-three.vercel.app

It answers in one run, in 1 to 3 minutes, and for about 5 cents:

> **What are the 10 topics growing the most this week, why they work, and how 30X adapts them for leaders in Latin America?**

It works for AI (the main demo), fitness, or **any open topic** the user writes.

## What it does

1. **Detects early.** It collects public pieces from YouTube, Reddit, Instagram, LinkedIn, TikTok, and Hacker News, and measures velocity, acceleration (with snapshots every 3 hours), the *outlier ratio* versus the channel, saturation, and how many networks each topic appears on.
2. **Explains why it works.** JEV classifies each piece (topic, hook, format, whether it mentions a launch) and the radar calculates which hook is growing the most, on which network each topic originated, and how it jumped between networks.
3. **Filters by audience.** JEV scores audience fit (applicability, technical level, relevance for LatAm) and the code combines everything into a score with visible and adjustable weights.
4. **Adapts and anticipates.** It proposes three ready-to-copy pieces (carousel, reel, and LinkedIn post) and a list of **what is coming**: topics that are not yet a trend, but the signals point to them becoming one.

## How the work is divided

| Who | What it does | Why |
| --- | --- | --- |
| **Code** | Collects, measures, and **decides the ranking** | Reproducible and auditable: the AI does not decide the order |
| **JEV** (TypeSafe, `jev-1.13.0`) | Classifies each piece with 8 typed questions in a single call (fan-out); scores ideas and predictions | Structured responses with probability and confidence, for fractions of a cent |
| **DeepSeek** | Names the topics of the run, writes the why and the ideas, and creates the configuration for an open topic | It only writes; it does not touch the ranking |
| **Tavily** | Web search for public posts on LinkedIn, TikTok, and Instagram | The URLs come from the search; no model invents them |

Each low-confidence response from JEV is excluded from the ranking. Topics with fewer than 3 pieces remain as an early signal and do not enter the top 10.

## Real cost per run

Measured with the `usage` field of each response, not estimated. A typical AI run (about 300 pieces):

| Step | Cost |
| --- | --- |
| JEV: classify about 300 pieces | ~0.025 USD |
| DeepSeek: topics, writing, and predictions | ~0.02 USD |
| YouTube, Reddit (RSS), Hacker News, and Tavily | 0 USD (free quotas) |
| **Total** | **~0.05 USD** |

The app shows the exact cost of each run, its breakdown, and the history.

## Architecture

```
Browser ──► Vercel (web/ + api/)
                 │  POST /api/correr  ──►  GitHub Actions (radar.yml)
                 │  GET  /api/estado  ◄──  steps of the run
                 │                           │  python -m radar recolectar / correr
                 │                           │  JEV + DeepSeek + Tavily + YouTube API
                 ◄── Vercel redeploys ◄─┘  commit of results (out/, web/datos.json)

Every 3 hours, GitHub Actions takes a new metrics snapshot to measure real acceleration.
```

- `radar/`: Python engine (connectors per network, JEV client, scoring, LLM, and local server).
- `api/`: Vercel functions that start the run and read its progress.
- `web/index.html`: the app (landing, run configuration, and results).
- `config/`: one YAML file per sector (keywords, persona, weights, and thresholds).
- `.github/workflows/radar.yml`: cloud execution and scheduled snapshots.

## Run it locally

```bash
uv venv .venv
uv pip install --python .venv -r requirements.txt
cp .env.example .env        # and fill in TYPESAFE_API_KEY, YOUTUBE_API_KEY, DEEPSEEK_API_KEY, TAVILY_API_KEY
.venv/Scripts/python -m radar probar     # checks each key
.venv/Scripts/python -m radar servir     # app at http://localhost:8765
```

From the terminal:

```bash
.venv/Scripts/python -m radar correr --sector ia_latam
.venv/Scripts/python -m radar sector-nuevo --sector libre_cafe --nicho "café de especialidad"
```

## Sources and rules

| Network | Via | Growth metrics |
| --- | --- | --- |
| YouTube | Data API v3 (official) | Yes: views, likes, and comments |
| Reddit | Public RSS (or official API with keys) | With the API, yes; with RSS, presence and fit |
| Instagram | Web search (or Graph API with a professional account) | With the Graph API, yes |
| LinkedIn | Web search of indexed posts | Presence and fit |
| TikTok | Web search + Creative Center hashtag ranking | Acceleration by hashtag |
| Hacker News | Algolia API | Yes: points |

Nothing is collected from behind a third-party login or by scraping that violates terms of use, and only data from public pieces is used, never from people. Keys live in `.env` (local) or in GitHub secrets; never in the repository.
