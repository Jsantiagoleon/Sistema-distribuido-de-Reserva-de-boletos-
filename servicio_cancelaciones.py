"""
ServicioCancelaciones · VM2 · se implementa en la Entrega 2

PULL connect :5559     <- GestorTransacciones (PUSH)
REQ  connect VM3:5555  -> ServicioPersistencia (REP)
PUB  bind :5560        -> ClienteCarga (SUB)
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