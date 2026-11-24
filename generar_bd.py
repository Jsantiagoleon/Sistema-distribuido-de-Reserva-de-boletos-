"""
Crea (o reinicia) las tablas del SRB en PostgreSQL con los datos iniciales · VM3

50 eventos en noviembre de 2026: E1 a E20 con dos ocurrencias y E21 a E50
con una, todas con 100 asientos libres (70 ocurrencias, 7.000 asientos).
Si las tablas ya existen se borran y se vuelven a crear (sirve para reiniciar la BD);
detenga Persistencia antes de reiniciar.

Requiere que PostgreSQL esté instalado y que existan el usuario y la base de datos
(ver README, sección "PostgreSQL en la VM3", o ejecute ./preparar_postgres.sh).

Uso: python3 generar_bd.py
"""

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
