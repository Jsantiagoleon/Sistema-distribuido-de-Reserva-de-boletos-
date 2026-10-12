"""
ServicioPersistencia · VM3

REP bind :5555 <- ServicioRMC y ServicioCancelaciones (REQ)

Uso: python3 servicio_persistencia.py
"""


class ServicioPersistencia:

    def __init__(self):
        self.sock_rep = None                 # REP
        self.solicitudes_procesadas = {}     # id_solicitud -> respuesta guardada
        self.eventos = {}                    # composición: gestiona 50 Evento
        self.reservas = {}                   # composición: gestiona 0..* Reserva

    def consultar_mes(self, mes):
        """Devuelve los eventos del mes."""
        pass

    def consultar_disponibilidad(self, id_evento, num_ocurrencia):
        """Devuelve los asientos libres de una ocurrencia."""
        pass

    def confirmar_reserva(self, solicitud):
        """Vuelve a revisar el cupo y, si alcanza, crea la reserva y guarda events.json."""
        pass

    def modificar_reserva(self, solicitud):
        """Entrega 2."""
        pass

    def liberar_asientos(self, solicitud):
        """Entrega 2."""
        pass


def main():
    print("servicio_persistencia.py: pendiente de implementar")


if __name__ == "__main__":
    main()