"""
ServicioRMC · VM2

REP bind :5556         <- GestorTransacciones (DEALER)
REQ connect VM3:5555   -> ServicioPersistencia (REP)

Uso: python3 servicio_rmc.py
"""


class ServicioRMC:

    def __init__(self):
        self.sock_gt = None             # REP
        self.sock_persistencia = None   # REQ

    def procesar_consulta(self, solicitud):
        """Pide a Persistencia los eventos del mes y devuelve la Respuesta."""
        pass

    def procesar_reserva(self, solicitud):
        """Consulta disponibilidad y, si hay cupo, pide la confirmación a Persistencia."""
        pass

    def procesar_modificacion(self, solicitud):
        """Entrega 2."""
        pass


def main():
    print("servicio_rmc.py: pendiente de implementar")


if __name__ == "__main__":
    main()