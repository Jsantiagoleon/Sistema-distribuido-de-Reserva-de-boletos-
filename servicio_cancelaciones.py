"""
ServicioCancelaciones en vm2 entrega 3

"""


class ServicioCancelaciones:

    def __init__(self):
        self.sock_gt = None               # PULL
        self.sock_persistencia = None     # REQ
        self.sock_notificaciones = None   # PUB

    def procesar_cancelacion(self, solicitud):
        """Entrega 2."""
        pass

    def notificar_cliente(self, id_cliente, respuesta):
        """Entrega 2."""
        pass