"""
Gestor de Transacciones (GT) · VM2 · capa de negocio.

Puerta de entrada del sistema: recibe a todos los clientes y enruta cada
solicitud por el canal síncrono o el asíncrono.

Sockets:
    ROUTER bind :5557          <- Clientes (REQ): consulta y reserva (canal síncrono)
    DEALER connect :5556       -> RMC (REP)
    ROUTER bind :5558          <- Clientes (DEALER): cancelaciones   (Entrega 2)
    PUSH   bind :5559          -> Servicio de Cancelaciones (PULL)   (Entrega 2)

Responsabilidades (Entrega 1):
    - Con un zmq.Poller atender a la vez lo que llega de los clientes (ROUTER)
      y lo que vuelve del RMC (DEALER), sin bloquearse.
    - Reenviar el mensaje completo [identidad, b"", json] al RMC y devolver la
      respuesta al cliente correcto usando esa identidad.
    - Registrar en resultados/gt_metricas.csv: tiempo de servicio interno y
      solicitudes completadas (EXITO o RECHAZADO) por tipo, para calcular el TPM.
    - Imprimir una línea por operación (comun.log).

Entrega 2: canal asíncrono (acuse inmediato + PUSH), GT de respaldo,
reparto entre réplicas del RMC y detección de réplicas caídas.

Ejecución:
    python3 gestor_transacciones.py
"""


def main():
    print("gestor_transacciones.py: pendiente de implementar")


if __name__ == "__main__":
    main()
