"""
GestorTransacciones · VM2

ROUTER bind :5557     <- ClienteCarga (REQ)      · canal síncrono
DEALER connect :5556  -> ServicioRMC (REP)
ROUTER bind :5558     <- ClienteCarga (DEALER)   · cancelaciones (Entrega 2)
PUSH   bind :5559     -> ServicioCancelaciones   · (Entrega 2)

Uso: python3 gestor_transacciones.py
"""


class GestorTransacciones:

    def __init__(self):
        self.sock_clientes_sync = None    # ROUTER
        self.sock_clientes_async = None   # ROUTER (Entrega 2)
        self.sock_rmc = None              # DEALER
        self.sock_cancelaciones = None    # PUSH   (Entrega 2)

    def enrutar_sincrono(self, solicitud):
        """Reenvía al RMC una solicitud de consulta o reserva recibida de un cliente."""
        pass

    def aceptar_cancelacion(self, solicitud):
        """Entrega 2."""
        pass

    def registrar_metrica(self, tipo, tiempo):
        """Cuenta las solicitudes completadas por tipo (TPM) y guarda el tiempo en gt_metricas.csv."""
        pass


def main():
    print("gestor_transacciones.py: pendiente de implementar")


if __name__ == "__main__":
    main()