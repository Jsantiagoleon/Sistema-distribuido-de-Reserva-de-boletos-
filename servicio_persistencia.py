"""
Servicio de Persistencia · VM3 · capa de almacenamiento.

Sockets:
    REP  bind :5555   <- RMC (y Cancelaciones en la Entrega 2) con REQ

Responsabilidades (Entrega 1):
    - Leer y escribir datos/events.json (eventos, reservas y solicitudes procesadas).
    - consultar_mes(mes): eventos y ocurrencias del mes.
    - consultar_disponibilidad(id_evento, num_ocurrencia): asientos libres.
    - confirmar_reserva(solicitud): confirmación condicional, vuelve a revisar
      el cupo antes de escribir (evita sobreventa).
    - Guardar el resultado de cada id_solicitud: si la misma solicitud llega
      dos veces, responde lo mismo y no descuenta asientos otra vez.
    - Guardar cada cambio en un archivo temporal y reemplazar el original con
      os.replace(), para no dañar events.json si el proceso se cae al escribir.
    - Validar los datos recibidos y responder ERROR si son incorrectos.
    - Imprimir una línea por operación (comun.log).

Entrega 2: modificar_reserva, liberar_asientos (cancelación), réplica de solo lectura.

Ejecución:
    python3 servicio_persistencia.py
"""


def main():
    print("servicio_persistencia.py: pendiente de implementar")


if __name__ == "__main__":
    main()
