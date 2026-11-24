"""
Clases de datos del diagrama de clases.

Solicitud y Respuesta son los mensajes que viajan en JSON entre procesos.
Evento, Ocurrencia y Reserva son las entidades que se guardan en PostgreSQL (ver bd.py).
"""

from dataclasses import dataclass, field
from datetime import date

# Valores de Solicitud.tipo
CONSULTA = "consulta"
RESERVA = "reserva"
MODIFICACION = "modificacion"
CANCELACION = "cancelacion"

# Valores de Respuesta.estado
EXITO = "EXITO"
RECHAZADO = "RECHAZADO"
ERROR = "ERROR"
ACEPTADA = "ACEPTADA"      # acuse inmediato del GT a una cancelación asíncrona

# Valores de Reserva.estado
ACTIVA = "activa"
CANCELADA = "cancelada"


@dataclass
class Solicitud:
    """Mensaje del cliente.
    - consulta:      mes
    - reserva:       id_evento, num_ocurrencia, asientos
    - modificacion:  id_reserva y UNA de dos cosas: asientos (nuevo total en la misma
                     ocurrencia) o num_ocurrencia (cambio de fecha conservando los asientos)
    - cancelacion:   id_reserva
    """
    id_solicitud: str
    id_cliente: str
    tipo: str
    mes: int = None
    id_evento: str = None
    num_ocurrencia: int = None
    id_reserva: str = None
    asientos: int = None


@dataclass
class Respuesta:
    id_solicitud: str
    estado: str
    datos: dict = field(default_factory=dict)


@dataclass
class Ocurrencia:
    numero: int
    fecha: date
    asientos_disponibles: int = 100
    asientos_libres: int = 100
    asientos_ocupados: int = 0


@dataclass
class Evento:
    id_evento: str
    num_ocurrencias: int
    ocurrencias: list = field(default_factory=list)   # composición Evento 1 -- 1..2 Ocurrencia


@dataclass
class Reserva:
    id_reserva: str
    id_cliente: str
    asientos: int
    id_evento: str = None        # asociación "sobre" con la Ocurrencia
    num_ocurrencia: int = None
    estado: str = ACTIVA         # una reserva cancelada se conserva, pero ya no ocupa asientos
