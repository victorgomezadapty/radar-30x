#!/bin/sh
# Ignored Build Step de Vercel (vercel.json).
# 0 = saltar el build. 1 = construir.
# Cualquier otro código hace fallar el despliegue, así que un commit ausente
# no puede dejar escapar el 128 de git ("fatal: bad object").
#
# Vercel clona con --depth=10. VERCEL_GIT_PREVIOUS_SHA es el último despliegue
# exitoso; cuando queda fuera de esa ventana, git diff muere en vez de
# comparar. En ese caso se construye. Si el commit está y web/, api/ y
# vercel.json no cambiaron (las capturas "Radar: captura de métricas" solo
# tocan data/radar.db), se salta.

prev="${VERCEL_GIT_PREVIOUS_SHA:-HEAD^}"

if ! git cat-file -e "${prev}^{commit}" 2>/dev/null; then
  exit 1
fi

git diff --quiet "$prev" HEAD -- web api vercel.json
status=$?
if [ "$status" -eq 0 ]; then
  exit 0
fi
exit 1
