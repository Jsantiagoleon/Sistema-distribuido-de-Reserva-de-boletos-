"""
ClienteCarga · VM1

Un proceso = un cliente. Genera solicitudes de consulta, reserva, modificación y cancelación
con porcentajes y ritmo parametrizables, mide el tiempo de respuesta de cada una y recibe las
notificaciones de cancelación.

Canales
  * Síncrono: REQ -> ROUTER del GT (consulta, reserva, modificación).
  * Asíncrono: DEALER -> ROUTER del GT (cancelación). El GT responde ACEPTADA al instante y,
    más tarde, el Servicio de Cancelaciones publica la notificación (SUB con el id del cliente).

Tolerancia a fallas (transparente para el usuario)
  * Si el GT no responde en 5 s, el cliente reenvía la MISMA solicitud (mismo id_solicitud) al otro
    GT de la lista --gt y se queda con él. Persistencia reconoce el id_solicitud y no repite la
    operación si ya se había ejecutado.
  * Si la notificación de una cancelación no llega en 10 s, reenvía la cancelación (mismo id).

Ejemplos
    python3 cliente.py --id C1 --rpm 20 --duracion 3                         50% consultas, 50% reservas
    python3 cliente.py --id C3 --pct-consulta 40 --pct-reserva 30 --pct-modificacion 20 --pct-cancelacion 10
    python3 cliente.py --id C1 --gt tcp://127.0.0.1:5557                     solo un GT (sin reintento)
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
from modelos import (Respuesta, Solicitud, CONSULTA, RESERVA, MODIFICACION, CANCELACION,
                     EXITO, ACEPTADA)


ejecucion = datetime.now().strftime("%H%M%S")
consecutivo = itertools.count(1)


def direccion_asincrona(direccion_gt):
    """El canal asíncrono del GT usa el puerto síncrono + 1."""
    base, puerto = direccion_gt.rsplit(":", 1)
    return f"{base}:{int(puerto) + 1}"


class ClienteCarga:

    def __init__(self, id_cliente, rpm=config.MIN_RPM, pct_consulta=50, pct_reserva=50,
                 pct_modificacion=0, pct_cancelacion=0, modo="fija",
                 dirs_gt=None, dir_notificaciones=config.DIR_NOTIFICACIONES, silencioso=False):
        self.id_cliente = id_cliente
        self.rpm = rpm
        self.pct_consulta, self.pct_reserva = pct_consulta, pct_reserva
        self.pct_modificacion, self.pct_cancelacion = pct_modificacion, pct_cancelacion
        self.modo = modo                                   # fija | cerrado
        self.dirs_gt = list(dirs_gt or config.DIRS_GT)
        self.gt_actual = 0                                 # índice del GT en uso (se queda con él)
        self.silencioso = silencioso
        self.ctx = zmq.Context.instance()

        self.sock_sync = None
        self.sock_async = None
        self._abrir_canales()

        # Notificaciones: SUB suscrito al tópico "<id_cliente>:"
        self.sock_notif = self.ctx.socket(zmq.SUB)
        self.sock_notif.setsockopt_string(zmq.SUBSCRIBE, f"{id_cliente}:")
        self.sock_notif.connect(dir_notificaciones)

        self.reservas = []          # reservas propias confirmadas (para modificar y cancelar)
        self.cancelaciones = {}     # id_solicitud -> dict(t0, solicitud, reenvios)
        self.notificaciones = []    # notificaciones recibidas (Respuesta), útil en las pruebas

        os.makedirs(config.DIR_RESULTADOS, exist_ok=True)
        self.f_csv = open(os.path.join(config.DIR_RESULTADOS, f"resultados_{id_cliente}.csv"),
                          "a", buffering=1, encoding="utf-8")
        if self.f_csv.tell() == 0:
            self.f_csv.write("hora,id_solicitud,tipo,estado,tiempo_ms,intentos\n")
        time.sleep(0.3)             # deja que el SUB termine de conectarse antes de la primera cancelación

    # ------------------------------------------------------------ canales
    @property
    def gt(self):
        return self.dirs_gt[self.gt_actual]

    def _abrir_canales(self):
        """(Re)crea los sockets hacia el GT actual. Un REQ que no recibió su respuesta queda
        inutilizable, por eso se reabre tras cada timeout."""
        for s in (self.sock_sync, self.sock_async):
            if s is not None:
                s.close()
        self.sock_sync = self.ctx.socket(zmq.REQ)
        self.sock_sync.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_CLIENTE_MS)
        self.sock_sync.setsockopt(zmq.LINGER, 0)
        self.sock_sync.setsockopt(zmq.REQ_CORRELATE, 1)     # descarta respuestas de solicitudes anteriores
        self.sock_sync.setsockopt(zmq.REQ_RELAXED, 1)
        self.sock_sync.connect(self.gt)
        self.sock_async = self.ctx.socket(zmq.DEALER)
        self.sock_async.setsockopt(zmq.LINGER, 0)
        self.sock_async.connect(direccion_asincrona(self.gt))

    def _cambiar_gt(self, motivo):
        anterior = self.gt
        if len(self.dirs_gt) > 1:
            self.gt_actual = (self.gt_actual + 1) % len(self.dirs_gt)
        self._abrir_canales()
        self.decir(f"{motivo}: {'pasa al GT ' + self.gt if self.gt != anterior else 'reabre el canal'}")

    def decir(self, texto):
        if not self.silencioso:
            print(f"{datetime.now():%H:%M:%S.%f}"[:-3] + f"  {self.id_cliente:<6} {texto}", flush=True)

    def nueva_solicitud(self, tipo, **campos):
        return Solicitud(f"{self.id_cliente}-{ejecucion}-{next(consecutivo):04d}",
                         self.id_cliente, tipo, **campos)

    # ------------------------------------------------------------ canal síncrono
    def enviar_sincrono(self, solicitud):
        """Envía la solicitud al GT y espera 5 s. Sin respuesta, reenvía la misma solicitud al
        otro GT (a lo sumo MAX_INTENTOS_CLIENTE veces). Devuelve (Respuesta | None, intentos)."""
        maximo = config.MAX_INTENTOS_CLIENTE if len(self.dirs_gt) > 1 else 1
        for intento in range(1, maximo + 1):
            try:
                self.sock_sync.send_string(json.dumps(asdict(solicitud)))
                return Respuesta(**json.loads(self.sock_sync.recv_string())), intento
            except zmq.Again:
                if intento < maximo:
                    self._cambiar_gt(f"sin respuesta del GT en {config.TIMEOUT_CLIENTE_MS / 1000:.0f} s "
                                     f"para {solicitud.id_solicitud}; reenvía la misma solicitud")
                else:
                    self._abrir_canales()
        return None, maximo

    def _ejecutar(self, solicitud, detalle):
        inicio = time.perf_counter()
        respuesta, intentos = self.enviar_sincrono(solicitud)
        ms = (time.perf_counter() - inicio) * 1000
        self.registrar_resultado(solicitud, respuesta, ms, detalle, intentos)
        return respuesta

    def enviar_consulta(self, mes):
        return self._ejecutar(self.nueva_solicitud(CONSULTA, mes=mes), f"mes {mes}")

    def enviar_reserva(self, id_evento, num_ocurrencia, asientos):
        solicitud = self.nueva_solicitud(RESERVA, id_evento=id_evento,
                                         num_ocurrencia=num_ocurrencia, asientos=asientos)
        respuesta = self._ejecutar(solicitud, f"{id_evento}/oc{num_ocurrencia} {asientos} asientos")
        if respuesta and respuesta.estado == EXITO:
            self.reservas.append({"id_reserva": respuesta.datos["id_reserva"], "id_evento": id_evento,
                                  "num_ocurrencia": num_ocurrencia, "asientos": asientos})
        return respuesta

    def enviar_modificacion(self, id_reserva, asientos=None, num_ocurrencia=None):
        """Cambia el número de asientos O pasa la reserva a otra ocurrencia (no ambos)."""
        solicitud = self.nueva_solicitud(MODIFICACION, id_reserva=id_reserva, asientos=asientos,
                                         num_ocurrencia=num_ocurrencia)
        cambio = f"{asientos} asientos" if asientos is not None else f"a la ocurrencia {num_ocurrencia}"
        respuesta = self._ejecutar(solicitud, f"{id_reserva} {cambio}")
        if respuesta and respuesta.estado == EXITO:
            for r in self.reservas:
                if r["id_reserva"] == id_reserva:
                    r["asientos"] = respuesta.datos.get("asientos", r["asientos"])
                    r["num_ocurrencia"] = respuesta.datos.get("num_ocurrencia", r["num_ocurrencia"])
        return respuesta

    # ------------------------------------------------------------ canal asíncrono
    def enviar_cancelacion(self, id_reserva):
        """Cancelación asíncrona: el GT contesta ACEPTADA de inmediato; la notificación de que la
        liberación quedó guardada llega después por el canal SUB (ver recibir_notificacion)."""
        solicitud = self.nueva_solicitud(CANCELACION, id_reserva=id_reserva)
        inicio = time.perf_counter()
        respuesta, intentos = self.enviar_asincrono(solicitud)
        ms = (time.perf_counter() - inicio) * 1000
        self.registrar_resultado(solicitud, respuesta, ms, id_reserva, intentos)
        if respuesta and respuesta.estado == ACEPTADA:
            ahora = time.perf_counter()
            self.cancelaciones[solicitud.id_solicitud] = {"t0": ahora, "ultimo_envio": ahora,
                                                          "solicitud": solicitud, "reenvios": 0}
        return respuesta

    def enviar_asincrono(self, solicitud):
        maximo = config.MAX_INTENTOS_CLIENTE if len(self.dirs_gt) > 1 else 1
        for intento in range(1, maximo + 1):
            self.sock_async.send_string(json.dumps(asdict(solicitud)))
            if self.sock_async.poll(config.TIMEOUT_CLIENTE_MS):
                respuesta = Respuesta(**json.loads(self.sock_async.recv_string()))
                if respuesta.id_solicitud == solicitud.id_solicitud:
                    return respuesta, intento
            if intento < maximo:
                self._cambiar_gt(f"sin acuse del GT para {solicitud.id_solicitud}; reenvía la cancelación")
        return None, maximo

    def recibir_notificacion(self, espera_ms=0):
        """Lee una notificación si hay (espera hasta espera_ms). Devuelve la Respuesta o None."""
        self.vaciar_acuses_tardios()
        if not self.sock_notif.poll(espera_ms):
            return None
        _, cuerpo = self.sock_notif.recv_multipart()
        respuesta = Respuesta(**json.loads(cuerpo))
        pendiente = self.cancelaciones.pop(respuesta.id_solicitud, None)
        if pendiente is None:
            return respuesta        # notificación repetida (por un reenvío): ya estaba atendida
        ms = (time.perf_counter() - pendiente["t0"]) * 1000
        self.notificaciones.append(respuesta)
        self.registrar_resultado(pendiente["solicitud"], respuesta, ms, "notificación de cancelación",
                                 pendiente["reenvios"] + 1, tipo="notificacion")
        return respuesta

    def vaciar_acuses_tardios(self):
        """Descarta los ACEPTADA que llegan después de un reenvío (ya no hacen falta)."""
        while self.sock_async.poll(0):
            self.sock_async.recv_string()

    def revisar_cancelaciones(self):
        """Atiende las notificaciones que lleguen y reenvía las cancelaciones cuya notificación
        tarda más de 10 s (mismo id_solicitud: Persistencia no libera dos veces)."""
        while self.recibir_notificacion(0) is not None:
            pass
        ahora = time.perf_counter()
        for id_solicitud, p in list(self.cancelaciones.items()):
            if ahora - p["ultimo_envio"] < config.TIMEOUT_NOTIFICACION_MS / 1000:
                continue
            if p["reenvios"] >= config.MAX_REENVIOS_CANCELACION:
                del self.cancelaciones[id_solicitud]
                self.registrar_resultado(p["solicitud"], None, (ahora - p["t0"]) * 1000,
                                         "sin notificación", p["reenvios"] + 1, tipo="notificacion")
                continue
            p["reenvios"] += 1
            p["ultimo_envio"] = ahora
            self.decir(f"notificación de {id_solicitud} no llegó en "
                       f"{config.TIMEOUT_NOTIFICACION_MS / 1000:.0f} s: reenvía la cancelación")
            self.sock_async.send_string(json.dumps(asdict(p["solicitud"])))

    # ------------------------------------------------------------ registro
    def registrar_resultado(self, solicitud, respuesta, ms, detalle, intentos=1, tipo=None):
        """Guarda el tiempo de respuesta en resultados_<id>.csv e imprime la línea de log."""
        tipo = tipo or solicitud.tipo
        estado = respuesta.estado if respuesta else "sin_respuesta"
        self.f_csv.write(f"{time.time():.3f},{solicitud.id_solicitud},{tipo},{estado},"
                         f"{ms:.3f},{intentos}\n")
        extra = f"  [{intentos} intentos]" if intentos > 1 else ""
        motivo = (f"  ({respuesta.datos['motivo']})" if respuesta and respuesta.datos.get("motivo") else "")
        self.decir(f"{tipo:<13} {solicitud.id_solicitud:<17} {estado:<13} {ms / 1000:.4f} s  "
                   f"{detalle}{motivo}{extra}")

    # ------------------------------------------------------------ carga
    def siguiente_solicitud(self):
        """Elige el tipo según los porcentajes. Modificar o cancelar exige tener una reserva propia;
        si todavía no hay ninguna, el cliente reserva."""
        r = random.randint(1, 100)
        if r <= self.pct_consulta:
            return self.enviar_consulta(config.MES)
        if r > self.pct_consulta + self.pct_reserva and self.reservas:
            if r <= self.pct_consulta + self.pct_reserva + self.pct_modificacion:
                return self.modificar_al_azar()
            return self.cancelar_al_azar()
        n = random.randint(1, config.NUM_EVENTOS)
        ocurrencia = random.randint(1, 2) if n <= config.EVENTOS_CON_DOS_OCURRENCIAS else 1
        return self.enviar_reserva(f"E{n}", ocurrencia, random.randint(1, 4))

    def modificar_al_azar(self):
        reserva = random.choice(self.reservas)
        dos_ocurrencias = int(reserva["id_evento"][1:]) <= config.EVENTOS_CON_DOS_OCURRENCIAS
        if dos_ocurrencias and random.random() < 0.5:
            return self.enviar_modificacion(reserva["id_reserva"],
                                            num_ocurrencia=3 - reserva["num_ocurrencia"])
        nuevo = random.choice([a for a in range(1, 5) if a != reserva["asientos"]])
        return self.enviar_modificacion(reserva["id_reserva"], asientos=nuevo)

    def cancelar_al_azar(self):
        reserva = self.reservas.pop(random.randrange(len(self.reservas)))
        return self.enviar_cancelacion(reserva["id_reserva"])

    def esperar(self, segundos):
        """Espera atendiendo las notificaciones que lleguen mientras tanto."""
        fin = time.time() + segundos
        while True:
            self.revisar_cancelaciones()
            restante = fin - time.time()
            if restante <= 0:
                return
            time.sleep(min(0.1, restante))

    def esperar_notificaciones_pendientes(self, maximo_s=None):
        maximo_s = maximo_s or (config.TIMEOUT_NOTIFICACION_MS / 1000) * (config.MAX_REENVIOS_CANCELACION + 1)
        fin = time.time() + maximo_s
        while self.cancelaciones and time.time() < fin:
            self.revisar_cancelaciones()
            time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description="Cliente generador de carga del SRB")
    parser.add_argument("--id", required=True, help="identificador del cliente (C1 ... C8)")
    parser.add_argument("--gt", default=",".join(config.DIRS_GT),
                        help="direcciones de los GT separadas por coma (principal primero)")
    parser.add_argument("--notif", default=config.DIR_NOTIFICACIONES,
                        help="dirección PUB de las notificaciones")
    parser.add_argument("--rpm", type=int, default=config.MIN_RPM, help="solicitudes por minuto")
    parser.add_argument("--modo", choices=["fija", "cerrado"], default="fija",
                        help="fija: una solicitud cada 60/rpm s · cerrado: la siguiente al recibir la respuesta")
    parser.add_argument("--pct-consulta", type=int, default=50)
    parser.add_argument("--pct-reserva", type=int, default=50)
    parser.add_argument("--pct-modificacion", type=int, default=0)
    parser.add_argument("--pct-cancelacion", type=int, default=0)
    parser.add_argument("--duracion", type=float, default=3, help="minutos de carga")
    parser.add_argument("--semilla", type=int, help="semilla del generador aleatorio (repetir una corrida)")
    args = parser.parse_args()

    if args.pct_consulta + args.pct_reserva + args.pct_modificacion + args.pct_cancelacion != 100:
        parser.error("los porcentajes deben sumar 100")
    if args.modo == "fija" and args.rpm < config.MIN_RPM:
        parser.error(f"--rpm debe ser al menos {config.MIN_RPM}")
    if args.semilla is not None:
        random.seed(args.semilla)

    cliente = ClienteCarga(args.id, args.rpm, args.pct_consulta, args.pct_reserva,
                           args.pct_modificacion, args.pct_cancelacion, args.modo,
                           args.gt.split(","), args.notif)
    print(f"{args.id}: {args.rpm} solicitudes/min · modo {args.modo} · {args.pct_consulta}% consultas, "
          f"{args.pct_reserva}% reservas, {args.pct_modificacion}% modificaciones, "
          f"{args.pct_cancelacion}% cancelaciones · {args.duracion} min · GT {args.gt}", flush=True)

    intervalo = 60 / args.rpm
    fin = time.time() + args.duracion * 60
    estados = {}
    try:
        while time.time() < fin:
            inicio = time.time()
            respuesta = cliente.siguiente_solicitud()
            estado = respuesta.estado if respuesta else "sin_respuesta"
            estados[estado] = estados.get(estado, 0) + 1
            if args.modo == "fija":
                cliente.esperar(max(0.0, intervalo - (time.time() - inicio)))
            else:
                cliente.revisar_cancelaciones()
        cliente.esperar_notificaciones_pendientes()
    except KeyboardInterrupt:
        pass

    print(f"{args.id} terminó · {sum(estados.values())} solicitudes · {estados} · "
          f"notificaciones recibidas: {len(cliente.notificaciones)} · "
          f"sin notificación: {len(cliente.cancelaciones)}", flush=True)


if __name__ == "__main__":
    main()
