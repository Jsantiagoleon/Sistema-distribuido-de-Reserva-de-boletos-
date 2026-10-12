"""
Servicio de Persistencia · VM3

REP bind :5555 <- RMC (REQ)

- Lee y escribe events.json (eventos, reservas y solicitudes procesadas).
- consultar_mes, consultar_disponibilidad y confirmar_reserva (vuelve a
  revisar el cupo antes de escribir).
- Si un id_solicitud ya fue procesado, devuelve la respuesta guardada.
- Escribe en un archivo temporal y lo reemplaza con os.replace().
- Responde ERROR si los datos son inválidos.
"""


def main():
    print("servicio_persistencia.py: pendiente de implementar")


if __name__ == "__main__":
    main()
