"""
Gráficas del informe de rendimiento (PNG) a partir de los resúmenes de metricas.py y de vmstat.

    python3 graficas.py g1 resumen.csv        G1 · tiempo de respuesta por tipo vs clientes (P1)
    python3 graficas.py g2 resumen.csv        G2 · TPM total y por tipo vs clientes (P1)
    python3 graficas.py g3 vm1.txt vm2.txt vm3.txt
                                              G3 · CPU y memoria libre de cada VM en el tiempo (vmstat -t)
    python3 graficas.py g4 resumen_cap.csv [--umbral 5]
                                              G4 · capacidad: TPM vs clientes en modo cerrado (P2),
                                                   con el punto de saturación marcado
    python3 graficas.py g5 <carpeta_corrida> [--marca SEG]
                                              G5 · línea de tiempo de una prueba de falla (T1/T2)
    python3 graficas.py g6 resumen.csv        G6 · base vs escalable: latencia y TPM
Opciones: --salida carpeta (por defecto graficas/), --descartar segundos (solo g5, por defecto 0).

Colores: azul = arquitectura base, naranja = arquitectura escalable (par de la paleta categórica
validada). Barras de error = desviación estándar ENTRE repeticiones (ver metricas.py).
"""

import argparse
import csv
from datetime import datetime
import glob
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLOR = {"base": "#2a78d6", "escalable": "#eb6834"}
MARCA = {"base": "o", "escalable": "s"}
TIPO_COLOR = {"consulta": "#2a78d6", "reserva": "#eb6834", "modificacion": "#6250d6"}
TIPOS = ["consulta", "reserva", "modificacion"]
TEXTO, TEXTO2, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": REJILLA, "axes.labelcolor": TEXTO2, "xtick.color": TEXTO2,
    "ytick.color": TEXTO2, "text.color": TEXTO, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": REJILLA,
    "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def leer_resumen(ruta):
    with open(ruta, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    for f in filas:
        for k in ("clientes", "corridas", "muestras"):
            f[k] = int(f[k])
        for k in ("media_ms", "desv_ms", "p95_ms", "gt_media_ms", "red_colas_ms", "tpm_gt", "tpm_gt_desv",
                  "tpm_clientes", "tpm_clientes_desv"):
            f[k] = float(f.get(k) or "nan")      # los resúmenes viejos no traen gt_media_ms / red_colas_ms
    return filas


def serie(filas, arq, tipo, campo, campo_err=None):
    pts = sorted((f for f in filas if f["arquitectura"] == arq and f["tipo"] == tipo), key=lambda f: f["clientes"])
    x = [f["clientes"] for f in pts]
    y = [f[campo] for f in pts]
    e = [f[campo_err] if campo_err else 0 for f in pts]
    return x, y, e


def panel(ax, filas, tipo, campo, campo_err, titulo, ylabel):
    hay = False
    for arq in ("base", "escalable"):
        x, y, e = serie(filas, arq, tipo, campo, campo_err)
        if not x:
            continue
        hay = True
        e = [0 if math.isnan(v) else v for v in e]
        ax.errorbar(x, y, yerr=e, color=COLOR[arq], marker=MARCA[arq], markersize=7, linewidth=2,
                    capsize=3, markeredgecolor="white", markeredgewidth=1.2, label=arq)
        ax.annotate(arq, (x[-1], y[-1]), textcoords="offset points", xytext=(6, 0), va="center",
                    color=TEXTO2, fontsize=9)
    ax.set_title(titulo, loc="left")
    ax.set_xlabel("Clientes simultáneos")
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    ax.margins(x=0.15)
    xs = sorted({f["clientes"] for f in filas})
    ax.set_xticks(xs)
    return hay


def guardar(fig, salida, nombre):
    os.makedirs(salida, exist_ok=True)
    ruta = os.path.join(salida, nombre)
    fig.savefig(ruta, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Gráfica guardada en", ruta)


def tipos_presentes(filas, candidatos):
    return [t for t in candidatos if any(f["tipo"] == t for f in filas)]


def tpm_de(f):
    return f["tpm_gt"] if not math.isnan(f["tpm_gt"]) else f["tpm_clientes"]


def barras_por_arquitectura(filas, salida, nombre, titulo, ylabel, valor, error=None, apilado=False):
    """Un panel por arquitectura; eje X = clientes; una barra por tipo de operación (o apiladas)."""
    arqs = [a for a in ("base", "escalable") if any(f["arquitectura"] == a for f in filas)]
    tipos = tipos_presentes(filas, TIPOS)
    xs = sorted({f["clientes"] for f in filas})
    fig, axes = plt.subplots(1, len(arqs), figsize=(4.6 * len(arqs), 3.6), squeeze=False, sharey=True)
    ancho = 0.8 if apilado else 0.8 / len(tipos)
    for ax, arq in zip(axes[0], arqs):
        base = [0.0] * len(xs)
        for k, tipo in enumerate(tipos):
            vals, errs = [], []
            for n in xs:
                fila = next((f for f in filas if f["arquitectura"] == arq and f["tipo"] == tipo
                             and f["clientes"] == n), None)
                v = valor(fila) if fila else 0.0
                vals.append(0.0 if math.isnan(v) else v)
                e = fila[error] if (fila and error) else 0.0
                errs.append(0.0 if math.isnan(e) else e)
            pos = [i if apilado else i + (k - (len(tipos) - 1) / 2) * ancho for i in range(len(xs))]
            ax.bar(pos, vals, ancho * 0.92, bottom=base if apilado else None, color=TIPO_COLOR[tipo],
                   label=tipo, yerr=None if (apilado or not error) else errs, capsize=2,
                   error_kw={"ecolor": TEXTO2, "elinewidth": 1})
            if apilado:
                base = [b + v for b, v in zip(base, vals)]
        if apilado:
            for i, tot in enumerate(base):
                ax.annotate(f"{tot:.0f}", (i, tot), textcoords="offset points", xytext=(0, 3), ha="center",
                            fontsize=8, color=TEXTO2)
        ax.set_xticks(range(len(xs)))
        ax.set_xticklabels(xs)
        ax.set_title(f"{titulo} · {arq}", loc="left")
        ax.set_xlabel("Clientes simultáneos")
    axes[0][0].set_ylabel(ylabel)
    axes[0][0].set_ylim(bottom=0)
    axes[0][0].legend(frameon=False, loc="upper left", fontsize=8)
    fig.tight_layout()
    guardar(fig, salida, nombre)


def g1(filas, salida):
    barras_por_arquitectura(filas, salida, "g1_tiempo_de_respuesta.png", "Tiempo de respuesta",
                            "ms (media ± desv. entre repeticiones)", lambda f: f["media_ms"], "desv_ms")


def g2(filas, salida):
    barras_por_arquitectura(filas, salida, "g2_tpm.png", "TPM por tipo (suma = total)",
                            "Transacciones por minuto (medido en el GT)", tpm_de, apilado=True)


def leer_vmstat(ruta):
    """Lee la salida de `vmstat -t`: devuelve lista de (segundos desde la 1.ª muestra, %CPU usada, MiB libres).
    La primera fila de vmstat es el promedio desde el arranque de la máquina y se descarta."""
    columnas, filas = None, []
    with open(ruta, encoding="utf-8", errors="replace") as f:
        for linea in f:
            t = linea.split()
            if "free" in t and "id" in t:
                columnas = t
                continue
            if columnas is None or len(t) < 19 or not t[0].lstrip("-").isdigit():
                continue
            try:
                ts = datetime.strptime(f"{t[-2]} {t[-1]}", "%Y-%m-%d %H:%M:%S").timestamp()
                filas.append((ts, 100.0 - float(t[columnas.index("id")]),
                              float(t[columnas.index("free")]) / 1024))
            except (ValueError, IndexError):
                continue
    filas = filas[1:]
    return [(ts - filas[0][0], cpu, mem) for ts, cpu, mem in filas] if filas else []


def g3(archivos, salida):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8.6, 5.2), sharex=True)
    paleta = ["#2a78d6", "#eb6834", "#6250d6", "#2d9b6b"]
    for k, ruta in enumerate(archivos):
        datos = leer_vmstat(ruta)
        if not datos:
            print("AVISO: sin datos de vmstat en", ruta)
            continue
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        a1.plot([d[0] for d in datos], [d[1] for d in datos], color=paleta[k % 4], linewidth=1.6, label=nombre)
        a2.plot([d[0] for d in datos], [d[2] for d in datos], color=paleta[k % 4], linewidth=1.6, label=nombre)
    a1.set_title("Uso de CPU (100 − id) de cada VM", loc="left")
    a1.set_ylabel("% CPU")
    a1.set_ylim(0, 100)
    a1.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
    a2.set_title("Memoria libre de cada VM", loc="left")
    a2.set_ylabel("MiB libres")
    a2.set_xlabel("Segundos desde la primera muestra")
    a2.set_ylim(bottom=0)
    fig.tight_layout()
    guardar(fig, salida, "g3_recursos.png")


def g4(filas, salida, umbral=5.0):
    """Capacidad (modo cerrado): TPM total y tiempo de respuesta medio vs clientes, con la saturación marcada."""
    from metricas import saturacion
    tot = {}
    for f in filas:
        if f["tipo"] in TIPOS:
            tot[(f["arquitectura"], f["clientes"])] = tot.get((f["arquitectura"], f["clientes"]), 0.0) + tpm_de(f)
    sat = saturacion([dict(f, prueba="capacidad") for f in filas], umbral)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.6))
    for arq in ("base", "escalable"):
        pts = sorted((n, v) for (a, n), v in tot.items() if a == arq)
        if pts:
            a1.plot([p[0] for p in pts], [p[1] for p in pts], color=COLOR[arq], marker=MARCA[arq], markersize=7,
                    linewidth=2, markeredgecolor="white", markeredgewidth=1.2, label=arq)
        if sat.get(arq):
            n, v, _ = sat[arq]
            a1.axvline(n, color=COLOR[arq], linestyle=":", linewidth=1.2)
            a1.annotate(f"saturación {arq}: {n} clientes", (n, 0), rotation=90, va="bottom",
                        ha="right" if arq == "base" else "left", xytext=(-3 if arq == "base" else 3, 6),
                        textcoords="offset points", fontsize=8, color=COLOR[arq])
    a1.set_title("Capacidad: TPM total", loc="left")
    a1.set_xlabel("Clientes en modo cerrado")
    a1.set_ylabel("Transacciones por minuto")
    a1.set_ylim(bottom=0)
    a1.set_xticks(sorted({f["clientes"] for f in filas}))
    a1.legend(frameon=False, loc="upper right")
    panel(a2, filas, "consulta", "media_ms", "desv_ms", "Tiempo de respuesta · consulta", "ms (media ± desv. estándar)")
    fig.tight_layout()
    guardar(fig, salida, "g4_capacidad.png")


def g6(filas, salida):
    """Base vs escalable: latencia media (ponderada por muestras) y TPM total contra clientes."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.6))
    for arq in ("base", "escalable"):
        lat, tpm = {}, {}
        for f in filas:
            if f["arquitectura"] != arq or f["tipo"] not in TIPOS:
                continue
            w = lat.setdefault(f["clientes"], [0.0, 0])
            if not math.isnan(f["media_ms"]):
                w[0] += f["media_ms"] * f["muestras"]
                w[1] += f["muestras"]
            tpm[f["clientes"]] = tpm.get(f["clientes"], 0.0) + tpm_de(f)
        xs = sorted(lat)
        if not xs:
            continue
        kw = {"color": COLOR[arq], "marker": MARCA[arq], "markersize": 7, "linewidth": 2,
              "markeredgecolor": "white", "markeredgewidth": 1.2, "label": arq}
        a1.plot(xs, [lat[x][0] / lat[x][1] if lat[x][1] else float("nan") for x in xs], **kw)
        a2.plot(xs, [tpm[x] for x in xs], **kw)
    a1.set_title("Tiempo de respuesta medio", loc="left")
    a1.set_ylabel("ms")
    a2.set_title("Transacciones por minuto", loc="left")
    a2.set_ylabel("TPM (medido en el GT)")
    for ax in (a1, a2):
        ax.set_xlabel("Clientes")
        ax.set_ylim(bottom=0)
        ax.set_xticks(sorted({f["clientes"] for f in filas}))
    a1.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    guardar(fig, salida, "g6_base_vs_escalable.png")


def g5(carpeta, salida, marca, descartar):
    from metricas import leer_corrida
    corrida = leer_corrida(carpeta, descartar)
    filas = corrida["filas"]
    t0 = min(r["inicio"] for r in filas)
    fig, ax = plt.subplots(figsize=(8.6, 3.8))
    colores = {"consulta": "#2a78d6", "reserva": "#eb6834", "modificacion": "#6250d6"}
    for tipo, color in colores.items():
        pts = [r for r in filas if r["tipo"] == tipo and r["estado"] != "sin_respuesta"]
        if pts:
            ax.scatter([r["inicio"] - t0 for r in pts], [r["tiempo_ms"] for r in pts], s=14, color=color,
                       alpha=0.85, label=tipo, edgecolors="none")
    reint = [r for r in filas if r["intentos"] > 1]
    if reint:
        ax.scatter([r["inicio"] - t0 for r in reint], [r["tiempo_ms"] for r in reint], s=80, facecolors="none",
                   edgecolors=TEXTO, linewidths=1.4, label="reenviada al otro GT (intentos > 1)")
    sin = [r for r in filas if r["estado"] == "sin_respuesta"]
    if sin:
        ax.scatter([r["inicio"] - t0 for r in sin], [r["tiempo_ms"] for r in sin], marker="x", s=50,
                   color="#e34948", label="sin respuesta")
    ruta_ev = os.path.join(carpeta, "gt_eventos.csv")
    if os.path.exists(ruta_ev):
        with open(ruta_ev, encoding="utf-8") as f:
            for e in csv.DictReader(f):
                t = float(e["hora"]) - t0
                if e["evento"] in ("gt_activo", "rmc_caida", "rmc_recuperada", "gt_pasivo") and t > 0:
                    ax.axvline(t, color=TEXTO2, linestyle="--", linewidth=1)
                    ax.annotate(e["evento"].replace("_", " "), (t, ax.get_ylim()[1]), rotation=90, va="top",
                                ha="right", fontsize=8, color=TEXTO2)
    if marca is not None:
        ax.axvline(marca, color="#e34948", linewidth=1.5)
        ax.annotate("falla provocada", (marca, ax.get_ylim()[1]), rotation=90, va="top", ha="right",
                    fontsize=8, color="#e34948")
    ax.set_title("Tiempo de respuesta durante la falla", loc="left")
    ax.set_xlabel("Segundos desde el inicio de la corrida")
    ax.set_ylabel("Tiempo de respuesta (ms)")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    fig.tight_layout()
    guardar(fig, salida, "g5_falla.png")


def main():
    p = argparse.ArgumentParser(description="Gráficas del informe de rendimiento")
    p.add_argument("grafica", choices=["g1", "g2", "g3", "g4", "g5", "g6"])
    p.add_argument("entrada", nargs="+",
                   help="resumen.csv (g1, g2, g4, g6), archivos de vmstat (g3) o carpeta de la corrida (g5)")
    p.add_argument("--salida", default="graficas")
    p.add_argument("--marca", type=float, help="g5: segundo (desde el inicio) en que se provocó la falla")
    p.add_argument("--descartar", type=float, default=0.0)
    p.add_argument("--umbral", type=float, default=5.0, help="g4: umbral de saturación en %% (como metricas.py)")
    a = p.parse_args()
    if a.grafica == "g3":
        g3(a.entrada, a.salida)
    elif a.grafica == "g5":
        g5(a.entrada[0], a.salida, a.marca, a.descartar)
    else:
        filas = leer_resumen(a.entrada[0])
        if a.grafica == "g4":
            filas = [f for f in filas if f["prueba"] == "capacidad"] or filas
            g4(filas, a.salida, a.umbral)
        else:
            filas = [f for f in filas if f["prueba"] == "escenario"] or filas
            {"g1": g1, "g2": g2, "g6": g6}[a.grafica](filas, a.salida)


if __name__ == "__main__":
    main()
