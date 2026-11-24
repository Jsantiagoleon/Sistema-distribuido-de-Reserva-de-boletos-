"""
Pruebas automáticas del SRB en localhost (cada componente es un proceso aparte).

    python3 -m unittest pruebas.test_srb -v          # todas (~1,5 min)
    python3 -m unittest pruebas.test_srb.Funcionales -v
    python3 -m unittest pruebas.test_srb.Fallas -v   # T1, T2, T3 y T4

Identificadores de la tabla de pruebas del informe: U1, U2, I1, F1, F2, C1, R1 (Funcionales)
y T1, T2, T3, T4 (Fallas). D1, P1, P2 y S1 se hacen en las 3 VM (ver README).
Cada clase levanta su propio sistema con una base PostgreSQL temporal; no toca la base "srb".
Requiere un servidor PostgreSQL accesible con las variables SRB_PG_* (ver README).
"""

import csv
import json
import os
import sys
import tempfile
import threading
import time
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

# Carpeta de resultados temporal para los clientes de las pruebas (antes de importar config)
RESULTADOS = tempfile.mkdtemp(prefix="srb_test_res_")
os.environ["SRB_DIR_RESULTADOS"] = RESULTADOS
os.environ["SRB_IP_VM2"] = os.environ["SRB_IP_VM3"] = "127.0.0.1"

import bd                                                # noqa: E402
import config                                            # noqa: E402
import prueba_concurrencia                               # noqa: E402
import prueba_idempotencia                               # noqa: E402
import prueba_robustez                                   # noqa: E402
from cliente import ClienteCarga                         # noqa: E402
from lanzar_local import Sistema                         # noqa: E402
from prueba_robustez import enviar_crudo                 # noqa: E402

PERSISTENCIA = f"tcp://127.0.0.1:{config.PUERTO_PERSISTENCIA}"
NOTIF = f"tcp://127.0.0.1:{config.PUERTO_NOTIFICACIONES}"


def a_persistencia(operacion, **solicitud):
    base = {"id_cliente": "U", "tipo": "reserva"}
    mensaje = json.dumps({"operacion": operacion, "solicitud": {**base, **solicitud}})
    return json.loads(enviar_crudo(PERSISTENCIA, mensaje))


def leer_bd(sistema):
    """Lee de PostgreSQL lo que quedó guardado, con la misma forma que usaban las pruebas:
    {"eventos": {id: {"ocurrencias": [...]}}, "reservas": {id_reserva: {...}}}."""
    conn = sistema.conectar_bd()
    try:
        with conn.cursor() as cur:
            eventos = bd.leer_eventos(cur)
            cur.execute("SELECT id_reserva, id_cliente, asientos, id_evento, num_ocurrencia, estado FROM reservas")
            reservas = {f[0]: dict(zip(("id_reserva", "id_cliente", "asientos", "id_evento",
                                        "num_ocurrencia", "estado"), f)) for f in cur.fetchall()}
    finally:
        conn.close()
    return {"eventos": eventos, "reservas": reservas}


class Funcionales(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sistema = Sistema(replicas=2)
        cls.sistema.arrancar()
        cls.cliente = ClienteCarga("T", dirs_gt=cls.sistema.dirs_gt, dir_notificaciones=NOTIF,
                                   silencioso=True)

    @classmethod
    def tearDownClass(cls):
        cls.sistema.parar()

    # ------------------------------------------------------------ U1
    def test_U1_persistencia_confirmar_reserva(self):
        """Con cupo, sin cupo y con asientos fuera de rango (directo a Persistencia)."""
        ok = a_persistencia("confirmar_reserva", id_solicitud="u1-a", id_evento="E30",
                            num_ocurrencia=1, asientos=60)
        self.assertEqual((ok["estado"], ok["datos"]["libres"]), ("EXITO", 40))
        sin_cupo = a_persistencia("confirmar_reserva", id_solicitud="u1-b", id_evento="E30",
                                  num_ocurrencia=1, asientos=41)
        self.assertEqual((sin_cupo["estado"], sin_cupo["datos"]["libres"]), ("RECHAZADO", 40))
        for i, asientos in enumerate([0, 101, -3, "3", True, None]):
            r = a_persistencia("confirmar_reserva", id_solicitud=f"u1-c{i}", id_evento="E30",
                               num_ocurrencia=1, asientos=asientos)
            self.assertEqual(r["estado"], "ERROR", f"asientos={asientos!r}")
        bd = leer_bd(self.sistema)
        oc = bd["eventos"]["E30"]["ocurrencias"][0]
        self.assertEqual((oc["asientos_libres"], oc["asientos_ocupados"]), (40, 60))

    # ------------------------------------------------------------ U2
    def test_U2_idempotencia(self):
        ok, detalle = prueba_idempotencia.ejecutar(self.sistema.dirs_gt[0])
        self.assertTrue(ok, "\n".join(detalle))

    # ------------------------------------------------------------ I1
    def test_I1_consulta_de_punta_a_punta(self):
        r = self.cliente.enviar_consulta(config.MES)
        self.assertEqual(r.estado, "EXITO")
        eventos = r.datos["eventos"]
        self.assertEqual(len(eventos), 50)
        self.assertEqual(sum(len(e["ocurrencias"]) for e in eventos), 70)

    def test_I1b_consulta_otro_mes_vacia(self):
        r = self.cliente.enviar_consulta(12)
        self.assertEqual((r.estado, r.datos["eventos"]), ("EXITO", []))

    # ------------------------------------------------------------ F1
    def test_F1_reservas(self):
        c = self.cliente
        self.assertEqual(c.enviar_reserva("E47", 1, 100).estado, "EXITO")
        sin_cupo = c.enviar_reserva("E47", 1, 1)
        self.assertEqual((sin_cupo.estado, sin_cupo.datos["motivo"]), ("RECHAZADO", "sin cupo"))
        self.assertEqual(c.enviar_reserva("E99", 1, 1).estado, "ERROR")
        self.assertEqual(c.enviar_reserva("E47", 2, 1).estado, "ERROR")   # E47 solo tiene oc1

    # ------------------------------------------------------------ F2
    def test_F2_modificacion_y_cancelacion(self):
        c = self.cliente
        r = c.enviar_reserva("E1", 1, 3)
        id_reserva = r.datos["id_reserva"]
        # más asientos en la misma ocurrencia
        m = c.enviar_modificacion(id_reserva, asientos=7)
        self.assertEqual((m.estado, m.datos["asientos"]), ("EXITO", 7))
        # pasar a la otra ocurrencia conservando los asientos
        m = c.enviar_modificacion(id_reserva, num_ocurrencia=2)
        self.assertEqual((m.estado, m.datos["num_ocurrencia"], m.datos["asientos"]), ("EXITO", 2, 7))
        # un evento de una sola ocurrencia solo admite cambiar asientos
        solo = c.enviar_reserva("E40", 1, 2).datos["id_reserva"]
        self.assertEqual(c.enviar_modificacion(solo, num_ocurrencia=2).estado, "RECHAZADO")
        # no se puede pedir más asientos de los que quedan
        lleno = c.enviar_reserva("E41", 1, 98).datos["id_reserva"]
        self.assertEqual(c.enviar_modificacion(lleno, asientos=100).estado, "EXITO")
        self.assertEqual(c.enviar_modificacion(r.datos["id_reserva"], asientos=1000).estado, "ERROR")

        # cancelación: acuse inmediato + notificación posterior
        t0 = time.perf_counter()
        ack = c.enviar_cancelacion(id_reserva)
        t_ack = time.perf_counter() - t0
        self.assertEqual(ack.estado, "ACEPTADA")
        notif = c.recibir_notificacion(5000)
        self.assertIsNotNone(notif, "no llegó la notificación")
        self.assertEqual((notif.estado, notif.datos["liberados"]), ("EXITO", 7))
        self.assertLess(t_ack, 1.0)
        oc2 = leer_bd(self.sistema)["eventos"]["E1"]["ocurrencias"][1]
        self.assertEqual((oc2["asientos_libres"], oc2["asientos_ocupados"]), (100, 0))
        # cancelar de nuevo la misma reserva: se acepta el pedido, la notificación dice RECHAZADO
        c.reservas.append({"id_reserva": id_reserva, "id_evento": "E1", "num_ocurrencia": 2, "asientos": 7})
        c.enviar_cancelacion(id_reserva)
        self.assertEqual(c.recibir_notificacion(5000).estado, "RECHAZADO")

    # ------------------------------------------------------------ réplica de lectura
    def test_replica_de_lectura_se_actualiza(self):
        c = self.cliente
        c.enviar_reserva("E31", 1, 5)
        time.sleep(0.3)
        r = c.enviar_consulta(config.MES)
        self.assertTrue(r.datos.get("replica"), "la consulta no la atendió la réplica de lectura")
        e31 = next(e for e in r.datos["eventos"] if e["id_evento"] == "E31")
        self.assertEqual(e31["ocurrencias"][0]["asientos_libres"], 95)

    # ------------------------------------------------------------ C1
    def test_C1_concurrencia_ultimos_asientos(self):
        ok, detalle = prueba_concurrencia.ejecutar(self.sistema.dirs_gt[0], self.sistema.nombre_bd)
        self.assertTrue(ok, "\n".join(detalle))

    # ------------------------------------------------------------ R1
    def test_R1_robustez(self):
        ok, detalle = prueba_robustez.ejecutar(self.sistema.dirs_gt[0])
        self.assertTrue(ok, "\n".join(detalle))


# ====================================================================== fallas
def leer_csv(id_cliente):
    with open(os.path.join(RESULTADOS, f"resultados_{id_cliente}.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Fallas(unittest.TestCase):
    """T1 y T2: una carga continua de un cliente mientras se mata (kill -9) un componente."""

    def carga(self, sistema, id_cliente, segundos, hacer_a_mitad):
        """Cliente en un hilo (consultas y reservas a unas 8 por segundo); a los 6 s ejecuta
        'hacer_a_mitad'. Devuelve el cliente al terminar."""
        cliente = ClienteCarga(id_cliente, dirs_gt=sistema.dirs_gt, dir_notificaciones=NOTIF,
                               silencioso=True)
        fin = time.time() + segundos

        def bucle():
            n = 0
            while time.time() < fin:
                n += 1
                if n % 2:
                    cliente.enviar_consulta(config.MES)
                else:
                    cliente.enviar_reserva(f"E{(n % 40) + 1}", 1, 1)
                time.sleep(0.1)

        hilo = threading.Thread(target=bucle)
        hilo.start()
        time.sleep(6)
        hacer_a_mitad()
        hilo.join()
        return cliente

    def verificar_sin_perdidas(self, sistema, cliente, id_cliente):
        filas = leer_csv(id_cliente)
        sin_respuesta = [f for f in filas if f["estado"] == "sin_respuesta"]
        self.assertEqual(sin_respuesta, [], "hubo solicitudes sin respuesta")
        # lo que el cliente cree que reservó == lo que Persistencia tiene (ni perdidas ni duplicadas)
        propias = {k for k, r in leer_bd(sistema)["reservas"].items() if r["id_cliente"] == id_cliente}
        del_cliente = {r["id_reserva"] for r in cliente.reservas}
        self.assertEqual(propias, del_cliente, "reservas perdidas o duplicadas")
        return filas

    def test_T1_falla_del_gt_principal(self):
        with Sistema(replicas=2) as s:
            def matar_gt():
                self.t_falla = time.time()
                s.matar("gt_principal")
            cliente = self.carga(s, "T1", 22, matar_gt)
            filas = self.verificar_sin_perdidas(s, cliente, "T1")

            reintentadas = [f for f in filas if int(f["intentos"]) > 1]
            self.assertTrue(reintentadas, "ninguna solicitud tuvo que reintentarse")
            self.assertLess(max(float(f["tiempo_ms"]) for f in filas), 6500)
            log = s.log("gt_respaldo")
            self.assertIn("GT RESPALDO ACTIVO", log)
            print("\n--- T1: log del GT de respaldo ---\n" + "\n".join(
                l for l in log.splitlines() if "***" in l or "arrancó" in l))
            print(f"solicitudes: {len(filas)}, reintentadas: {len(reintentadas)}, "
                  f"tiempo máximo: {max(float(f['tiempo_ms']) for f in filas):.0f} ms")

            # el principal regresa: debe quedar PASIVO (el respaldo sigue activo)
            s.iniciar("gt_principal")
            time.sleep(4)
            tras_regreso = s.log("gt_principal").split("arrancó")[-1]
            self.assertIn("GT PRINCIPAL PASIVO", tras_regreso)
            self.assertNotIn("GT PRINCIPAL ACTIVO", tras_regreso)
            print("--- T1: log del GT principal tras regresar ---\n" + "\n".join(
                l for l in s.log("gt_principal").splitlines() if "***" in l or "arrancó" in l))

    def test_T2_falla_de_una_replica_rmc(self):
        with Sistema(replicas=2) as s:
            cliente = self.carga(s, "T2", 20, lambda: s.matar("rmc0"))
            filas = self.verificar_sin_perdidas(s, cliente, "T2")
            log = s.log("gt_principal")
            self.assertIn("se da por CAÍDA", log)
            self.assertLess(max(float(f["tiempo_ms"]) for f in filas), config.TIMEOUT_CLIENTE_MS)
            print("\n--- T2: log del GT ---\n" + "\n".join(l for l in log.splitlines() if "!!!" in l))
            print(f"solicitudes: {len(filas)}, tiempo máximo: "
                  f"{max(float(f['tiempo_ms']) for f in filas):.0f} ms")
            s.iniciar("rmc0")
            time.sleep(3)
            self.assertIn("se reincorpora", s.log("gt_principal"))

    def test_T3_persistencia_caida(self):
        """Persistencia (punto único de falla) cae: el RMC responde ERROR 'persistencia no responde'
        con reintentar=true en ~3 s, el GT no se bloquea y, al volver Persistencia, todo se recupera
        sin duplicar reservas."""
        with Sistema(replicas=2, respaldo=False, replica_lectura=False) as s:
            c = ClienteCarga("T3", dirs_gt=s.dirs_gt, dir_notificaciones=NOTIF, silencioso=True)
            antes = c.enviar_reserva("E10", 1, 2)
            self.assertEqual(antes.estado, "EXITO")

            s.matar("persistencia")
            t0 = time.time()
            r = c.enviar_reserva("E10", 1, 2)
            dur = time.time() - t0
            self.assertEqual(r.estado, "ERROR")
            self.assertIn("persistencia no responde", r.datos["motivo"])
            self.assertTrue(r.datos["reintentar"])
            self.assertGreater(dur, config.TIMEOUT_PERSISTENCIA_MS / 1000 - 0.5)
            self.assertLess(dur, config.TIMEOUT_CLIENTE_MS / 1000)        # contestó el GT, no venció el cliente
            print(f"\nT3: con Persistencia caída respondió {r.estado} {r.datos} en {dur:.1f} s")
            self.assertRegex(s.log("gt_principal"), r"(?i)error\s+3\.\d+ s")      # el GT lo registró: ERROR tras ~3 s

            # el GT sigue vivo: otra solicitud también recibe su ERROR (no queda bloqueado)
            t0 = time.time()
            r2 = c.enviar_consulta(config.MES)
            self.assertLess(time.time() - t0, config.TIMEOUT_CLIENTE_MS / 1000)
            self.assertEqual(r2.estado, "ERROR")

            # Persistencia regresa (PostgreSQL conservó los datos): el sistema se recupera solo
            s.iniciar("persistencia")
            time.sleep(1.5)
            r3 = c.enviar_reserva("E10", 1, 2)
            self.assertEqual(r3.estado, "EXITO")
            reservas = [x for x in leer_bd(s)["reservas"].values() if x["id_cliente"] == "T3"]
            self.assertEqual(len(reservas), 2, "la reserva fallida no debe haberse guardado, solo las 2 buenas")

    def test_T4_misma_solicitud_en_dos_gt_activos(self):
        """Peor caso de la falla del principal: el cliente cree que cayó, reenvía al otro GT y los DOS
        GT terminan activos. La misma solicitud (mismo id_solicitud) no debe ejecutarse dos veces."""
        with Sistema(replicas=2, respaldo=True, replica_lectura=False, doble_activo=True) as s:
            self.assertIn("ACTIVO", s.log("gt_principal"))
            self.assertIn("ACTIVO", s.log("gt_respaldo"))
            solicitud = json.dumps({"id_cliente": "T4", "id_solicitud": "T4-1", "tipo": "reserva",
                                    "id_evento": "E20", "num_ocurrencia": 1, "asientos": 3})
            respuestas = []

            def enviar(gt):
                respuestas.append(json.loads(enviar_crudo(gt, solicitud)))

            hilos = [threading.Thread(target=enviar, args=(gt,)) for gt in s.dirs_gt]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join()
            self.assertEqual(len(respuestas), 2)
            self.assertEqual(respuestas[0]["estado"], "EXITO")
            self.assertEqual(respuestas[0], respuestas[1], "los dos GT deben devolver la misma reserva")
            bd = leer_bd(s)
            propias = [r for r in bd["reservas"].values() if r["id_cliente"] == "T4"]
            self.assertEqual(len(propias), 1, "la solicitud se ejecutó dos veces")
            oc = bd["eventos"]["E20"]["ocurrencias"][0]
            self.assertEqual(oc["asientos_libres"], 97)
            print(f"\nT4: dos GT activos, misma solicitud -> una sola reserva {respuestas[0]['datos']}")

    def test_replica_de_lectura_se_resincroniza_si_reinicia_la_principal(self):
        with Sistema(replicas=1, respaldo=False) as s:
            c = ClienteCarga("RL", dirs_gt=s.dirs_gt, dir_notificaciones=NOTIF, silencioso=True)
            c.enviar_reserva("E32", 1, 10)
            time.sleep(0.3)
            s.matar("persistencia")
            s.iniciar("persistencia")                       # arranca con los datos que ya están en PostgreSQL
            time.sleep(1.5)
            c.enviar_reserva("E32", 1, 5)                   # delta con seq 1 de la nueva época
            time.sleep(1.0)
            r = c.enviar_consulta(config.MES)
            e32 = next(e for e in r.datos["eventos"] if e["id_evento"] == "E32")
            self.assertTrue(r.datos.get("replica"))
            self.assertEqual(e32["ocurrencias"][0]["asientos_libres"], 85)
            self.assertIn("se reinició", s.log("replica_lectura"))


if __name__ == "__main__":
    unittest.main()
