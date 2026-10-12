"""
ClienteCarga · VM1

REQ    connect VM2:5557 -> GestorTransacciones (ROUTER)   · consulta y reserva
DEALER connect VM2:5558 -> GestorTransacciones (ROUTER)   · cancelación (Entrega 2)
SUB    connect VM2:5560 <- ServicioCancelaciones (PUB)    · notificaciones (Entrega 2)

Uso: python3 cliente.py --id C1 --rpm 20 --modo fija --pct-consulta 50 --pct-reserva 50 --duracion 3
"""


class ClienteCarga:

    def __init__(self, id_cliente, rpm, pct_consulta, pct_reserva, pct_modificacion, modo):
        self.id_cliente = id_cliente
        self.rpm = rpm
        self.pct_consulta = pct_consulta
        self.pct_reserva = pct_reserva
        self.pct_modificacion = pct_modificacion
        self.modo = modo                # fija | cerrado
        self.sock_sync = None           # REQ
        self.sock_cancel = None         # DEALER (Entrega 2)
        self.sock_notif = None          # SUB    (Entrega 2)

    def enviar_consulta(self, mes):
        """Envía una consulta de los eventos del mes y devuelve la Respuesta."""
        pass

    def enviar_reserva(self, id_evento, num_ocurrencia, asientos):
        """Envía una reserva y devuelve la Respuesta."""
        pass

    def enviar_modificacion(self, id_reserva, num_ocurrencia, asientos):
        """Entrega 2."""
        pass

    def enviar_cancelacion(self, id_reserva):
        """Entrega 2."""
        pass

    def recibir_notificacion(self):
        """Entrega 2."""
        pass

    def registrar_resultado(self, solicitud, respuesta, ms):
        """Guarda el tiempo de respuesta en resultados_<id>.csv e imprime la línea de log."""
        pass


def main():
    print("cliente.py: pendiente de implementar")


if __name__ == "__main__":
    main()