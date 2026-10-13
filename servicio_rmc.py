"""
ServicioRMC · VM2

REP bind :5556         <- GestorTransacciones (DEALER)
REQ connect VM3:5555   -> ServicioPersistencia (REP)

Recibe una Solicitud en JSON (consulta o reserva), aplica las reglas del
negocio pidiendo los datos a Persistencia y devuelve una Respuesta en JSON.

Uso: python3 servicio_rmc.py
"""

import json
import time
from dataclasses import asdict
from datetime import datetime

import zmq

import config
from modelos import Respuesta, Solicitud, CONSULTA, RESERVA, EXITO, RECHAZADO, ERROR


class ServicioRMC:

    def __init__(self):
        contexto = zmq.Context()
        self.sock_gt = contexto.socket(zmq.REP)              # REP: atiende al GT
        self.sock_gt.bind(f"tcp://*:{config.PUERTO_RMC}")
        self.sock_persistencia = contexto.socket(zmq.REQ)    # REQ: pregunta a Persistencia
        self.sock_persistencia.connect(config.DIR_PERSISTENCIA)

    def procesar_consulta(self, solicitud):
        """Pide a Persistencia los eventos del mes y devuelve la Respuesta."""
        if not isinstance(solicitud.mes, int) or not 1 <= solicitud.mes <= 12:
            return Respuesta(solicitud.id_solicitud, ERROR, {"motivo": "mes inválido"})

        self.sock_persistencia.send_string(json.dumps(
            {"operacion": "consultar_mes", "solicitud": asdict(solicitud)}))
        return Respuesta(**json.loads(self.sock_persistencia.recv_string()))

    def procesar_reserva(self, solicitud):
        """Consulta disponibilidad y, si hay cupo, pide la confirmación a Persistencia."""
        # 1. Consultar disponibilidad
        self.sock_persistencia.send_string(json.dumps(
            {"operacion": "consultar_disponibilidad", "solicitud": asdict(solicitud)}))
        disponibilidad = Respuesta(**json.loads(self.sock_persistencia.recv_string()))

        if disponibilidad.estado == ERROR:
            return disponibilidad
        libres = disponibilidad.datos["libres"]
        if not isinstance(solicitud.asientos, int) or solicitud.asientos < 1:
            return Respuesta(solicitud.id_solicitud, ERROR, {"motivo": "asientos inválidos"})
        if libres < solicitud.asientos:
            return Respuesta(solicitud.id_solicitud, RECHAZADO,
                             {"motivo": "sin cupo", "libres": libres})

        # 2. Hay cupo: pedir la confirmación condicional (Persistencia revisa otra vez)
        self.sock_persistencia.send_string(json.dumps(
            {"operacion": "confirmar_reserva", "solicitud": asdict(solicitud)}))
        return Respuesta(**json.loads(self.sock_persistencia.recv_string()))

    def procesar_modificacion(self, solicitud):
        """Entrega 2."""
        pass


def main():
    servicio = ServicioRMC()
    print(f"ServicioRMC escuchando en :{config.PUERTO_RMC} · "
          f"Persistencia en {config.DIR_PERSISTENCIA}", flush=True)

    while True:
        mensaje = servicio.sock_gt.recv_string()
        inicio = time.perf_counter()
        tipo, id_solicitud = "?", "?"
        try:
            solicitud = Solicitud(**json.loads(mensaje))
            tipo, id_solicitud = solicitud.tipo, solicitud.id_solicitud

            if tipo == CONSULTA:
                respuesta = servicio.procesar_consulta(solicitud)
            elif tipo == RESERVA:
                respuesta = servicio.procesar_reserva(solicitud)
            else:
                respuesta = Respuesta(id_solicitud, ERROR, {"motivo": "tipo no soportado"})
        except Exception as e:
            # Mensaje malformado: se responde ERROR y el servicio sigue funcionando
            respuesta = Respuesta(id_solicitud, ERROR, {"motivo": f"mensaje inválido: {e}"})

        servicio.sock_gt.send_string(json.dumps(asdict(respuesta), default=str))

        tiempo = time.perf_counter() - inicio
        print(f"{datetime.now():%H:%M:%S.%f}"[:-3] +
              f"  RMC    {tipo:<25} {id_solicitud:<10} {respuesta.estado:<10} {tiempo:.4f} s",
              flush=True)


if __name__ == "__main__":
    main()