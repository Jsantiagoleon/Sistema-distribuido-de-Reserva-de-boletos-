"""
Calcula las métricas de un escenario a partir de los CSV de resultados.

Tiempo de respuesta (promedio y desviación estándar) por cliente y total,
  con los archivos resultados_<id>.csv de los clientes (VM1).
TPM: solicitudes completadas por minuto en el Gestor, con gt_metricas.csv (VM2).

"""

import csv
import glob
import os
import statistics
import sys


def tiempo_respuesta(carpeta):
    archivos = sorted(glob.glob(os.path.join(carpeta, "resultados_*.csv")))
    if not archivos:
        print(f"No hay archivos resultados_*.csv en {carpeta}")
        return

    print(f"{'Cliente':<9}{'Solic.':>7}{'Sin resp.':>10}{'Promedio (s)':>14}{'Desv. est. (s)':>16}")
    print("-" * 56)
    todos = []
    for ruta in archivos:
        with open(ruta, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        tiempos = [float(r["tiempo_ms"]) / 1000 for r in filas if r["estado"] != "sin_respuesta"]
        sin_respuesta = len(filas) - len(tiempos)
        todos += tiempos
        cliente = os.path.basename(ruta)[len("resultados_"):-len(".csv")]
        print(f"{cliente:<9}{len(filas):>7}{sin_respuesta:>10}"
              f"{promedio(tiempos):>14}{desviacion(tiempos):>16}")
    print("-" * 56)
    print(f"{'Total':<9}{len(todos):>17}{promedio(todos):>14}{desviacion(todos):>16}")


def tpm(ruta):
    if not os.path.exists(ruta):
        print(f"No existe {ruta}")
        return

    with open(ruta, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    completadas = [r for r in filas if r["tipo"] != "error"]
    if not completadas:
        print("No hay solicitudes completadas")
        return

    horas = [float(r["hora"]) for r in completadas]
    minutos = max((max(horas) - min(horas)) / 60, 1 / 60)
    print(f"Solicitudes completadas: {len(completadas)}  (errores: {len(filas) - len(completadas)})")
    for tipo in sorted({r["tipo"] for r in completadas}):
        print(f"  {tipo}: {sum(1 for r in completadas if r['tipo'] == tipo)}")
    print(f"Duración: {minutos:.2f} min")
    print(f"TPM: {len(completadas) / minutos:.1f} solicitudes por minuto")


def promedio(valores):
    return f"{statistics.mean(valores):.4f}" if valores else "-"


def desviacion(valores):
    return f"{statistics.stdev(valores):.4f}" if len(valores) > 1 else "-"


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("clientes", "gestor"):
        print(__doc__)
    elif sys.argv[1] == "clientes":
        tiempo_respuesta(sys.argv[2])
    else:
        tpm(sys.argv[2])