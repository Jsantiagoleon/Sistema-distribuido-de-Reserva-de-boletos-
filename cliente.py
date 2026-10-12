"""
Cliente generador de carga · VM1 · capa de consumidores.

Cada cliente es un proceso independiente (no hilos: en Python los hilos no
corren en paralelo y eso alteraría las mediciones).

Sockets:
    REQ    connect VM2:5557    -> GT: consulta y reserva (síncrono)
    DEALER connect VM2:5558    -> GT: cancelación         (Entrega 2)
    SUB    connect VM2:5560    <- notificaciones, tópico = id_cliente (Entrega 2)

Parámetros (Tabla 4 del informe):
    --id                 C1 ... C8
    --gt                 dirección del GT (por defecto config.DIR_GT_SINCRONO)
    --rpm                solicitudes por minuto (mínimo 20)
    --modo               fija: una solicitud cada 60/rpm s · cerrado: envía la
                         siguiente al recibir la respuesta
    --pct-consulta / --pct-reserva / --pct-modificacion   (suman 100)
    --duracion           minutos de carga (por defecto 3)

Responsabilidades (Entrega 1):
    - Consultas del mes de noviembre; reservas de un evento, ocurrencia y
      1 a 4 asientos al azar.
    - id_solicitud único (p. ej. C3-0007) que se conserva en los reintentos.
    - Medir cada solicitud con time.perf_counter() y guardarla en
      resultados/resultados_<id>.csv.
    - Timeout de 5 s: registrar sin_respuesta y reabrir el socket REQ.
    - Imprimir una línea por operación (comun.log).

Ejecución:
    python3 cliente.py --id C1 --rpm 20 --pct-consulta 100 --duracion 3
"""


def main():
    print("cliente.py: pendiente de implementar")


if __name__ == "__main__":
    main()
