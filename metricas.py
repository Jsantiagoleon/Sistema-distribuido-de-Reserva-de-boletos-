"""
Procesa los resultados de las pruebas de carga.

Entradas:
    resultados/<corrida>/resultados_<id>.csv   (tiempos medidos en cada cliente)
    resultados/<corrida>/gt_metricas.csv       (conteos medidos en el GT)

Salidas por escenario (3, 5 y 8 clientes):
    1. Tiempo promedio de respuesta y desviación estándar de las consultas.
    2. Tiempo promedio de respuesta y desviación estándar de las reservas.
    3. TPM de consultas (medido en el GT).
    4. TPM de reservas (medido en el GT).
    - Se descartan los primeros 15 s de cada corrida.
    - Errores y timeouts se cuentan aparte.
    - Gráficas base vs. escalable (Entrega 2), con pandas y matplotlib.

Ejecución:
    python3 metricas.py resultados/
"""


def main():
    print("metricas.py: pendiente de implementar")


if __name__ == "__main__":
    main()
