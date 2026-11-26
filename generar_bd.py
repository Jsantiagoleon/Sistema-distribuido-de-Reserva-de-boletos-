import psycopg2

import bd
import config


def main():
    try:
        conn = bd.conectar()
    except psycopg2.Error as e:
        raise SystemExit(f"No se pudo conectar a PostgreSQL en {config.PG_HOST}:{config.PG_PUERTO} "
                         f"(base '{config.PG_BD}', usuario '{config.PG_USUARIO}'):\n{e}\n"
                         "¿Está instalado y encendido PostgreSQL? ¿Existen el usuario y la base? "
                         "Ver README o ejecute ./preparar_postgres.sh")
    eventos, ocurrencias = bd.crear_base(conn)
    conn.close()
    print(f"Base de datos '{config.PG_BD}' en {config.PG_HOST}:{config.PG_PUERTO} lista")
    print(f"{eventos} eventos · {ocurrencias} ocurrencias · "
          f"{ocurrencias * config.ASIENTOS_POR_OCURRENCIA} asientos libres")


if __name__ == "__main__":
    main()
