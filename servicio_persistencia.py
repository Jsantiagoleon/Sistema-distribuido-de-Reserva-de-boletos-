import argparse
import json
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime

import psycopg2
import zmq

import bd
import config
from modelos import (Evento, Ocurrencia, Respuesta, Solicitud,
                     ACTIVA, CANCELADA, EXITO, RECHAZADO, ERROR)

TRANSACCIONES_ENTRE_LIMPIEZAS = 200


def log(componente, texto):
    print(f"{datetime.now():%H:%M:%S.%f}"[:-3] + f"  {componente:<6} {texto}", flush=True)


def cargar_eventos(datos_eventos):
    eventos = {}
    for id_evento, e in datos_eventos.items():
        ocurrencias = [Ocurrencia(o["numero"], date.fromisoformat(o["fecha"]),
                                  o["asientos_disponibles"], o["asientos_libres"],
                                  o["asientos_ocupados"])
                       for o in e["ocurrencias"]]
        eventos[id_evento] = Evento(id_evento, e["num_ocurrencias"], ocurrencias)
    return eventos


class VistaEventos:

    def __init__(self):
        self.eventos = {}

    def consultar_mes(self, mes):
        return [e for e in self.eventos.values()
                if any(oc.fecha.month == mes for oc in e.ocurrencias)]

    def buscar_ocurrencia(self, id_evento, num_ocurrencia):
        evento = self.eventos.get(id_evento)
        if evento is None:
            return None
        for oc in evento.ocurrencias:
            if oc.numero == num_ocurrencia:
                return oc
        return None


def _entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


class ServicioPersistencia:

    def __init__(self):
        self.conn = None
        self.respuestas = {}
        self.escrituras = 0
        self.seq = 0
        self.epoca = time.time_ns()

        with self._transaccion() as cur:
            if not bd.existe_esquema(self.conn):
                raise SystemExit("La base de datos no tiene las tablas del SRB. "
                                 "Ejecute primero: python3 generar_bd.py")
            cur.execute("SELECT count(*) FROM ocurrencias")
            self.num_ocurrencias = cur.fetchone()[0]

        contexto = zmq.Context()
        self.sock_rep = contexto.socket(zmq.REP)
        self.sock_rep.bind(f"tcp://*:{config.PUERTO_PERSISTENCIA}")
        self.sock_deltas = contexto.socket(zmq.PUB)
        self.sock_deltas.bind(f"tcp://*:{config.PUERTO_REPLICA_PUB}")

    @contextmanager
    def _transaccion(self):
        if self.conn is None or self.conn.closed:
            self.conn = bd.conectar()
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except BaseException:
            try:
                self.conn.rollback()
            except Exception:
                self.conn = None
            raise
        finally:
            cur.close()

    def _valida_asientos(self, asientos):
        return _entero(asientos) and 1 <= asientos <= config.ASIENTOS_POR_OCURRENCIA

    def _recordar(self, id_solicitud, respuesta):
        self.respuestas[id_solicitud] = asdict(respuesta)
        while len(self.respuestas) > config.MAX_SOLICITUDES_GUARDADAS:
            self.respuestas.pop(next(iter(self.respuestas)))

    def _repetida(self, cur, solicitud):
        clave = str(solicitud.id_solicitud)
        guardada = self.respuestas.get(clave)
        if guardada is None:
            cur.execute("SELECT respuesta FROM solicitudes_procesadas WHERE id_solicitud = %s", (clave,))
            fila = cur.fetchone()
            guardada = fila[0] if fila else None
        return None if guardada is None else Respuesta(**guardada)

    def _ajustar(self, cur, id_evento, numero, delta_libres):
        cur.execute("""UPDATE ocurrencias
                          SET asientos_libres = asientos_libres + %s,
                              asientos_ocupados = asientos_ocupados - %s
                        WHERE id_evento = %s AND numero = %s
                          AND asientos_libres + %s >= 0 AND asientos_ocupados - %s >= 0
                    RETURNING asientos_libres, asientos_ocupados""",
                    (delta_libres, delta_libres, id_evento, numero, delta_libres, delta_libres))
        fila = cur.fetchone()
        return None if fila is None else (id_evento, numero, fila[0], fila[1])

    def _escribir(self, solicitud, logica):
        with self._transaccion() as cur:
            guardada = self._repetida(cur, solicitud)
            if guardada is not None:
                return guardada
            respuesta, cambiadas = logica(cur, solicitud)
            if respuesta.estado == EXITO:
                cur.execute("INSERT INTO solicitudes_procesadas (id_solicitud, respuesta) VALUES (%s, %s)",
                            (str(solicitud.id_solicitud), json.dumps(asdict(respuesta), default=str)))
                self.escrituras += 1
                if self.escrituras % TRANSACCIONES_ENTRE_LIMPIEZAS == 0:
                    cur.execute("DELETE FROM solicitudes_procesadas WHERE orden <= "
                                "(SELECT max(orden) FROM solicitudes_procesadas) - %s",
                                (config.MAX_SOLICITUDES_GUARDADAS,))
        self._recordar(str(solicitud.id_solicitud), respuesta)
        if respuesta.estado == EXITO:
            self.seq += 1
            self.sock_deltas.send_string(json.dumps({
                "epoca": self.epoca, "seq": self.seq,
                "ocurrencias": [{"id_evento": ide, "numero": num,
                                 "asientos_libres": libres, "asientos_ocupados": ocupados}
                                for ide, num, libres, ocupados in cambiadas]}))
        return respuesta

    def consultar_mes(self, mes):
        with self._transaccion() as cur:
            if not _entero(mes):
                return []
            return list(bd.leer_eventos(cur, mes).values())

    def consultar_disponibilidad_solicitud(self, solicitud):
        with self._transaccion() as cur:
            guardada = self._repetida(cur, solicitud)
            if guardada is not None:
                return Respuesta(guardada.id_solicitud, guardada.estado,
                                 {**guardada.datos, "repetida": True})
            libres = None
            if isinstance(solicitud.id_evento, str) and _entero(solicitud.num_ocurrencia):
                cur.execute("SELECT asientos_libres FROM ocurrencias WHERE id_evento = %s AND numero = %s",
                            (solicitud.id_evento, solicitud.num_ocurrencia))
                fila = cur.fetchone()
                libres = None if fila is None else fila[0]
        if libres is None:
            return Respuesta(solicitud.id_solicitud, ERROR,
                             {"motivo": "evento u ocurrencia inexistente"})
        return Respuesta(solicitud.id_solicitud, EXITO, {"libres": libres})

    def confirmar_reserva(self, solicitud):
        def logica(cur, s):
            if (not isinstance(s.id_evento, str) or not _entero(s.num_ocurrencia)
                    or not self._valida_asientos(s.asientos)):
                return Respuesta(s.id_solicitud, ERROR,
                                 {"motivo": "evento, ocurrencia o asientos inválidos"}), []
            cur.execute("""UPDATE ocurrencias
                              SET asientos_libres = asientos_libres - %s,
                                  asientos_ocupados = asientos_ocupados + %s
                            WHERE id_evento = %s AND numero = %s AND asientos_libres >= %s
                        RETURNING asientos_libres, asientos_ocupados""",
                        (s.asientos, s.asientos, s.id_evento, s.num_ocurrencia, s.asientos))
            fila = cur.fetchone()
            if fila is None:
                cur.execute("SELECT asientos_libres FROM ocurrencias WHERE id_evento = %s AND numero = %s",
                            (s.id_evento, s.num_ocurrencia))
                existente = cur.fetchone()
                if existente is None:
                    return Respuesta(s.id_solicitud, ERROR,
                                     {"motivo": "evento, ocurrencia o asientos inválidos"}), []
                return Respuesta(s.id_solicitud, RECHAZADO,
                                 {"motivo": "sin cupo", "libres": existente[0]}), []
            libres, ocupados = fila
            cur.execute("""INSERT INTO reservas (id_reserva, id_cliente, asientos, id_evento, num_ocurrencia)
                           VALUES ('R' || nextval('reservas_seq'), %s, %s, %s, %s) RETURNING id_reserva""",
                        (str(s.id_cliente), s.asientos, s.id_evento, s.num_ocurrencia))
            id_reserva = cur.fetchone()[0]
            return (Respuesta(s.id_solicitud, EXITO,
                              {"id_reserva": id_reserva, "id_evento": s.id_evento,
                               "num_ocurrencia": s.num_ocurrencia, "asientos": s.asientos,
                               "libres": libres}),
                    [(s.id_evento, s.num_ocurrencia, libres, ocupados)])
        return self._escribir(solicitud, logica)

    def _leer_reserva(self, cur, id_reserva):
        if not isinstance(id_reserva, str):
            return None
        cur.execute("""SELECT id_reserva, id_cliente, asientos, id_evento, num_ocurrencia, estado
                         FROM reservas WHERE id_reserva = %s FOR UPDATE""", (id_reserva,))
        fila = cur.fetchone()
        if fila is None:
            return None
        return dict(zip(("id_reserva", "id_cliente", "asientos", "id_evento", "num_ocurrencia", "estado"), fila))

    def modificar_reserva(self, solicitud):
        def logica(cur, s):
            def resp(estado, datos):
                return Respuesta(s.id_solicitud, estado, datos)

            reserva = self._leer_reserva(cur, s.id_reserva)
            if reserva is None:
                return resp(ERROR, {"motivo": "reserva inexistente"}), []
            if reserva["id_cliente"] != s.id_cliente:
                return resp(RECHAZADO, {"motivo": "la reserva pertenece a otro cliente"}), []
            if reserva["estado"] != ACTIVA:
                return resp(RECHAZADO, {"motivo": "la reserva está cancelada"}), []
            if (s.asientos is None) == (s.num_ocurrencia is None):
                return resp(ERROR, {"motivo": "indique solo asientos o solo num_ocurrencia"}), []

            cur.execute("SELECT numero, asientos_libres FROM ocurrencias WHERE id_evento = %s "
                        "ORDER BY numero FOR UPDATE", (reserva["id_evento"],))
            libres_de = dict(cur.fetchall())
            actual = reserva["num_ocurrencia"]

            if s.asientos is not None:
                if not self._valida_asientos(s.asientos):
                    return resp(ERROR, {"motivo": "asientos inválidos"}), []
                diferencia = s.asientos - reserva["asientos"]
                if diferencia == 0:
                    return resp(RECHAZADO, {"motivo": "sin cambios"}), []
                if diferencia > libres_de[actual]:
                    return resp(RECHAZADO, {"motivo": "sin cupo", "libres": libres_de[actual]}), []
                cambio = self._ajustar(cur, reserva["id_evento"], actual, -diferencia)
                cur.execute("UPDATE reservas SET asientos = %s WHERE id_reserva = %s",
                            (s.asientos, reserva["id_reserva"]))
                return (resp(EXITO, {"id_reserva": reserva["id_reserva"], "asientos": s.asientos,
                                     "num_ocurrencia": actual, "libres": cambio[2]}), [cambio])

            if len(libres_de) < 2:
                return resp(RECHAZADO, {"motivo": "el evento tiene una sola ocurrencia"}), []
            if not _entero(s.num_ocurrencia) or s.num_ocurrencia not in libres_de:
                return resp(ERROR, {"motivo": "ocurrencia inexistente"}), []
            if s.num_ocurrencia == actual:
                return resp(RECHAZADO, {"motivo": "la reserva ya está en esa ocurrencia"}), []
            if libres_de[s.num_ocurrencia] < reserva["asientos"]:
                return resp(RECHAZADO, {"motivo": "sin cupo", "libres": libres_de[s.num_ocurrencia]}), []
            origen = self._ajustar(cur, reserva["id_evento"], actual, +reserva["asientos"])
            destino = self._ajustar(cur, reserva["id_evento"], s.num_ocurrencia, -reserva["asientos"])
            cur.execute("UPDATE reservas SET num_ocurrencia = %s WHERE id_reserva = %s",
                        (s.num_ocurrencia, reserva["id_reserva"]))
            return (resp(EXITO, {"id_reserva": reserva["id_reserva"], "asientos": reserva["asientos"],
                                 "num_ocurrencia": s.num_ocurrencia, "libres": destino[2]}),
                    [origen, destino])
        return self._escribir(solicitud, logica)

    def cancelar_reserva(self, solicitud):
        def logica(cur, s):
            reserva = self._leer_reserva(cur, s.id_reserva)
            if reserva is None:
                return Respuesta(s.id_solicitud, ERROR, {"motivo": "reserva inexistente"}), []
            if reserva["id_cliente"] != s.id_cliente:
                return Respuesta(s.id_solicitud, RECHAZADO,
                                 {"motivo": "la reserva pertenece a otro cliente"}), []
            if reserva["estado"] == CANCELADA:
                return Respuesta(s.id_solicitud, RECHAZADO,
                                 {"motivo": "la reserva ya estaba cancelada"}), []
            cambio = self._ajustar(cur, reserva["id_evento"], reserva["num_ocurrencia"], +reserva["asientos"])
            cur.execute("UPDATE reservas SET estado = %s WHERE id_reserva = %s", (CANCELADA, reserva["id_reserva"]))
            return (Respuesta(s.id_solicitud, EXITO,
                              {"id_reserva": reserva["id_reserva"], "liberados": reserva["asientos"],
                               "libres": cambio[2]}), [cambio])
        return self._escribir(solicitud, logica)

    def snapshot(self):
        with self._transaccion() as cur:
            eventos = bd.leer_eventos(cur)
        return Respuesta("snapshot", EXITO, {"epoca": self.epoca, "seq": self.seq, "eventos": eventos})

    def atender(self, mensaje):
        operacion, id_solicitud = "?", "?"
        try:
            datos = json.loads(mensaje)
            operacion = datos["operacion"]
            if operacion == "snapshot":
                return operacion, "-", self.snapshot()
            solicitud = Solicitud(**datos["solicitud"])
            id_solicitud = solicitud.id_solicitud

            if operacion == "consultar_mes":
                respuesta = Respuesta(id_solicitud, EXITO,
                                      {"eventos": self.consultar_mes(solicitud.mes)})
            elif operacion == "consultar_disponibilidad":
                respuesta = self.consultar_disponibilidad_solicitud(solicitud)
            elif operacion == "confirmar_reserva":
                respuesta = self.confirmar_reserva(solicitud)
            elif operacion == "modificar_reserva":
                respuesta = self.modificar_reserva(solicitud)
            elif operacion == "cancelar_reserva":
                respuesta = self.cancelar_reserva(solicitud)
            else:
                respuesta = Respuesta(id_solicitud, ERROR, {"motivo": "operación desconocida"})
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            self.conn = None
            self.seq += 1
            log("PER", f"base de datos no disponible: {str(e).strip().splitlines()[0] if str(e).strip() else e}")
            respuesta = Respuesta(id_solicitud, ERROR,
                                  {"motivo": "base de datos no disponible", "reintentar": True})
        except Exception as e:
            respuesta = Respuesta(id_solicitud, ERROR, {"motivo": f"mensaje inválido: {e}"})
        return operacion, id_solicitud, respuesta


def main_principal():
    try:
        servicio = ServicioPersistencia()
    except psycopg2.Error as e:
        raise SystemExit(f"No se pudo conectar a PostgreSQL en {config.PG_HOST}:{config.PG_PUERTO} "
                         f"(base '{config.PG_BD}', usuario '{config.PG_USUARIO}'): {e}")
    log("PER", f"PostgreSQL {config.PG_HOST}:{config.PG_PUERTO}/{config.PG_BD} · "
               f"{servicio.num_ocurrencias} ocurrencias")
    log("PER", f"ServicioPersistencia escuchando en :{config.PUERTO_PERSISTENCIA} "
               f"(deltas para la réplica en :{config.PUERTO_REPLICA_PUB})")
    while True:
        mensaje = servicio.sock_rep.recv_string()
        inicio = time.perf_counter()
        operacion, id_solicitud, respuesta = servicio.atender(mensaje)
        servicio.sock_rep.send_string(json.dumps(asdict(respuesta), default=str))
        tiempo = time.perf_counter() - inicio
        log("PER", f"{operacion:<25} {id_solicitud:<17} {respuesta.estado:<10} {tiempo:.4f} s")


class ReplicaLectura(VistaEventos):

    def __init__(self):
        super().__init__()
        self.ctx = zmq.Context()
        self.seq = 0
        self.epoca = None
        self.sock_sub = self.ctx.socket(zmq.SUB)
        self.sock_sub.setsockopt_string(zmq.SUBSCRIBE, "")
        self.sock_sub.connect(config.DIR_REPLICA_PUB)
        self.sock_rep = self.ctx.socket(zmq.REP)
        self.sock_rep.bind(f"tcp://*:{config.PUERTO_REPLICA_LECTURA}")
        self.sincronizar()

    def sincronizar(self):
        while True:
            sock = self.ctx.socket(zmq.REQ)
            sock.setsockopt(zmq.RCVTIMEO, config.TIMEOUT_PERSISTENCIA_MS)
            sock.setsockopt(zmq.LINGER, 0)
            sock.connect(config.DIR_PERSISTENCIA)
            try:
                sock.send_string(json.dumps({"operacion": "snapshot"}))
                respuesta = Respuesta(**json.loads(sock.recv_string()))
                self.eventos = cargar_eventos(respuesta.datos["eventos"])
                self.seq = respuesta.datos["seq"]
                self.epoca = respuesta.datos["epoca"]
                log("REP", f"snapshot recibido (seq {self.seq}, {len(self.eventos)} eventos)")
                return
            except zmq.Again:
                log("REP", "la principal no responde; reintentando snapshot")
            finally:
                sock.close()

    def aplicar_delta(self, delta):
        if delta["epoca"] != self.epoca:
            log("REP", "la principal se reinició: se pide un snapshot nuevo")
            self.sincronizar()
            return
        if delta["seq"] <= self.seq:
            return
        if delta["seq"] != self.seq + 1:
            log("REP", f"salto de seq ({self.seq} -> {delta['seq']}): se pide un snapshot nuevo")
            self.sincronizar()
            return
        for o in delta["ocurrencias"]:
            oc = self.buscar_ocurrencia(o["id_evento"], o["numero"])
            if oc is not None:
                oc.asientos_libres = o["asientos_libres"]
                oc.asientos_ocupados = o["asientos_ocupados"]
        self.seq = delta["seq"]

    def atender(self, mensaje):
        id_solicitud = "?"
        try:
            datos = json.loads(mensaje)
            solicitud = Solicitud(**datos["solicitud"])
            id_solicitud = solicitud.id_solicitud
            if datos["operacion"] != "consultar_mes":
                return id_solicitud, Respuesta(id_solicitud, ERROR,
                                               {"motivo": "la réplica solo atiende consultar_mes"})
            eventos = self.consultar_mes(solicitud.mes)
            return id_solicitud, Respuesta(id_solicitud, EXITO,
                                           {"eventos": [asdict(e) for e in eventos],
                                            "replica": True, "seq": self.seq})
        except Exception as e:
            return id_solicitud, Respuesta(id_solicitud, ERROR, {"motivo": f"mensaje inválido: {e}"})


def main_replica():
    replica = ReplicaLectura()
    log("REP", f"Réplica de lectura escuchando en :{config.PUERTO_REPLICA_LECTURA} "
               f"· deltas desde {config.DIR_REPLICA_PUB}")
    poller = zmq.Poller()
    poller.register(replica.sock_sub, zmq.POLLIN)
    poller.register(replica.sock_rep, zmq.POLLIN)
    while True:
        eventos = dict(poller.poll())
        if replica.sock_sub in eventos:
            while True:
                try:
                    replica.aplicar_delta(json.loads(replica.sock_sub.recv_string(zmq.NOBLOCK)))
                except zmq.Again:
                    break
        if replica.sock_rep in eventos:
            inicio = time.perf_counter()
            mensaje = replica.sock_rep.recv_string()
            id_solicitud, respuesta = replica.atender(mensaje)
            replica.sock_rep.send_string(json.dumps(asdict(respuesta), default=str))
            log("REP", f"{'consultar_mes':<25} {id_solicitud:<17} {respuesta.estado:<10} "
                       f"{time.perf_counter() - inicio:.4f} s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servicio de Persistencia del SRB")
    parser.add_argument("--rol", choices=["principal", "replica"], default="principal")
    args = parser.parse_args()
    if args.rol == "principal":
        main_principal()
    else:
        main_replica()
