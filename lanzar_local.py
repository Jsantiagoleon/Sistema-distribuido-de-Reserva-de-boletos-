"""
Levanta TODO el SRB en una sola máquina (localhost) para probar sin las 3 VM.

Cada componente es un proceso aparte, igual que en el despliegue real; el GT de respaldo usa el
puerto 6557 (el principal el 5557) para que los dos convivan en la misma máquina. Crea una base de
datos PostgreSQL temporal (srb_local_xxxx, en el servidor que indiquen las variables SRB_PG_*) y una
carpeta de resultados temporal; al terminar borra la base temporal, así que no toca la base "srb".

Uso en una terminal:
    python3 lanzar_local.py [--replicas 2] [--sin-respaldo] [--replica-lectura]
Luego, en otra:
    python3 cliente.py --id C1 --gt tcp://127.0.0.1:5557,tcp://127.0.0.1:6557 --duracion 1
Ctrl+C detiene todo. Los logs de cada proceso quedan en la carpeta que se imprime al arrancar.

También lo usan las pruebas automáticas (pruebas/) mediante la clase Sistema.
"""

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import bd

AQUI = os.path.dirname(os.path.abspath(__file__))
GT_PRINCIPAL = "tcp://127.0.0.1:5557"
GT_RESPALDO = "tcp://127.0.0.1:6557"


class Sistema:

    def __init__(self, replicas=2, respaldo=True, replica_lectura=True, carpeta=None, doble_activo=False):
        self.replicas = replicas
        self.respaldo = respaldo
        self.replica_lectura = replica_lectura
        # doble_activo=True: los dos GT se creen "principal" y no se oyen entre sí, así que quedan
        # ACTIVOS a la vez (prueba T4: dos GT atendiendo la misma solicitud). El "par" apunta a un
        # puerto donde nadie publica latidos.
        self.doble_activo = doble_activo
        self.carpeta = carpeta or tempfile.mkdtemp(prefix="srb_local_")
        self.nombre_bd = "srb_local_" + uuid.uuid4().hex[:10]
        self.dir_resultados = os.path.join(self.carpeta, "resultados")
        self.env = {**os.environ, "SRB_IP_VM2": "127.0.0.1", "SRB_IP_VM3": "127.0.0.1",
                    "SRB_PG_BD": self.nombre_bd, "SRB_DIR_RESULTADOS": self.dir_resultados,
                    "PYTHONUNBUFFERED": "1"}
        self.procesos = {}
        self.dirs_gt = [GT_PRINCIPAL, GT_RESPALDO] if respaldo else [GT_PRINCIPAL]

    # ------------------------------------------------------------ procesos
    def _comando(self, nombre):
        py = sys.executable
        if nombre == "persistencia":
            return [py, "servicio_persistencia.py"]
        if nombre == "replica_lectura":
            return [py, "servicio_persistencia.py", "--rol", "replica"]
        if nombre == "cancelaciones":
            return [py, "servicio_cancelaciones.py"]
        if nombre.startswith("rmc"):
            cmd = [py, "servicio_rmc.py", nombre[3:]]
            return cmd + (["--replica-lectura"] if self.replica_lectura else [])
        if self.doble_activo and nombre in ("gt_principal", "gt_respaldo"):
            puerto = "5557" if nombre == "gt_principal" else "6557"
            return [py, "gestor_transacciones.py", "--rol", "principal", "--puerto", puerto,
                    "--replicas", str(self.replicas), "--par", "127.0.0.1:9999"]
        if nombre == "gt_principal":
            return [py, "gestor_transacciones.py", "--rol", "principal", "--replicas", str(self.replicas),
                    "--par", "127.0.0.1:6557"]
        if nombre == "gt_respaldo":
            return [py, "gestor_transacciones.py", "--rol", "respaldo", "--puerto", "6557",
                    "--replicas", str(self.replicas), "--par", "127.0.0.1:5557"]
        raise ValueError(nombre)

    def iniciar(self, nombre):
        log = open(os.path.join(self.carpeta, f"{nombre}.log"), "a")
        self.procesos[nombre] = subprocess.Popen(self._comando(nombre), cwd=AQUI, env=self.env,
                                                 stdout=log, stderr=subprocess.STDOUT)
        log.close()                      # el proceso hijo conserva su propia copia del descriptor

    def matar(self, nombre):
        """kill -9: simula la caída abrupta del proceso."""
        p = self.procesos.pop(nombre)
        p.kill()
        p.wait()

    # ------------------------------------------------------------ base de datos temporal
    def _crear_bd(self):
        admin = bd.conectar("postgres")
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{self.nombre_bd}"')
        admin.close()
        subprocess.run([sys.executable, "generar_bd.py"], cwd=AQUI, env=self.env,
                       check=True, stdout=subprocess.DEVNULL)

    def _borrar_bd(self):
        admin = bd.conectar("postgres")
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{self.nombre_bd}" WITH (FORCE)')
        admin.close()

    def conectar_bd(self):
        """Conexión a la base temporal (para que las pruebas revisen lo que quedó guardado)."""
        return bd.conectar(self.nombre_bd)

    def arrancar(self, generar_bd=True):
        if generar_bd:
            self._crear_bd()
        self.iniciar("persistencia")
        if self.replica_lectura:
            time.sleep(0.5)
            self.iniciar("replica_lectura")
        self.iniciar("cancelaciones")
        for i in range(self.replicas):
            self.iniciar(f"rmc{i}")
        self.iniciar("gt_principal")
        if self.respaldo:
            self.iniciar("gt_respaldo")
        # el GT principal se activa tras 1,5 s de escucha; el respaldo queda pasivo
        time.sleep(2.5)

    def parar(self):
        for p in self.procesos.values():
            p.terminate()
        for p in self.procesos.values():
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        self.procesos.clear()
        self._borrar_bd()

    def log(self, nombre):
        with open(os.path.join(self.carpeta, f"{nombre}.log"), encoding="utf-8") as f:
            return f.read()

    def __enter__(self):
        self.arrancar()
        return self

    def __exit__(self, *exc):
        self.parar()


def main():
    parser = argparse.ArgumentParser(description="Levanta el SRB completo en localhost")
    parser.add_argument("--replicas", type=int, default=2, help="réplicas del RMC")
    parser.add_argument("--sin-respaldo", action="store_true", help="sin GT de respaldo")
    parser.add_argument("--sin-replica-lectura", action="store_true", help="sin réplica de lectura")
    args = parser.parse_args()

    sistema = Sistema(args.replicas, not args.sin_respaldo, not args.sin_replica_lectura)
    sistema.arrancar()
    print(f"SRB local en marcha. Logs y base de datos en {sistema.carpeta}")
    print(f"Cliente: python3 cliente.py --id C1 --gt {','.join(sistema.dirs_gt)} --duracion 1")
    print("Para ver la BD: SRB_PG_BD=" + sistema.nombre_bd + " python3 ver_bd.py")
    print("Para simular una falla: kill -9 <pid>  (pids abajo). Ctrl+C detiene todo.")
    for nombre, p in sistema.procesos.items():
        print(f"  {nombre:<16} pid {p.pid}")
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        sistema.parar()


if __name__ == "__main__":
    main()
