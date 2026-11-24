#!/usr/bin/env bash
# VM2 (y VM3): deja vacíos gt_metricas.csv y gt_eventos.csv antes de cada corrida, SIN borrarlos.
# El GT mantiene esos archivos abiertos mientras corre: si se borran con rm, sigue escribiendo en un
# archivo que ya no existe y la corrida queda sin datos del GT. Aquí se vacían en el mismo archivo y se
# les pone el encabezado, así el GT en marcha sigue escribiendo a continuación.
# Uso: ./reiniciar_metricas_gt.sh
cd "$(dirname "$0")" || exit 1
mkdir -p resultados
echo "hora,tipo,tiempo_s" > resultados/gt_metricas.csv
echo "hora,evento,detalle" > resultados/gt_eventos.csv
echo "gt_metricas.csv y gt_eventos.csv reiniciados en $(pwd)/resultados"
