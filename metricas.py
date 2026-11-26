import argparse
import csv
import glob
import json
import math
import os
import statistics
import sys

TIPOS = ["consulta", "reserva", "modificacion"]
PROCESADAS = ("EXITO", "RECHAZADO")


def leer_corrida(carpeta, descartar=15.0):
    filas = []
    for ruta in sorted(glob.glob(os.path.join(carpeta, "resultados_*.csv"))):
        with open(ruta, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r["hora"] = float(r["hora"])
                r["tiempo_ms"] = float(r["tiempo_ms"])
                r["intentos"] = int(r.get("intentos") or 1)
                r["inicio"] = r["hora"] - r["tiempo_ms"] / 1000
                r["cliente"] = os.path.basename(ruta)[len("resultados_"):-4]
                filas.append(r)
    if not filas:
        raise SystemExit(f"{carpeta}: no hay archivos resultados_*.csv")

    solicitudes = [r for r in filas if r["tipo"] not in ("notificacion",)]
    t0 = min(r["inicio"] for r in solicitudes)
    inicio, fin = t0 + descartar, max(r["hora"] for r in solicitudes)
    if fin <= inicio:
        raise SystemExit(f"{carpeta}: la corrida dura menos de {descartar:.0f} s; no hay datos para medir")
    en_ventana = [r for r in filas if inicio <= r["inicio"] <= fin]

    gt, ventana_gt = [], (None, None)
    ruta_gt = os.path.join(carpeta, "gt_metricas.csv")
    if os.path.exists(ruta_gt):
        with open(ruta_gt, encoding="utf-8") as f:
            todas = list(csv.DictReader(f))
        if todas:
            horas = [float(r["hora"]) for r in todas]
            ventana_gt = (min(horas) + descartar, max(horas))
            gt = [r for r in todas if ventana_gt[0] <= float(r["hora"]) <= ventana_gt[1]]
    meta = {}
    if os.path.exists(os.path.join(carpeta, "meta.json")):
        with open(os.path.join(carpeta, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
    return {"filas": en_ventana, "gt": gt, "inicio": inicio, "fin": fin, "meta": meta,
            "ventana_gt": ventana_gt, "tiene_gt": os.path.exists(ruta_gt) and bool(gt)}


def percentil(valores, p):
    if not valores:
        return float("nan")
    orden = sorted(valores)
    k = (len(orden) - 1) * p / 100
    return orden[int(math.floor(k))] + (orden[int(math.ceil(k))] - orden[int(math.floor(k))]) * (k - math.floor(k))


def desviacion(valores):
    return statistics.stdev(valores) if len(valores) > 1 else 0.0


def analizar(corrida):
    minutos = (corrida["fin"] - corrida["inicio"]) / 60
    g0, g1 = corrida["ventana_gt"]
    minutos_gt = (g1 - g0) / 60 if g0 is not None and g1 > g0 else float("nan")
    salida = {}
    for tipo in TIPOS + ["cancelacion", "notificacion"]:
        filas = [r for r in corrida["filas"] if r["tipo"] == tipo]
        if not filas:
            continue
        if tipo == "cancelacion":
            buenas = [r for r in filas if r["estado"] == "ACEPTADA"]
        elif tipo == "notificacion":
            buenas = [r for r in filas if r["estado"] in PROCESADAS]
        else:
            buenas = [r for r in filas if r["estado"] in PROCESADAS]
        tiempos = [r["tiempo_ms"] for r in buenas]
        t_gt = [float(g["tiempo_s"]) * 1000 for g in corrida["gt"] if g["tipo"] == tipo]
        media = statistics.fmean(tiempos) if tiempos else float("nan")
        media_gt = statistics.fmean(t_gt) if t_gt else float("nan")
        salida[tipo] = {
            "solicitudes": len(filas),
            "procesadas": len(buenas),
            "errores": sum(1 for r in filas if r["estado"] == "ERROR"),
            "sin_respuesta": sum(1 for r in filas if r["estado"] == "sin_respuesta"),
            "reintentos": sum(1 for r in filas if r["intentos"] > 1),
            "tiempos": tiempos,
            "media_ms": media,
            "desv_ms": desviacion(tiempos),
            "p95_ms": percentil(tiempos, 95),
            "gt_media_ms": media_gt,
            "red_colas_ms": media - media_gt,
            "tpm_clientes": len(buenas) / minutos,
            "tpm_gt": (len(t_gt) / minutos_gt if corrida["tiene_gt"] else float("nan")),
        }
    salida["_minutos"] = minutos
    salida["_minutos_gt"] = minutos_gt
    return salida


def imprimir_corrida(carpeta, corrida, stats):
    meta = corrida["meta"]
    titulo = (f"{meta.get('arquitectura', '?')} · {meta.get('clientes', '?')} clientes · "
              f"repetición {meta.get('repeticion', '?')}" if meta else carpeta)
    print(f"\n{titulo}  ({stats['_minutos']:.2f} min medidos tras descartar el arranque)")
    print(f"{'Operación':<14}{'Solic.':>8}{'Proc.':>7}{'Err.':>6}{'SinR.':>7}{'Reint.':>8}"
          f"{'Media ms':>10}{'Desv ms':>9}{'P95 ms':>9}{'GT ms':>8}{'Red ms':>8}{'TPM GT':>9}{'TPM cli':>9}")
    print("-" * 118)
    for tipo in TIPOS + ["cancelacion", "notificacion"]:
        s = stats.get(tipo)
        if s:
            print(f"{tipo:<14}{s['solicitudes']:>8}{s['procesadas']:>7}{s['errores']:>6}"
                  f"{s['sin_respuesta']:>7}{s['reintentos']:>8}{s['media_ms']:>10.1f}{s['desv_ms']:>9.1f}"
                  f"{s['p95_ms']:>9.1f}{s['gt_media_ms']:>8.1f}{s['red_colas_ms']:>8.1f}"
                  f"{s['tpm_gt']:>9.1f}{s['tpm_clientes']:>9.1f}")
    if not corrida["tiene_gt"]:
        print("(sin gt_metricas.csv utilizable en la carpeta: las columnas del GT quedan en nan; copie el "
              "archivo desde la VM2)")
    elif abs(stats["_minutos_gt"] - stats["_minutos"]) > 0.2 * stats["_minutos"]:
        print(f"AVISO: la ventana del GT ({stats['_minutos_gt']:.1f} min) difiere de la de los clientes "
              f"({stats['_minutos']:.1f} min). Probablemente gt_metricas.csv trae más de una corrida: "
              "bórrelo en la VM2 antes de cada corrida.")


def agregar(carpetas, descartar):
    grupos = {}
    for carpeta in carpetas:
        corrida = leer_corrida(carpeta, descartar)
        meta = corrida["meta"]
        clave = (meta.get("arquitectura", "?"), int(meta.get("clientes", 0)), meta.get("tipo", "escenario"))
        grupos.setdefault(clave, []).append(analizar(corrida))

    filas = []
    for (arq, n, kind), corridas in sorted(grupos.items()):
        for tipo in TIPOS + ["cancelacion", "notificacion"]:
            con_tipo = [c[tipo] for c in corridas if tipo in c]
            if not con_tipo:
                continue
            tiempos = [t for s in con_tipo for t in s["tiempos"]]
            medias = [s["media_ms"] for s in con_tipo if not math.isnan(s["media_ms"])]
            gt_ms = [s["gt_media_ms"] for s in con_tipo if not math.isnan(s["gt_media_ms"])]
            red_ms = [s["red_colas_ms"] for s in con_tipo if not math.isnan(s["red_colas_ms"])]
            tpm_gt = [s["tpm_gt"] for s in con_tipo if not math.isnan(s["tpm_gt"])]
            tpm_cl = [s["tpm_clientes"] for s in con_tipo]
            filas.append({
                "arquitectura": arq, "clientes": n, "prueba": kind, "tipo": tipo,
                "corridas": len(con_tipo), "muestras": len(tiempos),
                "media_ms": statistics.fmean(medias) if medias else float("nan"),
                "desv_ms": desviacion(medias) if len(medias) > 1 else desviacion(tiempos),
                "p95_ms": percentil(tiempos, 95),
                "gt_media_ms": statistics.fmean(gt_ms) if gt_ms else float("nan"),
                "red_colas_ms": statistics.fmean(red_ms) if red_ms else float("nan"),
                "tpm_gt": statistics.fmean(tpm_gt) if tpm_gt else float("nan"),
                "tpm_gt_desv": desviacion(tpm_gt) if tpm_gt else float("nan"),
                "tpm_clientes": statistics.fmean(tpm_cl), "tpm_clientes_desv": desviacion(tpm_cl),
                "errores": sum(s["errores"] for s in con_tipo),
                "sin_respuesta": sum(s["sin_respuesta"] for s in con_tipo),
                "reintentos": sum(s["reintentos"] for s in con_tipo),
            })
    return filas


def imprimir_resumen(filas):
    print(f"{'Arquitectura':<13}{'Prueba':<11}{'Cli.':>5} {'Operación':<13}{'Corr.':>6}{'Media ms':>10}"
          f"{'Desv ms':>9}{'GT ms':>8}{'Red ms':>8}{'TPM GT':>9}{'±':>6}{'TPM cli':>9}{'Err.':>6}{'SinR.':>7}")
    print("-" * 120)
    for f in filas:
        print(f"{f['arquitectura']:<13}{f['prueba']:<11}{f['clientes']:>5} {f['tipo']:<13}{f['corridas']:>6}"
              f"{f['media_ms']:>10.1f}{f['desv_ms']:>9.1f}{f['gt_media_ms']:>8.1f}{f['red_colas_ms']:>8.1f}"
              f"{f['tpm_gt']:>9.1f}{f['tpm_gt_desv']:>6.1f}{f['tpm_clientes']:>9.1f}{f['errores']:>6}"
              f"{f['sin_respuesta']:>7}")


def tpm_total(filas):
    tot = {}
    for f in filas:
        if f["tipo"] in TIPOS:
            v = f["tpm_gt"] if not math.isnan(f["tpm_gt"]) else f["tpm_clientes"]
            tot[(f["arquitectura"], f["clientes"])] = tot.get((f["arquitectura"], f["clientes"]), 0.0) + v
    return tot


def saturacion(filas, umbral=5.0):
    tot = tpm_total([f for f in filas if f["prueba"] == "capacidad"])
    resultado = {}
    for arq in sorted({a for a, _ in tot}):
        pts = sorted((n, v) for (a, n), v in tot.items() if a == arq)
        resultado[arq] = None
        for (n0, v0), (n1, v1) in zip(pts, pts[1:]):
            aumento = (v1 - v0) / v0 * 100 if v0 > 0 else float("inf")
            if aumento < umbral:
                resultado[arq] = (n0, v0, aumento)
                break
    return resultado


def imprimir_saturacion(filas, umbral):
    sat = saturacion(filas, umbral)
    if not sat:
        return
    print(f"\nSaturación (P2, criterio: el siguiente cliente sube el TPM menos de {umbral:g} %):")
    for arq, r in sat.items():
        if r is None:
            print(f"  {arq}: el TPM siguió creciendo en todo el rango; aumente el número de clientes")
        else:
            print(f"  {arq}: capacidad alcanzada con {r[0]} clientes (TPM ≈ {r[1]:.0f}); "
                  f"el siguiente subió {r[2]:.1f} %")


def guardar_csv(filas, ruta):
    if not filas:
        return
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"\nResumen guardado en {ruta}")


def expandir(patrones):
    carpetas = []
    for p in patrones:
        carpetas.extend(sorted(glob.glob(p)) or [p])
    return [c for c in carpetas if os.path.isdir(c)]


def main():
    parser = argparse.ArgumentParser(description="Métricas de rendimiento del SRB")
    sub = parser.add_subparsers(dest="orden", required=True)
    p1 = sub.add_parser("corrida", help="métricas de una corrida")
    p1.add_argument("carpeta")
    p2 = sub.add_parser("resumen", help="combina varias corridas (repeticiones) por arquitectura y clientes")
    p2.add_argument("carpetas", nargs="+")
    p2.add_argument("--csv", help="guarda el resumen en este archivo")
    p2.add_argument("--umbral", type=float, default=5.0,
                    help="P2: aumento mínimo de TPM (%%) para seguir considerando que no hay saturación")
    for p in (p1, p2):
        p.add_argument("--descartar", type=float, default=15.0, help="segundos iniciales que se descartan")
    args = parser.parse_args()

    if args.orden == "corrida":
        corrida = leer_corrida(args.carpeta, args.descartar)
        imprimir_corrida(args.carpeta, corrida, analizar(corrida))
    else:
        carpetas = expandir(args.carpetas)
        if not carpetas:
            sys.exit("No se encontraron carpetas de corridas")
        filas = agregar(carpetas, args.descartar)
        imprimir_resumen(filas)
        imprimir_saturacion(filas, args.umbral)
        if args.csv:
            guardar_csv(filas, args.csv)


if __name__ == "__main__":
    main()
