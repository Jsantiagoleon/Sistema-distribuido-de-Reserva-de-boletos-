import argparse
import json
import multiprocessing as mp
import sys
import time

import bd
import config
from prueba_robustez import enviar_crudo


def reservar(gt, id_cliente, asientos, arranque, salida):
    arranque.wait()
    respuesta = json.loads(enviar_crudo(gt, json.dumps({
        "id_solicitud": f"{id_cliente}-conc-{int(time.time())}", "id_cliente": id_cliente,
        "tipo": "reserva", "id_evento": "E49", "num_ocurrencia": 1, "asientos": asientos})))
    salida.put((id_cliente, respuesta["estado"]))


def ejecutar(gt, base=None):
    ok, detalle = True, []
    preparacion = json.loads(enviar_crudo(gt, json.dumps({
        "id_solicitud": f"C0-conc-{int(time.time())}", "id_cliente": "C0", "tipo": "reserva",
        "id_evento": "E49", "num_ocurrencia": 1, "asientos": 92})))
    detalle.append(f"preparación: se reservan 92 de 100 asientos de E49/oc1 -> {preparacion['estado']}, "
                   f"quedan {preparacion['datos'].get('libres')}")

    arranque, salida = mp.Event(), mp.Queue()
    procesos = [mp.Process(target=reservar, args=(gt, f"C{i}", 2, arranque, salida)) for i in range(1, 9)]
    for p in procesos:
        p.start()
    time.sleep(0.5)
    arranque.set()
    resultados = [salida.get(timeout=15) for _ in procesos]
    for p in procesos:
        p.join()

    exitos = sum(1 for _, e in resultados if e == "EXITO")
    rechazos = sum(1 for _, e in resultados if e == "RECHAZADO")
    bien = exitos == 4 and rechazos == 4
    ok &= bien
    detalle.append(f"{'OK ' if bien else 'MAL'}  8 clientes piden 2 asientos con 8 libres: "
                   f"{exitos} EXITO y {rechazos} RECHAZADO (esperado 4 y 4)")

    extra = json.loads(enviar_crudo(gt, json.dumps({
        "id_solicitud": f"C0-conc-extra-{int(time.time())}", "id_cliente": "C0", "tipo": "reserva",
        "id_evento": "E49", "num_ocurrencia": 1, "asientos": 1})))
    bien = extra["estado"] == "RECHAZADO"
    ok &= bien
    detalle.append(f"{'OK ' if bien else 'MAL'}  una reserva más de 1 asiento: {extra['estado']} (esperado RECHAZADO)")

    if base:
        conn = bd.conectar(None if base is True else base)
        with conn.cursor() as cur:
            cur.execute("SELECT asientos_libres, asientos_ocupados FROM ocurrencias "
                        "WHERE id_evento = 'E49' AND numero = 1")
            libres, ocupados = cur.fetchone()
            cur.execute("SELECT count(*), coalesce(sum(asientos), 0) FROM reservas "
                        "WHERE id_evento = 'E49' AND num_ocurrencia = 1 AND estado = 'activa'")
            reservas, vendidos = cur.fetchone()
        conn.close()
        bien = libres + ocupados == 100 and libres == 0 and vendidos == ocupados
        ok &= bien
        detalle.append(f"{'OK ' if bien else 'MAL'}  PostgreSQL: libres {libres} + ocupados {ocupados} = "
                       f"{libres + ocupados}; {reservas} reservas activas suman {vendidos} asientos")
    return ok, detalle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba C1: concurrencia sobre los últimos asientos")
    parser.add_argument("--gt", default=config.DIRS_GT[0])
    parser.add_argument("--bd", nargs="?", const=True, default=None, metavar="NOMBRE_BD",
                        help="consultar también PostgreSQL (la base configurada, o NOMBRE_BD) para revisar los asientos")
    args = parser.parse_args()
    ok, detalle = ejecutar(args.gt, args.bd)
    print("\n".join(detalle))
    print("C1:", "APROBADA" if ok else "FALLIDA")
    sys.exit(0 if ok else 1)
