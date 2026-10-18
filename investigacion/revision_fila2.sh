#!/usr/bin/env bash
# Segunda fila de la revision (cambio 4 del plan): lo que falta, ordenado por memoria.
#   1. en paralelo (livianos): rasgos 2025 de Filadelfia (R3) + R5 de Baton Rouge y Tempe
#   2. solo: rutas de R3 en Filadelfia (8 procesos de ~2 GB)
#   3. solo: R5 en Filadelfia, sin repetir su control (ya paso: resultados/revision/r5_control_filadelfia.txt)
#   bash investigacion/revision_fila2.sh <carpeta de registros>
cd "$(dirname "$0")/.." || exit 1
REG="$1"
PY=".venv/Scripts/python.exe"
export PYTHONIOENCODING=utf-8
mkdir -p "$REG"
paso() {
    local nombre="$1"; shift
    echo "$(date '+%H:%M') inicio $nombre" >> "$REG/fila2.log"
    "$@" > "$REG/$nombre.log" 2>&1
    local codigo=$?
    echo "$(date '+%H:%M') fin $nombre (codigo $codigo)" >> "$REG/fila2.log"
    return $codigo
}
paso r3_construir_filadelfia $PY investigacion/revision_rasgos_2025.py construir filadelfia &
P1=$!
paso r5_br_tempe $PY investigacion/revision_datos.py r5 baton_rouge tempe &
P2=$!
wait $P1; C1=$?
wait $P2
[ $C1 -eq 0 ] && paso r3_evaluar_filadelfia $PY investigacion/revision_rasgos_2025.py evaluar filadelfia
paso r5_filadelfia $PY investigacion/revision_datos.py r5 filadelfia --sin-control filadelfia
echo "$(date '+%H:%M') FILA 2 TERMINADA" >> "$REG/fila2.log"
