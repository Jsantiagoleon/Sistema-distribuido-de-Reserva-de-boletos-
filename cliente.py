"""
ClienteCarga · VM1

REQ    connect VM2:5557 -> GestorTransacciones (ROUTER)   · consulta y reserva
DEALER connect VM2:5558 -> GestorTransacciones (ROUTER)   · cancelación (Entrega 2)
SUB    connect VM2:5560 <- ServicioCancelaciones (PUB)    · notificaciones (Entrega 2)

Genera carga durante un tiempo dado: envía consultas y reservas al Gestor,
mide el tiempo de respuesta de cada una y lo guarda en resultados_<id>.csv.

Uso: python3 cliente.py --id C1 --rpm 20 --modo fija --pct-consulta 50 --pct-reserva 50 --duracion 3
"""

import argparse
import itertools
import json
import os
import random
import time
from dataclasses import asdict
from datetime import datetime

import zmq

import config
from modelos import Respuesta, Solicitud, CONSULTA, RESERVA

# Consecutivo de las solicitudes de este cliente: C1-0001, C1-0002, ...
consecutivo = itertools.count(1)


class ClienteCarga:

    def __init__(self, id_cliente, rpm, pct_consulta, pct_reserva, pct_modificacion, modo,
                 direccion_gt=config.DIR_GT):
        self.id_cliente = id_cliente
        self.rpm = rpm
        self.pct_consulta = pct_consulta
        self.pct_reserva = pct_reserva
        self.pct_modificacion = pct_modificacion
        self.modo = modo                # fija | cerrado
        self.sock_sync = zmq.Context.instance().socket(zmq.REQ)     # REQ hacia el GT
        self.sock_sync.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_CLIENTE_MS)
        self.sock_sync.setsockopt(zmq.LINGER, 0)
        self.sock_sync.connect(direccion_gt)
        self.sock_cancel = None         # DEALER (Entrega 2)
        self.sock_notif = None          # SUB    (Entrega 2)

    def enviar_consulta(self, mes):
        """Envía una consulta de los eventos del mes y devuelve la Respuesta
        (None si no hubo respuesta en 5 s)."""
        solicitud = Solicitud(f"{self.id_cliente}-{next(consecutivo):04d}", self.id_cliente,
                              CONSULTA, mes=mes)
        inicio = time.perf_counter()
        try:
            self.sock_sync.send_string(json.dumps(asdict(solicitud)))
            respuesta = Respuesta(**json.loads(self.sock_sync.recv_string()))
        except zmq.Again:
            # Timeout: se registra sin_respuesta y se reabre el socket REQ
            respuesta = None
            direccion = self.sock_sync.getsockopt_string(zmq.LAST_ENDPOINT)
            self.sock_sync.close()
            self.sock_sync = zmq.Context.instance().socket(zmq.REQ)
            self.sock_sync.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_CLIENTE_MS)
            self.sock_sync.setsockopt(zmq.LINGER, 0)
            self.sock_sync.connect(direccion)
        ms = (time.perf_counter() - inicio) * 1000
        self.registrar_resultado(solicitud, respuesta, ms)
        return respuesta

    def enviar_reserva(self, id_evento, num_ocurrencia, asientos):
        """Envía una reserva y devuelve la Respuesta (None si no hubo respuesta en 5 s)."""
        solicitud = Solicitud(f"{self.id_cliente}-{next(consecutivo):04d}", self.id_cliente,
                              RESERVA, id_evento=id_evento, num_ocurrencia=num_ocurrencia,
                              asientos=asientos)
        inicio = time.perf_counter()
        try:
            self.sock_sync.send_string(json.dumps(asdict(solicitud)))
            respuesta = Respuesta(**json.loads(self.sock_sync.recv_string()))
        except zmq.Again:
            # Timeout: se registra sin_respuesta y se reabre el socket REQ
            respuesta = None
            direccion = self.sock_sync.getsockopt_string(zmq.LAST_ENDPOINT)
            self.sock_sync.close()
            self.sock_sync = zmq.Context.instance().socket(zmq.REQ)
            self.sock_sync.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_CLIENTE_MS)
            self.sock_sync.setsockopt(zmq.LINGER, 0)
            self.sock_sync.connect(direccion)
        ms = (time.perf_counter() - inicio) * 1000
        self.registrar_resultado(solicitud, respuesta, ms)
        return respuesta

    def enviar_modificacion(self, id_reserva, num_ocurrencia, asientos):
        """Entrega 2."""
        pass

    def enviar_cancelacion(self, id_reserva):
        """Entrega 2."""
        pass

    def recibir_notificacion(self):
        """Entrega 2."""
        pass

    def registrar_resultado(self, solicitud, respuesta, ms):
        """Guarda el tiempo de respuesta en resultados_<id>.csv e imprime la línea de log."""
        estado = respuesta.estado if respuesta else "sin_respuesta"

        os.makedirs(config.DIR_RESULTADOS, exist_ok=True)
        ruta = os.path.join(config.DIR_RESULTADOS, f"resultados_{self.id_cliente}.csv")
        nuevo = not os.path.exists(ruta)
        with open(ruta, "a", encoding="utf-8") as f:
            if nuevo:
                f.write("hora,id_solicitud,tipo,estado,tiempo_ms\n")
            f.write(f"{time.time():.3f},{solicitud.id_solicitud},{solicitud.tipo},{estado},{ms:.3f}\n")

        detalle = (f"{solicitud.id_evento}/oc{solicitud.num_ocurrencia} {solicitud.asientos} asientos"
                   if solicitud.tipo == RESERVA else f"mes {solicitud.mes}")
        print(f"{datetime.now():%H:%M:%S.%f}"[:-3] +
              f"  {self.id_cliente:<6} {solicitud.tipo:<25} {solicitud.id_solicitud:<10} "
              f"{estado:<13} {ms / 1000:.4f} s  {detalle}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Cliente generador de carga del SRB")
    parser.add_argument("--id", required=True, help="identificador del cliente (C1 ... C8)")
    parser.add_argument("--gt", default=config.DIR_GT, help="dirección del Gestor")
    parser.add_argument("--rpm", type=int, default=config.MIN_RPM, help="solicitudes por minuto")
    parser.add_argument("--modo", choices=["fija", "cerrado"], default="fija")
    parser.add_argument("--pct-consulta", type=int, default=50)
    parser.add_argument("--pct-reserva", type=int, default=50)
    parser.add_argument("--pct-modificacion", type=int, default=0)
    parser.add_argument("--duracion", type=float, default=3, help="minutos de carga")
    args = parser.parse_args()

    if args.pct_consulta + args.pct_reserva + args.pct_modificacion != 100:
        parser.error("los porcentajes deben sumar 100")
    if args.rpm < config.MIN_RPM:
        parser.error(f"--rpm debe ser al menos {config.MIN_RPM}")
    if args.pct_modificacion > 0:
        parser.error("la modificación se implementa en la Entrega 2")

    cliente = ClienteCarga(args.id, args.rpm, args.pct_consulta, args.pct_reserva,
                           args.pct_modificacion, args.modo, args.gt)
    print(f"{args.id}: {args.rpm} solicitudes/min · modo {args.modo} · "
          f"{args.pct_consulta}% consultas, {args.pct_reserva}% reservas · "
          f"{args.duracion} min · Gestor en {args.gt}", flush=True)

    intervalo = 60 / args.rpm
    fin = time.time() + args.duracion * 60
    estados = {}
    try:
        while time.time() < fin:
            inicio = time.time()
            if random.randint(1, 100) <= args.pct_consulta:
                respuesta = cliente.enviar_consulta(config.MES)
            else:
                n = random.randint(1, config.NUM_EVENTOS)
                ocurrencia = random.randint(1, 2) if n <= config.EVENTOS_CON_DOS_OCURRENCIAS else 1
                respuesta = cliente.enviar_reserva(f"E{n}", ocurrencia, random.randint(1, 4))

            estado = respuesta.estado if respuesta else "sin_respuesta"
            estados[estado] = estados.get(estado, 0) + 1

            # Modo fija: una solicitud cada 60/rpm segundos. Modo cerrado: sin espera
            if args.modo == "fija":
                time.sleep(max(0.0, intervalo - (time.time() - inicio)))
    except KeyboardInterrupt:
        pass

    print(f"{args.id} terminó · {sum(estados.values())} solicitudes · {estados}", flush=True)


if __name__ == "__main__":
    main()