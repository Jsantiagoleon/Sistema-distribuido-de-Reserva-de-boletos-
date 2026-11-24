"""
Muestra los asientos libres y ocupados de cada ocurrencia y el número de reservas · VM3

Lee directamente de PostgreSQL (la misma información sale con psql, ver README).
Uso: python3 ver_bd.py
"""

import psycopg2

import bd
import config


def main():
    try:
        conn = bd.conectar()
    except psycopg2.Error as e:
        raise SystemExit(f"No se pudo conectar a PostgreSQL en {config.PG_HOST}:{config.PG_PUERTO}: {e}")
    if not bd.existe_esquema(conn):
        raise SystemExit("La base de datos no tiene las tablas del SRB. Ejecute primero: python3 generar_bd.py")

    with conn.cursor() as cur:
        eventos = bd.leer_eventos(cur)
        cur.execute("SELECT count(*) FILTER (WHERE estado = 'activa'), "
                    "count(*) FILTER (WHERE estado = 'cancelada') FROM reservas")
        activas, canceladas = cur.fetchone()
    conn.close()

    print(f"{'Evento':<8}{'Oc.':<5}{'Fecha':<13}{'Libres':>8}{'Ocupados':>10}")
    print("-" * 44)
    ocurrencias = libres = ocupados = 0
    for id_evento, evento in eventos.items():
        for oc in evento["ocurrencias"]:
            print(f"{id_evento:<8}{oc['numero']:<5}{oc['fecha']:<13}"
                  f"{oc['asientos_libres']:>8}{oc['asientos_ocupados']:>10}")
            ocurrencias += 1
            libres += oc["asientos_libres"]
            ocupados += oc["asientos_ocupados"]
    print("-" * 44)
    print(f"Eventos: {len(eventos)} · Ocurrencias: {ocurrencias} · Libres: {libres} · "
          f"Ocupados: {ocupados} · Reservas activas: {activas} · canceladas: {canceladas}")


if __name__ == "__main__":
    main()
