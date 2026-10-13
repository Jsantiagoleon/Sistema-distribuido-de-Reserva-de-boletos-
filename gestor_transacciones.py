"""
GestorTransacciones · VM2

ROUTER bind :5557     <- ClienteCarga (REQ)      · canal síncrono
DEALER connect :5556  -> ServicioRMC (REP)
ROUTER bind :5558     <- ClienteCarga (DEALER)   · cancelaciones (Entrega 2)
PUSH   bind :5559     -> ServicioCancelaciones   · (Entrega 2)

Recibe a todos los clientes por el ROUTER y reenvía cada solicitud al RMC por
el DEALER, sin bloquearse. Cuando vuelve la respuesta, la entrega al cliente
correcto usando la identidad que puso el ROUTER.

Uso: python3 gestor_transacciones.py
"""

import json
import os
import time
from datetime import datetime

import zmq

import config


class GestorTransacciones:

    def __init__(self):
        contexto = zmq.Context()
        self.sock_clientes_sync = contexto.socket(zmq.ROUTER)   # ROUTER: recibe a los clientes
        self.sock_clientes_sync.bind(f"tcp://*:{config.PUERTO_GT}")
        self.sock_clientes_async = None                          # ROUTER (Entrega 2)
        self.sock_rmc = contexto.socket(zmq.DEALER)             # DEALER: reenvía al RMC
        self.sock_rmc.connect(config.DIR_RMC)
        self.sock_cancelaciones = None                           # PUSH   (Entrega 2)

    def enrutar_sincrono(self, solicitud):
        """Reenvía al RMC una solicitud de consulta o reserva recibida de un cliente.
        'solicitud' es el mensaje completo [identidad, b"", json]: se envía tal cual,
        y la identidad vuelve pegada a la respuesta del RMC."""
        self.sock_rmc.send_multipart(solicitud)

    def aceptar_cancelacion(self, solicitud):
        """Entrega 2."""
        pass

    def registrar_metrica(self, tipo, tiempo):
        """Guarda en resultados/gt_metricas.csv una fila por solicitud completada
        (hora, tipo, tiempo de servicio en el GT). Con estas filas se calcula el TPM."""
        os.makedirs(config.DIR_RESULTADOS, exist_ok=True)
        ruta = os.path.join(config.DIR_RESULTADOS, "gt_metricas.csv")
        nuevo = not os.path.exists(ruta)
        with open(ruta, "a", encoding="utf-8") as f:
            if nuevo:
                f.write("hora,tipo,tiempo_s\n")
            f.write(f"{time.time():.3f},{tipo},{tiempo:.6f}\n")


def main():
    gestor = GestorTransacciones()
    print(f"GestorTransacciones escuchando en :{config.PUERTO_GT} · RMC en {config.DIR_RMC}",
          flush=True)

    # Atiende a los clientes y al RMC a la vez, sin quedarse bloqueado en ninguno
    poller = zmq.Poller()
    poller.register(gestor.sock_clientes_sync, zmq.POLLIN)
    poller.register(gestor.sock_rmc, zmq.POLLIN)

    # Solicitudes en curso: identidad del cliente -> (inicio, tipo, id_solicitud)
    en_curso = {}

    while True:
        eventos = dict(poller.poll())

        # 1. Llegó una solicitud de un cliente: [identidad, b"", json]
        if gestor.sock_clientes_sync in eventos:
            solicitud = gestor.sock_clientes_sync.recv_multipart()
            try:
                datos = json.loads(solicitud[-1])
                tipo, id_solicitud = datos.get("tipo", "?"), datos.get("id_solicitud", "?")
            except Exception:
                tipo, id_solicitud = "?", "?"
            en_curso[solicitud[0]] = (time.perf_counter(), tipo, id_solicitud)
            gestor.enrutar_sincrono(solicitud)

        # 2. Llegó la respuesta del RMC: [identidad, b"", json] -> al cliente correcto
        if gestor.sock_rmc in eventos:
            respuesta = gestor.sock_rmc.recv_multipart()
            gestor.sock_clientes_sync.send_multipart(respuesta)

            inicio, tipo, id_solicitud = en_curso.pop(respuesta[0], (time.perf_counter(), "?", "?"))
            tiempo = time.perf_counter() - inicio
            try:
                estado = json.loads(respuesta[-1]).get("estado", "?")
            except Exception:
                estado = "?"

            # El TPM cuenta las solicitudes completadas (EXITO o RECHAZADO);
            # los errores se registran aparte
            gestor.registrar_metrica(tipo if estado in ("EXITO", "RECHAZADO") else "error", tiempo)

            print(f"{datetime.now():%H:%M:%S.%f}"[:-3] +
                  f"  GT     {tipo:<25} {id_solicitud:<10} {estado:<10} {tiempo:.4f} s",
                  flush=True)


if __name__ == "__main__":
    main()