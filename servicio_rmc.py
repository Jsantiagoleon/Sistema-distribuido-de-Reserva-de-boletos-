"""
Servicio RMC (Reserva, Modificación y Consultas) · VM2 · capa de negocio.

Sockets:
    REP  bind :5556            <- Gestor de Transacciones (DEALER)
    REQ  connect VM3:5555      -> Servicio de Persistencia (REP)

Responsabilidades (Entrega 1):
    - procesar_consulta: pide a Persistencia los eventos del mes y los devuelve.
    - procesar_reserva: consulta disponibilidad y, si hay cupo, pide la
      confirmación condicional a Persistencia.
    - Responder EXITO, RECHAZADO (sin cupo) o ERROR (datos inválidos).
    - No guarda estado de la transacción: toda la información viaja en el mensaje.
    - Imprimir una línea por operación (comun.log).

Entrega 2: procesar_modificacion, varias réplicas, aviso "sigo activo" al GT.

Ejecución:
    python3 servicio_rmc.py
"""


def main():
    print("servicio_rmc.py: pendiente de implementar")


if __name__ == "__main__":
    main()
