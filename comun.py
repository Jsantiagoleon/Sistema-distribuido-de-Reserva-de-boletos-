"""
Funciones compartidas: formato de mensajes y línea de log por operación.
"""

import time
from datetime import datetime

# Tipos de operación
CONSULTA = "consulta"
RESERVA = "reserva"

# Estados de una respuesta
EXITO = "EXITO"
RECHAZADO = "RECHAZADO"
ERROR = "ERROR"
SIN_RESPUESTA = "sin_respuesta"


def crear_solicitud(id_solicitud, id_cliente, tipo, mes=None, id_evento=None,
                    num_ocurrencia=None, id_reserva=None, asientos=None):
    """{id_solicitud, id_cliente, tipo, mes, id_evento, num_ocurrencia, id_reserva, asientos}"""
    return {
        "id_solicitud": id_solicitud,
        "id_cliente": id_cliente,
        "tipo": tipo,
        "mes": mes,
        "id_evento": id_evento,
        "num_ocurrencia": num_ocurrencia,
        "id_reserva": id_reserva,
        "asientos": asientos,
    }


def crear_respuesta(id_solicitud, estado, datos=None):
    """{id_solicitud, estado: EXITO | RECHAZADO | ERROR, datos}"""
    return {"id_solicitud": id_solicitud, "estado": estado, "datos": datos or {}}


def log(proceso, tipo, id_solicitud, resultado, tiempo_s=None, detalle=""):
    """Una línea por operación: hora, proceso, tipo, id_solicitud, resultado, tiempo."""
    hora = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    tiempo = f"{tiempo_s:.4f} s" if tiempo_s is not None else "-"
    print(f"{hora}  {proceso:<6} {tipo:<10} {str(id_solicitud):<10} "
          f"{resultado:<13} {tiempo:>10}  {detalle}".rstrip(), flush=True)


def cronometro():
    """Marca de tiempo para medir latencias (no depende de la hora del sistema)."""
    return time.perf_counter()
