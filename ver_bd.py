"""
Muestra los asientos libres y ocupados de cada ocurrencia · VM3

Uso: python3 ver_bd.py
"""

import json
import os

import config


def main():
    if not os.path.exists(config.RUTA_BD):
        print("No existe events.json. Ejecute primero: python3 generar_bd.py")
        return

    with open(config.RUTA_BD, "r", encoding="utf-8") as f:
        bd = json.load(f)

    print(f"{'Evento':<8}{'Oc.':<5}{'Fecha':<13}{'Libres':>8}{'Ocupados':>10}")
    print("-" * 44)
    ocurrencias = libres = ocupados = 0
    for id_evento, evento in bd["eventos"].items():
        for oc in evento["ocurrencias"]:
            print(f"{id_evento:<8}{oc['numero']:<5}{oc['fecha']:<13}"
                  f"{oc['asientos_libres']:>8}{oc['asientos_ocupados']:>10}")
            ocurrencias += 1
            libres += oc["asientos_libres"]
            ocupados += oc["asientos_ocupados"]
    print("-" * 44)
    print(f"Eventos: {len(bd['eventos'])} · Ocurrencias: {ocurrencias} · Libres: {libres} · "
          f"Ocupados: {ocupados} · Reservas: {len(bd['reservas'])}")


if __name__ == "__main__":
    main()