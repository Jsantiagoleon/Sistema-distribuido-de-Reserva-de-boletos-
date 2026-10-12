"""
Servicio RMC · VM2

REP bind :5556         <- GT (DEALER)
REQ connect VM3:5555   -> Persistencia (REP)

- Consulta: pide a Persistencia los eventos del mes.
- Reserva: consulta disponibilidad y, si hay cupo, pide la confirmación.
- Responde EXITO, RECHAZADO o ERROR.
"""


def main():
    print("servicio_rmc.py: pendiente de implementar")


if __name__ == "__main__":
    main()
