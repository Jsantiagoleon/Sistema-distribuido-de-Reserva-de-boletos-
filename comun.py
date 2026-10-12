"""
Funciones compartidas por todos los procesos del SRB.

- Formato de los mensajes (solicitud y respuesta en JSON).
- Línea de log por operación, para que en la sustentación se vea qué hace
  cada proceso y con qué resultado.
"""

import time
from datetime import datetime

# Tipos de operación
CONSULTA = "consulta"
RESERVA = "reserva"
MODIFICACION = "modificacion"   # Entrega 2
CANCELACION = "cancelacion"     # Entrega 2
TIPOS_VALIDOS = (CONSULTA, RESERVA, MODIFICACION, CANCELACION)

# Estados de una respuesta
EXITO = "EXITO"
RECHAZADO = "RECHAZADO"
ERROR = "ERROR"
SIN_RESPUESTA = "sin_respuesta"  # lo registra el cliente cuando vence el timeout


def crear_solicitud(id_solicitud, id_cliente, tipo, mes=None, id_evento=None,
                    num_ocurrencia=None, id_reserva=None, asientos=None):
    """Solicitud: {id_solicitud, id_cliente, tipo, mes, id_evento,
    num_ocurrencia, id_reserva, asientos}. Los campos que no aplican van en None."""
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
    """Respuesta: {id_solicitud, estado: EXITO | RECHAZADO | ERROR, datos}."""
    return {"id_solicitud": id_solicitud, "estado": estado, "datos": datos or {}}


def hora_actual():
    """Hora local con milisegundos, para las líneas de log."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(proceso, tipo, id_solicitud, resultado, tiempo_s=None, detalle=""):
    """Imprime una línea por operación:
    hora · proceso · tipo · id_solicitud · resultado · tiempo · detalle"""
    tiempo = f"{tiempo_s:.4f} s" if tiempo_s is not None else "-"
    linea = (f"{hora_actual()}  {proceso:<6} {tipo:<12} {str(id_solicitud):<12} "
             f"{resultado:<13} {tiempo:>10}  {detalle}")
    print(linea.rstrip(), flush=True)


def cronometro():
    """Marca de tiempo para medir latencias dentro de un mismo proceso.
    perf_counter no depende de la hora del sistema."""
    return time.perf_counter()
