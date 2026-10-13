"""
ServicioPersistencia · VM3

REP bind :5555 <- ServicioRMC y ServicioCancelaciones (REQ)

Recibe mensajes JSON de la forma {"operacion": ..., "solicitud": {...}} con
operacion = consultar_mes | consultar_disponibilidad | confirmar_reserva,
y responde con una Respuesta en JSON.

Uso: python3 servicio_persistencia.py
"""

import json
import os
import time
from dataclasses import asdict
from datetime import date, datetime

import zmq

import config
from modelos import Evento, Ocurrencia, Reserva, Respuesta, Solicitud, EXITO, RECHAZADO, ERROR


class ServicioPersistencia:

    def __init__(self):
        # Carga events.json (creado con generar_bd.py)
        with open(config.RUTA_BD, "r", encoding="utf-8") as f:
            bd = json.load(f)

        self.eventos = {}                    # composición: gestiona 50 Evento
        for id_evento, e in bd["eventos"].items():
            ocurrencias = [Ocurrencia(o["numero"], date.fromisoformat(o["fecha"]),
                                      o["asientos_disponibles"], o["asientos_libres"],
                                      o["asientos_ocupados"])
                           for o in e["ocurrencias"]]
            self.eventos[id_evento] = Evento(id_evento, e["num_ocurrencias"], ocurrencias)

        self.reservas = {k: Reserva(**r) for k, r in bd["reservas"].items()}   # 0..* Reserva
        self.solicitudes_procesadas = bd["solicitudes_procesadas"]  # id_solicitud -> respuesta

        contexto = zmq.Context()
        self.sock_rep = contexto.socket(zmq.REP)
        self.sock_rep.bind(f"tcp://*:{config.PUERTO_PERSISTENCIA}")

    def consultar_mes(self, mes):
        """Devuelve los eventos que tienen al menos una ocurrencia en el mes."""
        return [e for e in self.eventos.values()
                if any(oc.fecha.month == mes for oc in e.ocurrencias)]

    def consultar_disponibilidad(self, id_evento, num_ocurrencia):
        """Devuelve los asientos libres de una ocurrencia, o None si no existe."""
        evento = self.eventos.get(id_evento)
        if evento is None:
            return None
        for oc in evento.ocurrencias:
            if oc.numero == num_ocurrencia:
                return oc.asientos_libres
        return None

    def confirmar_reserva(self, solicitud):
        """Vuelve a revisar el cupo y, si alcanza, crea la reserva y guarda events.json.
        Si el id_solicitud ya fue procesado, devuelve la respuesta guardada."""
        # Solicitud repetida: misma respuesta, sin descontar asientos otra vez
        if solicitud.id_solicitud in self.solicitudes_procesadas:
            return Respuesta(**self.solicitudes_procesadas[solicitud.id_solicitud])

        libres = self.consultar_disponibilidad(solicitud.id_evento, solicitud.num_ocurrencia)
        if libres is None or not isinstance(solicitud.asientos, int) \
                or not 1 <= solicitud.asientos <= config.ASIENTOS_POR_OCURRENCIA:
            respuesta = Respuesta(solicitud.id_solicitud, ERROR,
                                  {"motivo": "evento, ocurrencia o asientos inválidos"})
        elif libres < solicitud.asientos:
            respuesta = Respuesta(solicitud.id_solicitud, RECHAZADO,
                                  {"motivo": "sin cupo", "libres": libres})
        else:
            evento = self.eventos[solicitud.id_evento]
            oc = next(o for o in evento.ocurrencias if o.numero == solicitud.num_ocurrencia)
            oc.asientos_libres -= solicitud.asientos
            oc.asientos_ocupados += solicitud.asientos

            id_reserva = f"R{len(self.reservas) + 1}"
            self.reservas[id_reserva] = Reserva(id_reserva, solicitud.id_cliente, solicitud.asientos,
                                                solicitud.id_evento, solicitud.num_ocurrencia)
            respuesta = Respuesta(solicitud.id_solicitud, EXITO,
                                  {"id_reserva": id_reserva, "libres": oc.asientos_libres})

        self.solicitudes_procesadas[solicitud.id_solicitud] = asdict(respuesta)

        # Guarda en un archivo temporal y lo reemplaza con os.replace(), para que
        # events.json no quede dañado si el proceso se cae a mitad de la escritura
        bd = {
            "eventos": {k: asdict(e) for k, e in self.eventos.items()},
            "reservas": {k: asdict(r) for k, r in self.reservas.items()},
            "solicitudes_procesadas": self.solicitudes_procesadas,
        }
        temporal = config.RUTA_BD + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(bd, f, ensure_ascii=False, indent=2, default=str)
        os.replace(temporal, config.RUTA_BD)

        return respuesta


def main():
    servicio = ServicioPersistencia()
    print(f"ServicioPersistencia escuchando en :{config.PUERTO_PERSISTENCIA}", flush=True)

    while True:
        mensaje = servicio.sock_rep.recv_string()
        inicio = time.perf_counter()
        operacion, id_solicitud = "?", "?"
        try:
            datos = json.loads(mensaje)
            operacion = datos["operacion"]
            solicitud = Solicitud(**datos["solicitud"])
            id_solicitud = solicitud.id_solicitud

            if operacion == "consultar_mes":
                eventos = servicio.consultar_mes(solicitud.mes)
                respuesta = Respuesta(id_solicitud, EXITO,
                                      {"eventos": [asdict(e) for e in eventos]})
            elif operacion == "consultar_disponibilidad":
                libres = servicio.consultar_disponibilidad(solicitud.id_evento,
                                                           solicitud.num_ocurrencia)
                respuesta = (Respuesta(id_solicitud, ERROR, {"motivo": "evento u ocurrencia inexistente"})
                             if libres is None else Respuesta(id_solicitud, EXITO, {"libres": libres}))
            elif operacion == "confirmar_reserva":
                respuesta = servicio.confirmar_reserva(solicitud)
            else:
                respuesta = Respuesta(id_solicitud, ERROR, {"motivo": "operación desconocida"})
        except Exception as e:
            # Mensaje malformado: se responde ERROR y el servicio sigue funcionando
            respuesta = Respuesta(id_solicitud, ERROR, {"motivo": f"mensaje inválido: {e}"})

        servicio.sock_rep.send_string(json.dumps(asdict(respuesta), default=str))

        tiempo = time.perf_counter() - inicio
        print(f"{datetime.now():%H:%M:%S.%f}"[:-3] +
              f"  PER    {operacion:<25} {id_solicitud:<10} {respuesta.estado:<10} {tiempo:.4f} s",
              flush=True)


if __name__ == "__main__":
    main()