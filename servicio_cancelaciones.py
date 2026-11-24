"""
ServicioCancelaciones · VM2

Recibe las cancelaciones que el GT empuja por PUSH/PULL (patrón pipeline), envía a
Persistencia la orden de liberación de asientos y, cuando Persistencia responde, publica la
notificación al cliente por PUB/SUB. El tópico de cada notificación es el id del cliente
(más ":"), de modo que cada cliente solo recibe las suyas.

Es la parte asíncrona de la cancelación: el cliente ya recibió ACEPTADA del GT; la notificación
llega cuando la liberación realmente quedó guardada en Persistencia.

Si Persistencia no responde en 3 s se reintenta (hasta 3 veces) con el mismo id_solicitud.
Como Persistencia guarda la respuesta de cada id_solicitud, un reintento nunca libera dos veces.
"""

import json
import time
from dataclasses import asdict
from datetime import datetime

import zmq

import config
from modelos import Respuesta, Solicitud, ERROR


def log(texto):
    print(f"{datetime.now():%H:%M:%S.%f}"[:-3] + f"  CANCEL {texto}", flush=True)


class ServicioCancelaciones:

    def __init__(self):
        self.ctx = zmq.Context()
        self.sock_gt = self.ctx.socket(zmq.PULL)                  # PULL: órdenes que empuja el GT
        self.sock_gt.bind(f"tcp://*:{config.PUERTO_CANCELACIONES}")
        self.sock_notificaciones = self.ctx.socket(zmq.PUB)       # PUB: notificaciones a clientes
        self.sock_notificaciones.bind(f"tcp://*:{config.PUERTO_NOTIFICACIONES}")
        self.sock_persistencia = self._nuevo_req()                # REQ: orden a Persistencia

    def _nuevo_req(self):
        sock = self.ctx.socket(zmq.REQ)
        sock.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_PERSISTENCIA_MS)
        sock.setsockopt(zmq.LINGER, 0)
        sock.connect(config.DIR_PERSISTENCIA)
        return sock

    def procesar_cancelacion(self, solicitud):
        """Orden de liberación a Persistencia, con reintentos si no responde."""
        for intento in range(1, config.REINTENTOS_CANCELACIONES + 1):
            try:
                self.sock_persistencia.send_string(json.dumps(
                    {"operacion": "cancelar_reserva", "solicitud": asdict(solicitud)}))
                return Respuesta(**json.loads(self.sock_persistencia.recv_string()))
            except zmq.Again:
                self.sock_persistencia.close()
                self.sock_persistencia = self._nuevo_req()
                log(f"Persistencia no respondió a {solicitud.id_solicitud} "
                    f"(intento {intento}/{config.REINTENTOS_CANCELACIONES})")
        return Respuesta(solicitud.id_solicitud, ERROR,
                         {"motivo": "persistencia no responde", "reintentar": True})

    def notificar_cliente(self, id_cliente, respuesta):
        """Publica la Respuesta con el id del cliente como tópico."""
        self.sock_notificaciones.send_multipart([f"{id_cliente}:".encode(),
                                                 json.dumps(asdict(respuesta), default=str).encode()])


def main():
    servicio = ServicioCancelaciones()
    log(f"ServicioCancelaciones: PULL :{config.PUERTO_CANCELACIONES} · PUB :{config.PUERTO_NOTIFICACIONES} "
        f"· Persistencia {config.DIR_PERSISTENCIA}")
    while True:
        mensaje = servicio.sock_gt.recv_string()
        inicio = time.perf_counter()
        id_cliente, id_solicitud = "?", "?"
        try:
            solicitud = Solicitud(**json.loads(mensaje))
            id_cliente, id_solicitud = solicitud.id_cliente, solicitud.id_solicitud
            respuesta = servicio.procesar_cancelacion(solicitud)
        except Exception as e:
            respuesta = Respuesta(id_solicitud, ERROR, {"motivo": f"mensaje inválido: {e}"})
        servicio.notificar_cliente(id_cliente, respuesta)
        log(f"{id_solicitud:<17} {respuesta.estado:<10} {time.perf_counter() - inicio:.4f} s  "
            f"-> notificación a {id_cliente}")


if __name__ == "__main__":
    main()
