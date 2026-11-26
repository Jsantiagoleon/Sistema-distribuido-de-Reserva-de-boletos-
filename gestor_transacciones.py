import argparse
import json
import os
import time
from datetime import datetime

import zmq

import config


def log(texto):
    print(f"{datetime.now():%H:%M:%S.%f}"[:-3] + f"  GT     {texto}", flush=True)


class ReplicaRMC:

    def __init__(self, ctx, host, indice):
        self.nombre = f"RMC-{indice}@{host}" if host != config.IP_VM2 else f"RMC-{indice}"
        self.dir = f"tcp://{host}:{config.puerto_rmc(indice)}"
        self.dir_latido = f"tcp://{host}:{config.puerto_latido_rmc(indice)}"
        self.sock = ctx.socket(zmq.DEALER)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.connect(self.dir)
        self.sock_latido = ctx.socket(zmq.SUB)
        self.sock_latido.setsockopt_string(zmq.SUBSCRIBE, "")
        self.sock_latido.connect(self.dir_latido)
        self.viva = True
        self.ultimo_latido = time.monotonic()


class GestorTransacciones:

    def __init__(self, rol, puerto, rmc, par, dir_cancelaciones):
        self.rol = rol
        self.puerto = puerto
        self.ctx = zmq.Context()
        self.activo = False
        self.pasivo_anunciado = False
        self.sock_sync = None
        self.sock_async = None

        self.sock_pub = self.ctx.socket(zmq.PUB)
        self.sock_pub.bind(f"tcp://*:{puerto + 4}")
        self.sock_par = self.ctx.socket(zmq.SUB)
        self.sock_par.setsockopt_string(zmq.SUBSCRIBE, "")
        self.sock_par.connect(f"tcp://{par[0]}:{par[1] + 4}")
        self.par_activo_desde = None
        self.sock_cancelaciones = self.ctx.socket(zmq.PUSH)
        self.sock_cancelaciones.connect(dir_cancelaciones)

        self.replicas = [ReplicaRMC(self.ctx, host, i) for host, i in rmc]
        self.turno = 0
        self.en_curso = {}
        self.en_espera = []
        self.poller = zmq.Poller()
        self.poller.register(self.sock_par, zmq.POLLIN)
        for r in self.replicas:
            self.poller.register(r.sock, zmq.POLLIN)
            self.poller.register(r.sock_latido, zmq.POLLIN)

        os.makedirs(config.DIR_RESULTADOS, exist_ok=True)
        self.f_metricas = open(os.path.join(config.DIR_RESULTADOS, "gt_metricas.csv"), "a", buffering=1)
        if self.f_metricas.tell() == 0:
            self.f_metricas.write("hora,tipo,tiempo_s\n")
        self.f_eventos = open(os.path.join(config.DIR_RESULTADOS, "gt_eventos.csv"), "a", buffering=1)
        if self.f_eventos.tell() == 0:
            self.f_eventos.write("hora,evento,detalle\n")

    def evento(self, nombre, detalle=""):
        self.f_eventos.write(f"{time.time():.3f},{nombre},{detalle}\n")

    def registrar_metrica(self, tipo, tiempo):
        self.f_metricas.write(f"{time.time():.3f},{tipo},{tiempo:.6f}\n")

    def activar(self, motivo):
        self.sock_sync = self.ctx.socket(zmq.ROUTER)
        self.sock_sync.setsockopt(zmq.LINGER, 0)
        self.sock_sync.bind(f"tcp://*:{self.puerto}")
        self.sock_async = self.ctx.socket(zmq.ROUTER)
        self.sock_async.setsockopt(zmq.LINGER, 0)
        self.sock_async.bind(f"tcp://*:{self.puerto + 1}")
        self.poller.register(self.sock_sync, zmq.POLLIN)
        self.poller.register(self.sock_async, zmq.POLLIN)
        self.activo = True
        self.pasivo_anunciado = False
        self.ultimo_latido_enviado = 0.0
        log(f"*** GT {self.rol.upper()} ACTIVO: {motivo}. Atiende clientes en :{self.puerto} "
            f"(síncrono) y :{self.puerto + 1} (asíncrono)")
        self.evento("gt_activo", f"{self.rol}|{motivo}")

    def desactivar(self, motivo):
        for s in (self.sock_sync, self.sock_async):
            self.poller.unregister(s)
            s.close()
        self.sock_sync = self.sock_async = None
        self.en_curso.clear()
        self.en_espera.clear()
        self.activo = False
        self.pasivo_anunciado = True
        self.par_activo_desde = time.monotonic()
        log(f"*** GT {self.rol.upper()} PASIVO: {motivo}")
        self.evento("gt_pasivo", f"{self.rol}|{motivo}")

    def atender_latido_par(self):
        par_activo = False
        while True:
            try:
                datos = json.loads(self.sock_par.recv_string(zmq.NOBLOCK))
            except zmq.Again:
                break
            if datos.get("activo"):
                par_activo = True
                self.par_activo_desde = time.monotonic()
        return par_activo

    def elegir_replica(self):
        for _ in range(len(self.replicas)):
            r = self.replicas[self.turno % len(self.replicas)]
            self.turno += 1
            if r.viva:
                return r
        return None

    def enrutar_sincrono(self, frames, tipo, id_solicitud, inicio):
        pendiente = {"inicio": inicio, "tipo": tipo, "id": id_solicitud, "frames": frames, "replica": None}
        self.en_curso[frames[0]] = pendiente
        self.enviar_a_replica(pendiente)

    def enviar_a_replica(self, pendiente):
        replica = self.elegir_replica()
        if replica is None:
            pendiente["replica"] = None
            self.en_espera.append(pendiente)
            return
        pendiente["replica"] = replica
        replica.sock.send_multipart(pendiente["frames"])

    def entregar_respuesta(self, replica, frames):
        pendiente = self.en_curso.get(frames[0])
        try:
            datos = json.loads(frames[-1])
            estado, id_resp = datos.get("estado", "?"), datos.get("id_solicitud")
        except Exception:
            estado, id_resp = "?", None
        if pendiente is None or id_resp != pendiente["id"]:
            return
        del self.en_curso[frames[0]]
        self.sock_sync.send_multipart(frames)

        tiempo = time.perf_counter() - pendiente["inicio"]
        self.registrar_metrica(pendiente["tipo"] if estado in ("EXITO", "RECHAZADO") else "error", tiempo)
        log(f"{pendiente['tipo']:<13} {pendiente['id']:<17} {estado:<10} {tiempo:.4f} s  ({replica.nombre})")

    def aceptar_cancelacion(self, frames):
        inicio = time.perf_counter()
        try:
            solicitud = json.loads(frames[-1])
            id_solicitud = solicitud["id_solicitud"]
        except Exception:
            self.sock_async.send_multipart([frames[0], json.dumps(
                {"id_solicitud": "?", "estado": "ERROR", "datos": {"motivo": "mensaje inválido"}}).encode()])
            return
        self.sock_cancelaciones.send_string(json.dumps(solicitud))
        self.sock_async.send_multipart([frames[0], json.dumps(
            {"id_solicitud": id_solicitud, "estado": "ACEPTADA", "datos": {}}).encode()])
        tiempo = time.perf_counter() - inicio
        self.registrar_metrica("cancelacion", tiempo)
        log(f"{'cancelacion':<13} {id_solicitud:<17} {'ACEPTADA':<10} {tiempo:.4f} s  (-> Cancelaciones)")

    def revisar_replicas(self):
        ahora = time.monotonic()
        for r in self.replicas:
            while True:
                try:
                    r.sock_latido.recv_string(zmq.NOBLOCK)
                    r.ultimo_latido = ahora
                    if not r.viva:
                        r.viva = True
                        r.sock.connect(r.dir)
                        log(f"{r.nombre} volvió a emitir latidos: se reincorpora al reparto")
                        self.evento("rmc_recuperada", r.nombre)
                        self.vaciar_espera()
                except zmq.Again:
                    break
            if r.viva and ahora - r.ultimo_latido > config.TIMEOUT_LATIDO_RMC_MS / 1000:
                r.viva = False
                r.sock.disconnect(r.dir)
                reasignar = [p for p in self.en_curso.values() if p["replica"] is r]
                log(f"!!! {r.nombre} sin latidos hace {ahora - r.ultimo_latido:.1f} s: se da por CAÍDA. "
                    f"Reasigna {len(reasignar)} solicitud(es) en curso")
                self.evento("rmc_caida", f"{r.nombre}|reasignadas={len(reasignar)}")
                for p in reasignar:
                    self.enviar_a_replica(p)

    def vaciar_espera(self):
        espera, self.en_espera = self.en_espera, []
        for p in espera:
            if p["frames"][0] in self.en_curso:
                self.enviar_a_replica(p)

    def limpiar(self):
        limite = time.perf_counter() - 30
        for ident in [i for i, p in self.en_curso.items() if p["inicio"] < limite]:
            del self.en_curso[ident]
        self.en_espera = [p for p in self.en_espera if p["frames"][0] in self.en_curso]

    def ejecutar(self):
        espera_inicial = (config.ESPERA_INICIAL_PRINCIPAL_MS if self.rol == "principal"
                          else config.ESPERA_INICIAL_RESPALDO_MS) / 1000
        arranque = time.monotonic()
        ultimo_limpiar = ultimo_replicas = time.monotonic()
        log(f"GT {self.rol} arrancó: escucha {espera_inicial:.1f} s al otro GT antes de decidir su rol. "
            f"Réplicas RMC: {', '.join(r.nombre for r in self.replicas)}")

        while True:
            eventos = dict(self.poller.poll(100))
            ahora = time.monotonic()

            par_activo = self.atender_latido_par()
            if not self.activo:
                if par_activo and not self.pasivo_anunciado:
                    self.pasivo_anunciado = True
                    log(f"*** GT {self.rol.upper()} PASIVO: el otro GT ya está activo; "
                        f"vigila sus latidos (asume el rol si faltan "
                        f"{config.TIMEOUT_LATIDO_GT_MS / 1000:.0f} s)")
                    self.evento("gt_pasivo", f"{self.rol}|el otro GT ya esta activo")
                if self.par_activo_desde is None:
                    if ahora - arranque > espera_inicial:
                        self.activar("no hay otro GT activo")
                elif ahora - self.par_activo_desde > config.TIMEOUT_LATIDO_GT_MS / 1000:
                    self.activar(f"{ahora - self.par_activo_desde:.1f} s sin latidos del otro GT: "
                                 f"se asume su rol (falla detectada)")
                    self.par_activo_desde = None
            elif par_activo and self.rol == "respaldo":
                self.desactivar("el GT principal está activo")

            if self.activo and ahora - self.ultimo_latido_enviado >= config.INTERVALO_LATIDO_MS / 1000:
                self.sock_pub.send_string(json.dumps({"gt": self.rol, "activo": True, "t": ahora}))
                self.ultimo_latido_enviado = ahora

            if self.activo:
                if self.sock_sync in eventos:
                    frames = self.sock_sync.recv_multipart()
                    try:
                        datos = json.loads(frames[-1])
                        tipo, id_solicitud = datos.get("tipo", "?"), datos.get("id_solicitud", "?")
                    except Exception:
                        tipo, id_solicitud = "?", "?"
                    self.enrutar_sincrono(frames, tipo, id_solicitud, time.perf_counter())

                if self.sock_async in eventos:
                    self.aceptar_cancelacion(self.sock_async.recv_multipart())

                for r in self.replicas:
                    if r.sock in eventos:
                        while True:
                            try:
                                self.entregar_respuesta(r, r.sock.recv_multipart(zmq.NOBLOCK))
                            except zmq.Again:
                                break

            if ahora - ultimo_replicas >= 0.2:
                self.revisar_replicas()
                ultimo_replicas = ahora
            if ahora - ultimo_limpiar >= 5:
                self.limpiar()
                ultimo_limpiar = ahora
            if not self.activo:
                for r in self.replicas:
                    while r.sock in eventos:
                        try:
                            r.sock.recv_multipart(zmq.NOBLOCK)
                        except zmq.Again:
                            break


def analizar_host_indice(texto):
    host, indice = texto.rsplit(":", 1)
    return host, int(indice)


def main():
    parser = argparse.ArgumentParser(description="Gestor de Transacciones del SRB")
    parser.add_argument("--rol", choices=["principal", "respaldo"], default="principal")
    parser.add_argument("--puerto", type=int, default=config.PUERTO_GT,
                        help="puerto del canal síncrono; el asíncrono usa +1 y el latido +4")
    parser.add_argument("--replicas", type=int, default=1,
                        help="réplicas del RMC en la VM2 (índices 0 .. N-1)")
    parser.add_argument("--rmc", action="append", default=[], metavar="HOST:INDICE",
                        help="réplica adicional del RMC en otra máquina (se puede repetir)")
    parser.add_argument("--par", metavar="HOST:PUERTO",
                        help="dirección del otro GT (por defecto: VM3 si es principal, VM2 si es respaldo)")
    parser.add_argument("--cancelaciones", default=config.DIR_CANCELACIONES,
                        help="dirección PULL del Servicio de Cancelaciones")
    args = parser.parse_args()

    rmc = [(config.IP_VM2, i) for i in range(args.replicas)] + [analizar_host_indice(x) for x in args.rmc]
    if args.par:
        host, p = args.par.rsplit(":", 1)
        par = (host, int(p))
    else:
        par = (config.IP_VM3 if args.rol == "principal" else config.IP_VM2, config.PUERTO_GT)

    GestorTransacciones(args.rol, args.puerto, rmc, par, args.cancelaciones).ejecutar()


if __name__ == "__main__":
    main()
