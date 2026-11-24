#!/usr/bin/env bash
# Registra el uso de CPU y memoria de la máquina con vmstat mientras corre una prueba.
# Uso: ./monitor_recursos.sh <archivo_salida> [intervalo_s=1]     (Ctrl+C para terminar)
# Columnas útiles: us/sy (CPU de usuario y sistema), id (CPU libre), wa (espera de E/S), free (memoria libre).
ARCHIVO="${1:?indique el archivo de salida}"
INTERVALO="${2:-1}"
echo "vmstat cada ${INTERVALO} s -> ${ARCHIVO}"
vmstat -t -n "$INTERVALO" | tee "$ARCHIVO"
