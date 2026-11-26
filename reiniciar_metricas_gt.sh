#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
mkdir -p resultados
echo "hora,tipo,tiempo_s" > resultados/gt_metricas.csv
echo "hora,evento,detalle" > resultados/gt_eventos.csv
echo "gt_metricas.csv y gt_eventos.csv reiniciados en $(pwd)/resultados"
