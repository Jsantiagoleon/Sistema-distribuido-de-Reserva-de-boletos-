import argparse
import json
import sys

import zmq

import config

CASOS = [
    ("texto que no es JSON", "hola"),
    ("JSON que no es un objeto", "[1, 2, 3]"),
    ("falta id_solicitud", json.dumps({"id_cliente": "R", "tipo": "consulta", "mes": 11})),
    ("campo desconocido", json.dumps({"id_solicitud": "R-1", "id_cliente": "R", "tipo": "consulta",
                                      "mes": 11, "extra": 1})),
    ("tipo desconocido", json.dumps({"id_solicitud": "R-2", "id_cliente": "R", "tipo": "borrar"})),
    ("mes fuera de rango (13)", json.dumps({"id_solicitud": "R-3", "id_cliente": "R", "tipo": "consulta", "mes": 13})),
    ("mes con texto", json.dumps({"id_solicitud": "R-4", "id_cliente": "R", "tipo": "consulta", "mes": "once"})),
    ("reserva con 0 asientos", json.dumps({"id_solicitud": "R-5", "id_cliente": "R", "tipo": "reserva",
                                           "id_evento": "E1", "num_ocurrencia": 1, "asientos": 0})),
    ("reserva con 101 asientos", json.dumps({"id_solicitud": "R-6", "id_cliente": "R", "tipo": "reserva",
                                             "id_evento": "E1", "num_ocurrencia": 1, "asientos": 101})),
    ("reserva con asientos como texto", json.dumps({"id_solicitud": "R-7", "id_cliente": "R", "tipo": "reserva",
                                                    "id_evento": "E1", "num_ocurrencia": 1, "asientos": "dos"})),
    ("evento inexistente", json.dumps({"id_solicitud": "R-8", "id_cliente": "R", "tipo": "reserva",
                                       "id_evento": "E99", "num_ocurrencia": 1, "asientos": 1})),
    ("ocurrencia inexistente", json.dumps({"id_solicitud": "R-9", "id_cliente": "R", "tipo": "reserva",
                                           "id_evento": "E30", "num_ocurrencia": 2, "asientos": 1})),
    ("modificación sin id_reserva", json.dumps({"id_solicitud": "R-10", "id_cliente": "R",
                                                "tipo": "modificacion", "asientos": 2})),
    ("modificación de una reserva inexistente", json.dumps({"id_solicitud": "R-11", "id_cliente": "R",
                                                            "tipo": "modificacion", "id_reserva": "R9999",
                                                            "asientos": 2})),
]


def enviar_crudo(gt, texto, timeout_ms=6000):
    sock = zmq.Context.instance().socket(zmq.REQ)
    sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(gt)
    try:
        sock.send_string(texto)
        return sock.recv_string()
    except zmq.Again:
        return None
    finally:
        sock.close()


def ejecutar(gt):
    ok, detalle = True, []
    for nombre, mensaje in CASOS:
        crudo = enviar_crudo(gt, mensaje)
        try:
            estado = json.loads(crudo)["estado"]
        except Exception:
            estado = "SIN RESPUESTA VÁLIDA" if crudo is None else f"respuesta no JSON: {crudo!r}"
        bien = estado in ("ERROR", "RECHAZADO")
        ok &= bien
        detalle.append(f"{'OK ' if bien else 'MAL'}  {nombre:<42} -> {estado}")

    valida = json.dumps({"id_solicitud": "R-FIN", "id_cliente": "R", "tipo": "consulta", "mes": config.MES})
    crudo = enviar_crudo(gt, valida)
    sigue = crudo is not None and json.loads(crudo)["estado"] == "EXITO"
    ok &= sigue
    detalle.append(f"{'OK ' if sigue else 'MAL'}  consulta válida después de los mensajes malos -> "
                   f"{'EXITO' if sigue else 'falló'}")
    return ok, detalle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba R1: mensajes mal formados")
    parser.add_argument("--gt", default=config.DIRS_GT[0])
    args = parser.parse_args()
    ok, detalle = ejecutar(args.gt)
    print("\n".join(detalle))
    print("R1:", "APROBADA" if ok else "FALLIDA")
    sys.exit(0 if ok else 1)
