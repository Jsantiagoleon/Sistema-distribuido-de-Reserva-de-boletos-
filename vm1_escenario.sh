#!/usr/bin/env bash
# Lanza en paralelo los clientes de un escenario · VM1
# Uso: ./vm1_escenario.sh <3|5|8> [duracion_min=3] [modo=fija|cerrado]
#   3: C1 y C2 consultan; C3 consulta y reserva (50/50)
#   5: C1-C3 consultan; C4 y C5 reservan
#   8: C1-C4 consultan; C5-C8 reservan

N="$1"
DURACION="${2:-3}"
MODO="${3:-fija}"

case "$N" in
  3) SOLO_CONSULTA=2 ;;
  5) SOLO_CONSULTA=3 ;;
  8) SOLO_CONSULTA=4 ;;
  *) echo "Uso: $0 <3|5|8> [duracion_min=3] [modo=fija|cerrado]"; exit 1 ;;
esac

cd "$(dirname "$0")"
export SRB_DIR_RESULTADOS="resultados/esc${N}_$(date +%Y%m%d_%H%M%S)"

for i in $(seq 1 "$N"); do
  if (( i <= SOLO_CONSULTA )); then
    MEZCLA="--pct-consulta 100 --pct-reserva 0"
  elif [[ "$N" == "3" ]]; then
    MEZCLA="--pct-consulta 50 --pct-reserva 50"
  else
    MEZCLA="--pct-consulta 0 --pct-reserva 100"
  fi
  python3 cliente.py --id "C$i" --rpm 20 --modo "$MODO" --duracion "$DURACION" $MEZCLA &
done

wait
echo "Escenario de $N clientes terminado. Resultados en $SRB_DIR_RESULTADOS"
