#!/usr/bin/env bash
ARCHIVO="${1:?indique el archivo de salida}"
INTERVALO="${2:-1}"
echo "vmstat cada ${INTERVALO} s -> ${ARCHIVO}"
vmstat -t -n "$INTERVALO" | tee "$ARCHIVO"
