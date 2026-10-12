#!/usr/bin/env bash
# Lanza en paralelo los clientes de un escenario de la Tabla 1 del enunciado · VM1.
#
# Uso:   ./vm1_escenario.sh <3|5|8> [duracion_min=3] [modo=fija]
# Ej.:   ./vm1_escenario.sh 3
#        ./vm1_escenario.sh 8 3 cerrado
#
# Escenarios (Entrega 1: solo consulta y reserva):
#   3 clientes: C1 y C2 solo consultan; C3 consulta y reserva (50/50).
#   5 clientes: C1-C3 solo consultan; C4 y C5 reservan.
#   8 clientes: C1-C4 solo consultan; C5-C8 reservan.
# En la Entrega 2 los que no consultan harán mitad reservas y mitad modificaciones.
#
# La IP del GT se toma de SRB_IP_VM2 (ver config.py).

set -e

N="$1"
DURACION="${2:-3}"
MODO="${3:-fija}"
RPM=20

if [[ "$N" != "3" && "$N" != "5" && "$N" != "8" ]]; then
  echo "Uso: $0 <3|5|8> [duracion_min=3] [modo=fija|cerrado]"
  exit 1
fi

cd "$(dirname "$0")"

# Cada corrida guarda sus CSV en su propia carpeta
export SRB_DIR_RESULTADOS="resultados/esc${N}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SRB_DIR_RESULTADOS"
echo "Escenario de $N clientes · $DURACION min · modo $MODO · resultados en $SRB_DIR_RESULTADOS"

case "$N" in
  3) SOLO_CONSULTA=2 ;;
  5) SOLO_CONSULTA=3 ;;
  8) SOLO_CONSULTA=4 ;;
esac

for i in $(seq 1 "$N"); do
  if (( i <= SOLO_CONSULTA )); then
    MEZCLA="--pct-consulta 100 --pct-reserva 0"
  elif [[ "$N" == "3" ]]; then
    MEZCLA="--pct-consulta 50 --pct-reserva 50"
  else
    MEZCLA="--pct-consulta 0 --pct-reserva 100"
  fi
  python3 cliente.py --id "C$i" --rpm "$RPM" --modo "$MODO" --duracion "$DURACION" $MEZCLA &
done

wait
echo "Escenario de $N clientes terminado. Resultados en $SRB_DIR_RESULTADOS"
