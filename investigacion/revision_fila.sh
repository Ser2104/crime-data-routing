#!/usr/bin/env bash
# Fila de calculos de la revision (investigacion/analisis_revision.md), uno tras otro para
# no agotar la memoria. Cada paso deja su registro en $REG/<paso>.log. Si un paso falla, los
# que dependen de el no corren; los demas siguen.
#   bash investigacion/revision_fila.sh <carpeta de registros> [archivo que esperar]
cd "$(dirname "$0")/.." || exit 1
REG="$1"
ESPERAR="$2"
PY=".venv/Scripts/python.exe"
export PYTHONIOENCODING=utf-8
mkdir -p "$REG"

if [ -n "$ESPERAR" ]; then   # esperar a que termine el trabajo anterior (R1 y R2)
    until grep -q "^codigo" "$ESPERAR" 2>/dev/null; do sleep 60; done
fi

paso() {   # paso <nombre> <comando...>
    local nombre="$1"; shift
    echo "$(date '+%H:%M') inicio $nombre" >> "$REG/fila.log"
    "$@" > "$REG/$nombre.log" 2>&1
    local codigo=$?
    echo "$(date '+%H:%M') fin $nombre (codigo $codigo)" >> "$REG/fila.log"
    return $codigo
}

paso r7 $PY investigacion/revision_rutas.py r7
paso r8 $PY investigacion/revision_rutas.py r8
paso r9 $PY investigacion/revision_rutas.py r9
paso r10_ensayo $PY investigacion/revision_g16.py ensayo && paso r10 $PY investigacion/revision_g16.py examen
paso r4 $PY investigacion/revision_datos.py r4
paso r6 $PY investigacion/revision_datos.py r6
paso r5 $PY investigacion/revision_datos.py r5
paso r3_validar $PY investigacion/revision_rasgos_2025.py validar \
    && paso r3_construir $PY investigacion/revision_rasgos_2025.py construir \
    && paso r3_evaluar $PY investigacion/revision_rasgos_2025.py evaluar
echo "$(date '+%H:%M') FILA TERMINADA" >> "$REG/fila.log"
