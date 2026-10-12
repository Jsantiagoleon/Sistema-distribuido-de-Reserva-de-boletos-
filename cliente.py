"""
Cliente generador de carga · VM1

REQ connect VM2:5557 -> GT (ROUTER)

Parámetros: --id, --gt, --rpm, --modo (fija | cerrado),
            --pct-consulta, --pct-reserva, --pct-modificacion, --duracion (min)

- Consultas del mes de noviembre; reservas de un evento, ocurrencia y 1 a 4 asientos al azar.
- id_solicitud único (C3-0007) que se conserva en los reintentos.
- Mide cada solicitud con time.perf_counter() y la guarda en resultados/resultados_<id>.csv.
- Timeout de 5 s: registra sin_respuesta y reabre el socket REQ.
"""


def main():
    print("cliente.py: pendiente de implementar")


if __name__ == "__main__":
    main()
