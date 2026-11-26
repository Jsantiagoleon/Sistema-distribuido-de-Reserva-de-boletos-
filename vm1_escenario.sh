#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
IP_VM2="${SRB_IP_VM2:-10.43.100.247}"
IP_VM3="${SRB_IP_VM3:-10.43.99.241}"
PUERTO_GT=5557
FECHA="$(date +%Y%m%d_%H%M%S)"

uso() {
  echo "Uso:"
  echo "  ./vm1_escenario.sh <3|5|8> <base|escalable> [repeticion=1] [duracion_min=3]"
  echo "  ./vm1_escenario.sh capacidad <N> <base|escalable> [duracion_min=1]"
  exit 1
}

if [[ "$1" == "capacidad" ]]; then
  N="$2"; ARQ="$3"; DURACION="${4:-1}"; REP=1; TIPO="capacidad"; MODO="cerrado"
  [[ "$N" =~ ^[0-9]+$ && ( "$ARQ" == "base" || "$ARQ" == "escalable" ) ]] || uso
  CARPETA="resultados/${ARQ}_cap${N}_${FECHA}"
else
  N="$1"; ARQ="$2"; REP="${3:-1}"; DURACION="${4:-3}"; TIPO="escenario"; MODO="fija"
  case "$N" in 3) SOLO_CONSULTA=2 ;; 5) SOLO_CONSULTA=3 ;; 8) SOLO_CONSULTA=4 ;; *) uso ;; esac
  [[ "$ARQ" == "base" || "$ARQ" == "escalable" ]] || uso
  CARPETA="resultados/${ARQ}_esc${N}_r${REP}_${FECHA}"
fi

if [[ "$ARQ" == "base" ]]; then
  GT="${SRB_GT:-tcp://${IP_VM2}:${PUERTO_GT}}"
else
  GT="${SRB_GT:-tcp://${IP_VM2}:${PUERTO_GT},tcp://${IP_VM3}:${PUERTO_GT}}"
fi

mkdir -p "$CARPETA"
export SRB_DIR_RESULTADOS="$CARPETA"
cat > "$CARPETA/meta.json" <<META
{"arquitectura": "$ARQ", "clientes": $N, "repeticion": $REP, "tipo": "$TIPO", "modo": "$MODO",
 "duracion_min": $DURACION, "gt": "$GT", "fecha": "$FECHA"}
META

echo "== $TIPO · $N clientes · $ARQ · repetición $REP · ${DURACION} min · modo $MODO · GT $GT"
for i in $(seq 1 "$N"); do
  if [[ "$TIPO" == "capacidad" ]]; then
    MEZCLA="--pct-consulta 50 --pct-reserva 50"
  elif (( i <= SOLO_CONSULTA )); then
    MEZCLA="--pct-consulta 100 --pct-reserva 0"
  elif [[ "$N" == "3" ]]; then
    MEZCLA="--pct-consulta 50 --pct-reserva 50"
  else
    MEZCLA="--pct-consulta 0 --pct-reserva 50 --pct-modificacion 50"
  fi
  python3 cliente.py --id "C$i" --gt "$GT" --rpm 20 --modo "$MODO" --duracion "$DURACION" $MEZCLA &
done

wait
echo "Terminado. Resultados en $CARPETA"
echo "Copie ahora el gt_metricas.csv de la VM2:  scp <usuario>@${IP_VM2}:<ruta>/resultados/gt_metricas.csv $CARPETA/"
