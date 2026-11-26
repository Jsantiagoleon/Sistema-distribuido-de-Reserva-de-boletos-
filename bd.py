import psycopg2
import psycopg2.extras

import config
from modelos import Evento, Ocurrencia

ESQUEMA = """
DROP TABLE IF EXISTS solicitudes_procesadas, reservas, ocurrencias, eventos CASCADE;
DROP SEQUENCE IF EXISTS reservas_seq;

CREATE TABLE eventos (
    id_evento       TEXT PRIMARY KEY,
    num_ocurrencias INTEGER NOT NULL CHECK (num_ocurrencias BETWEEN 1 AND 2)
);

CREATE TABLE ocurrencias (
    id_evento            TEXT    NOT NULL REFERENCES eventos(id_evento),
    numero               INTEGER NOT NULL,
    fecha                DATE    NOT NULL,
    asientos_disponibles INTEGER NOT NULL,
    asientos_libres      INTEGER NOT NULL CHECK (asientos_libres  >= 0),
    asientos_ocupados    INTEGER NOT NULL CHECK (asientos_ocupados >= 0),
    PRIMARY KEY (id_evento, numero),
    CHECK (asientos_libres + asientos_ocupados = asientos_disponibles)
);
CREATE INDEX ocurrencias_fecha ON ocurrencias (fecha);

CREATE SEQUENCE reservas_seq;
CREATE TABLE reservas (
    id_reserva     TEXT PRIMARY KEY,
    id_cliente     TEXT    NOT NULL,
    asientos       INTEGER NOT NULL CHECK (asientos > 0),
    id_evento      TEXT    NOT NULL,
    num_ocurrencia INTEGER NOT NULL,
    estado         TEXT    NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'cancelada')),
    FOREIGN KEY (id_evento, num_ocurrencia) REFERENCES ocurrencias (id_evento, numero)
);
CREATE INDEX reservas_cliente ON reservas (id_cliente);

CREATE TABLE solicitudes_procesadas (
    id_solicitud TEXT PRIMARY KEY,
    respuesta    JSONB  NOT NULL,
    orden        BIGSERIAL
);
CREATE INDEX solicitudes_orden ON solicitudes_procesadas (orden);
"""


def conectar(base=None):
    return psycopg2.connect(host=config.PG_HOST, port=config.PG_PUERTO,
                            dbname=base or config.PG_BD, user=config.PG_USUARIO,
                            password=config.PG_CLAVE,
                            connect_timeout=config.PG_TIMEOUT_CONEXION_S,
                            application_name="srb")


def existe_esquema(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.ocurrencias') IS NOT NULL "
                    "AND to_regclass('public.reservas') IS NOT NULL "
                    "AND to_regclass('public.solicitudes_procesadas') IS NOT NULL")
        return cur.fetchone()[0]


def datos_iniciales():
    from datetime import date
    eventos = []
    for i in range(1, config.NUM_EVENTOS + 1):
        if i <= config.EVENTOS_CON_DOS_OCURRENCIAS:
            ocurrencias = [Ocurrencia(1, date(config.ANIO, config.MES, i)),
                           Ocurrencia(2, date(config.ANIO, config.MES, i + 10))]
        else:
            ocurrencias = [Ocurrencia(1, date(config.ANIO, config.MES, i - 20))]
        eventos.append(Evento(f"E{i}", len(ocurrencias), ocurrencias))
    return eventos


def crear_base(conn):
    eventos = datos_iniciales()
    with conn.cursor() as cur:
        cur.execute(ESQUEMA)
        psycopg2.extras.execute_values(
            cur, "INSERT INTO eventos (id_evento, num_ocurrencias) VALUES %s",
            [(e.id_evento, e.num_ocurrencias) for e in eventos])
        psycopg2.extras.execute_values(
            cur, "INSERT INTO ocurrencias (id_evento, numero, fecha, asientos_disponibles, "
                 "asientos_libres, asientos_ocupados) VALUES %s",
            [(e.id_evento, o.numero, o.fecha, o.asientos_disponibles, o.asientos_libres,
              o.asientos_ocupados) for e in eventos for o in e.ocurrencias])
    conn.commit()
    return len(eventos), sum(e.num_ocurrencias for e in eventos)


def leer_eventos(cur, mes=None):
    filtro = ""
    parametros = ()
    if mes is not None:
        filtro = ("WHERE e.id_evento IN (SELECT id_evento FROM ocurrencias "
                  "WHERE EXTRACT(MONTH FROM fecha) = %s)")
        parametros = (mes,)
    cur.execute(f"""
        SELECT e.id_evento, e.num_ocurrencias, o.numero, o.fecha,
               o.asientos_disponibles, o.asientos_libres, o.asientos_ocupados
        FROM eventos e JOIN ocurrencias o USING (id_evento)
        {filtro}
        ORDER BY length(e.id_evento), e.id_evento, o.numero""", parametros)
    eventos = {}
    for id_evento, n, numero, fecha, disp, libres, ocupados in cur.fetchall():
        e = eventos.setdefault(id_evento, {"id_evento": id_evento, "num_ocurrencias": n,
                                           "ocurrencias": []})
        e["ocurrencias"].append({"numero": numero, "fecha": fecha.isoformat(),
                                 "asientos_disponibles": disp, "asientos_libres": libres,
                                 "asientos_ocupados": ocupados})
    return eventos
