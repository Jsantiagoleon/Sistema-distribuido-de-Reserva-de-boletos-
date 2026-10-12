"""
Servicio de Cancelaciones y Notificaciones · VM2 · capa de negocio.

*** Se implementa en la Entrega 2. En la Entrega 1 solo existe este esqueleto. ***

Sockets:
    PULL connect :5559         <- Gestor de Transacciones (PUSH)
    REQ  connect VM3:5555      -> Servicio de Persistencia (REP)
    PUB  bind :5560            -> Clientes (SUB), tópico = id_cliente

Responsabilidades:
    - Recoger cancelaciones de la cola (PULL).
    - Pedir a Persistencia que libere los asientos y esperar su respuesta.
    - Publicar la notificación con el id_cliente como tópico.

Ejecución:
    python3 servicio_cancelaciones.py
"""


def main():
    print("servicio_cancelaciones.py: se implementa en la Entrega 2")


if __name__ == "__main__":
    main()
