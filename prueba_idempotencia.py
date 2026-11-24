"""
Prueba U2 (idempotencia) · PC o VM1

Envía DOS veces la misma solicitud (mismo id_solicitud), como haría un cliente que reintenta tras
la caída del GT, y comprueba que la operación se ejecuta una sola vez:
  1. Reserva repetida: la segunda respuesta es idéntica y los asientos se descontaron una vez.
  2. Reserva que agota la ocurrencia, repetida: sigue siendo EXITO (no RECHAZADO por falta de cupo).
  3. Modificación repetida: mismo resultado, sin aplicar el cambio dos veces.

Usa E50/oc1 y E48/oc1; después hay que reiniciar la BD (python3 generar_bd.py).

Uso: python3 prueba_idempotencia.py [--gt tcp://10.43.100.247:5557]
"""

import argparse
import json
import sys
import time

import config
from prueba_robustez import enviar_crudo


def pedir(gt, **campos):
    return json.loads(enviar_crudo(gt, json.dumps({"id_cliente": "ID", **campos})))


def ejecutar(gt):
    marca = int(time.time())
    ok, detalle = True, []

    def comprobar(condicion, texto):
        nonlocal ok
        ok &= bool(condicion)
        detalle.append(f"{'OK ' if condicion else 'MAL'}  {texto}")

    # 1. reserva repetida
    r = dict(id_solicitud=f"ID-{marca}-1", tipo="reserva", id_evento="E50", num_ocurrencia=1, asientos=4)
    a, b = pedir(gt, **r), pedir(gt, **r)
    comprobar(a["estado"] == "EXITO" and a == b, f"reserva enviada dos veces: misma respuesta ({a['datos']})")
    c = pedir(gt, id_solicitud=f"ID-{marca}-2", tipo="reserva", id_evento="E50", num_ocurrencia=1, asientos=1)
    comprobar(c["datos"].get("libres") == 95,
              f"los asientos se descontaron una sola vez: quedan {c['datos'].get('libres')} (esperado 95)")

    # 2. reserva que agota la ocurrencia, repetida
    r = dict(id_solicitud=f"ID-{marca}-3", tipo="reserva", id_evento="E48", num_ocurrencia=1, asientos=100)
    a, b = pedir(gt, **r), pedir(gt, **r)
    comprobar(a["estado"] == "EXITO" and b == a,
              f"reserva de las 100 plazas repetida: {a['estado']} y luego {b['estado']} (esperado EXITO y EXITO)")

    # 3. modificación repetida
    reserva = a["datos"]["id_reserva"]
    m = dict(id_solicitud=f"ID-{marca}-4", tipo="modificacion", id_reserva=reserva, asientos=90)
    a, b = pedir(gt, **m), pedir(gt, **m)
    comprobar(a["estado"] == "EXITO" and a == b,
              f"modificación repetida: misma respuesta ({a['datos']}); libres tras el cambio = 10")
    return ok, detalle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba U2: idempotencia")
    parser.add_argument("--gt", default=config.DIRS_GT[0])
    args = parser.parse_args()
    ok, detalle = ejecutar(args.gt)
    print("\n".join(detalle))
    print("U2:", "APROBADA" if ok else "FALLIDA")
    sys.exit(0 if ok else 1)
