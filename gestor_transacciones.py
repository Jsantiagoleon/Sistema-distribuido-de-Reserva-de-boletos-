"""
Gestor de Transacciones (GT) · VM2

ROUTER bind :5557      <- Clientes (REQ)
DEALER connect :5556   -> RMC (REP)

- Con un zmq.Poller atiende a los clientes y las respuestas del RMC sin bloquearse.
- Reenvía [identidad, b"", mensaje] al RMC y devuelve la respuesta al cliente correcto.
- Registra en resultados/gt_metricas.csv las solicitudes completadas por tipo (TPM).
"""


def main():
    print("gestor_transacciones.py: pendiente de implementar")


if __name__ == "__main__":
    main()
