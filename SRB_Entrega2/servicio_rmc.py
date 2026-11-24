"""
ServicioRMC (Reserva, Modificación y Consulta) · VM2

Recibe una Solicitud en JSON desde el GT, aplica las reglas del negocio pidiendo los datos
a Persistencia y devuelve una Respuesta en JSON.

Se pueden lanzar varias réplicas, cada una con su índice (proceso independiente, puerto propio):
    python3 servicio_rmc.py            réplica 0  (REP :5556, latidos :5650)
    python3 servicio_rmc.py 1          réplica 1  (REP :5566, latidos :5651)
    python3 servicio_rmc.py 1 --replica-lectura    las consultas del mes van a la réplica de lectura
                                                   de Persistencia (con respaldo en la principal)

Concurrencia: cada réplica atiende una solicitud a la vez en un solo hilo (los sockets de ZeroMQ
no son seguros entre hilos). Los latidos salen de un hilo auxiliar que tiene SU PROPIO socket PUB
y no comparte nada con el hilo principal, así una espera larga a Persistencia no hace que el GT
crea que la réplica murió.
"""

import argparse
import json
import threading
import time
from dataclasses import asdict
from datetime import datetime

import zmq

import config
from modelos import (Respuesta, Solicitud, CONSULTA, RESERVA, MODIFICACION, EXITO, RECHAZADO, ERROR)


def log(texto):
    print(f"{datetime.now():%H:%M:%S.%f}"[:-3] + f"  RMC    {texto}", flush=True)


class PersistenciaNoResponde(Exception):
    pass


class ServicioRMC:

    def __init__(self, indice=0, usar_replica_lectura=False):
        self.indice = indice
        self.usar_replica_lectura = usar_replica_lectura
        self.replica_caida_hasta = 0.0           # mientras no pase esta hora no se intenta la réplica
        self.ctx = zmq.Context()
        self.sock_gt = self.ctx.socket(zmq.REP)              # REP: atiende al GT
        self.sock_gt.bind(f"tcp://*:{config.puerto_rmc(indice)}")
        self.sock_persistencia = self._nuevo_req(config.DIR_PERSISTENCIA,
                                                 config.TIMEOUT_PERSISTENCIA_MS)
        self.sock_replica = (self._nuevo_req(config.DIR_REPLICA_LECTURA,
                                             config.TIMEOUT_REPLICA_LECTURA_MS)
                             if usar_replica_lectura else None)
        threading.Thread(target=self._emitir_latidos, daemon=True).start()

    # ------------------------------------------------------------ comunicación
    def _nuevo_req(self, direccion, timeout_ms):
        sock = self.ctx.socket(zmq.REQ)
        sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
        sock.setsockopt(zmq.LINGER, 0)
        sock.connect(direccion)
        return sock

    def _emitir_latidos(self):
        """Hilo auxiliar: un latido por segundo por un PUB propio."""
        pub = self.ctx.socket(zmq.PUB)
        pub.bind(f"tcp://*:{config.puerto_latido_rmc(self.indice)}")
        while True:
            pub.send_string(json.dumps({"rmc": self.indice, "t": time.time()}))
            time.sleep(config.INTERVALO_LATIDO_MS / 1000)

    def preguntar(self, operacion, solicitud):
        """Una ida y vuelta a Persistencia. Si no responde en 3 s se recrea el socket REQ
        (un REQ que no recibió su respuesta queda inutilizable) y se lanza PersistenciaNoResponde."""
        try:
            self.sock_persistencia.send_string(json.dumps(
                {"operacion": operacion, "solicitud": asdict(solicitud)}))
            return Respuesta(**json.loads(self.sock_persistencia.recv_string()))
        except zmq.Again:
            self.sock_persistencia.close()
            self.sock_persistencia = self._nuevo_req(config.DIR_PERSISTENCIA,
                                                     config.TIMEOUT_PERSISTENCIA_MS)
            raise PersistenciaNoResponde(operacion)

    def preguntar_replica(self, solicitud):
        """Consulta del mes a la réplica de lectura; devuelve None si no responde a tiempo."""
        if time.time() < self.replica_caida_hasta:
            return None
        try:
            self.sock_replica.send_string(json.dumps(
                {"operacion": "consultar_mes", "solicitud": asdict(solicitud)}))
            return Respuesta(**json.loads(self.sock_replica.recv_string()))
        except zmq.Again:
            self.sock_replica.close()
            self.sock_replica = self._nuevo_req(config.DIR_REPLICA_LECTURA,
                                                config.TIMEOUT_REPLICA_LECTURA_MS)
            self.replica_caida_hasta = time.time() + 10     # no se insiste durante 10 s
            log("réplica de lectura sin respuesta: las consultas van a la principal por 10 s")
            return None

    # ------------------------------------------------------------ reglas del negocio
    def procesar_consulta(self, solicitud):
        """Eventos del mes: réplica de lectura si está configurada; si no, Persistencia."""
        if not isinstance(solicitud.mes, int) or not 1 <= solicitud.mes <= 12:
            return Respuesta(solicitud.id_solicitud, ERROR, {"motivo": "mes inválido"})
        if self.sock_replica is not None:
            respuesta = self.preguntar_replica(solicitud)
            if respuesta is not None and respuesta.estado == EXITO:
                return respuesta
        return self.preguntar("consultar_mes", solicitud)

    def procesar_reserva(self, solicitud):
        """Consulta la disponibilidad y, si hay cupo, pide la confirmación a Persistencia."""
        if (not isinstance(solicitud.asientos, int) or isinstance(solicitud.asientos, bool)
                or not 1 <= solicitud.asientos <= config.ASIENTOS_POR_OCURRENCIA):
            return Respuesta(solicitud.id_solicitud, ERROR, {"motivo": "asientos inválidos"})

        disponibilidad = self.preguntar("consultar_disponibilidad", solicitud)
        if disponibilidad.estado == ERROR:
            return disponibilidad
        if disponibilidad.datos.get("repetida"):
            # Reintento de una solicitud ya procesada (por ejemplo tras la caída del GT):
            # Persistencia entregó la respuesta guardada y no se vuelve a ejecutar nada
            return Respuesta(disponibilidad.id_solicitud, disponibilidad.estado,
                             {k: v for k, v in disponibilidad.datos.items() if k != "repetida"})
        libres = disponibilidad.datos["libres"]
        if libres < solicitud.asientos:
            return Respuesta(solicitud.id_solicitud, RECHAZADO, {"motivo": "sin cupo", "libres": libres})

        # Hay cupo: confirmación condicional (Persistencia revisa el cupo otra vez, porque otra
        # réplica del RMC pudo reservar entre la consulta y la confirmación)
        return self.preguntar("confirmar_reserva", solicitud)

    def procesar_modificacion(self, solicitud):
        """Cambio de asientos o de ocurrencia. El cupo se revisa y se cambia dentro de
        Persistencia, en una sola operación atómica."""
        if not solicitud.id_reserva:
            return Respuesta(solicitud.id_solicitud, ERROR, {"motivo": "falta id_reserva"})
        if (solicitud.asientos is None) == (solicitud.num_ocurrencia is None):
            return Respuesta(solicitud.id_solicitud, ERROR,
                             {"motivo": "indique solo asientos o solo num_ocurrencia"})
        return self.preguntar("modificar_reserva", solicitud)


def main():
    parser = argparse.ArgumentParser(description="Réplica del servicio RMC")
    parser.add_argument("indice", nargs="?", type=int, default=0, help="índice de la réplica (0, 1, ...)")
    parser.add_argument("--replica-lectura", action="store_true",
                        help="enviar las consultas del mes a la réplica de lectura de Persistencia")
    args = parser.parse_args()

    servicio = ServicioRMC(args.indice, args.replica_lectura)
    log(f"RMC-{args.indice} escuchando en :{config.puerto_rmc(args.indice)} · latidos en "
        f":{config.puerto_latido_rmc(args.indice)} · Persistencia en {config.DIR_PERSISTENCIA}"
        + (" · consultas a la réplica de lectura" if args.replica_lectura else ""))

    while True:
        mensaje = servicio.sock_gt.recv_string()
        inicio = time.perf_counter()
        tipo, id_solicitud = "?", "?"
        try:
            crudo = json.loads(mensaje)
            if isinstance(crudo, dict):
                # el id se toma antes de validar los campos, para que un ERROR por mensaje
                # inválido lleve el id_solicitud del cliente y el GT pueda entregarlo
                id_solicitud = str(crudo.get("id_solicitud", "?"))
            solicitud = Solicitud(**crudo)
            tipo, id_solicitud = solicitud.tipo, solicitud.id_solicitud
            if tipo == CONSULTA:
                respuesta = servicio.procesar_consulta(solicitud)
            elif tipo == RESERVA:
                respuesta = servicio.procesar_reserva(solicitud)
            elif tipo == MODIFICACION:
                respuesta = servicio.procesar_modificacion(solicitud)
            else:
                respuesta = Respuesta(id_solicitud, ERROR, {"motivo": "tipo no soportado"})
        except PersistenciaNoResponde as e:
            # Persistencia no contestó en 3 s: el cliente recibe un ERROR que indica reintentar
            log(f"Persistencia no respondió a '{e}' en {config.TIMEOUT_PERSISTENCIA_MS / 1000:.0f} s; "
                f"se responde ERROR {id_solicitud}")
            respuesta = Respuesta(id_solicitud, ERROR,
                                  {"motivo": "persistencia no responde", "reintentar": True})
        except Exception as e:
            # Mensaje malformado: se responde ERROR y el servicio sigue funcionando
            respuesta = Respuesta(id_solicitud, ERROR, {"motivo": f"mensaje inválido: {e}"})

        servicio.sock_gt.send_string(json.dumps(asdict(respuesta), default=str))
        log(f"RMC-{args.indice} {tipo:<13} {id_solicitud:<17} {respuesta.estado:<10} "
            f"{time.perf_counter() - inicio:.4f} s")


if __name__ == "__main__":
    main()
