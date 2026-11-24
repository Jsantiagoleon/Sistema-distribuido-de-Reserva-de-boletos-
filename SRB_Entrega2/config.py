"""
Configuración del SRB (Entrega 2): IPs, puertos, tiempos y constantes.

Despliegue:
  VM1  10.43.99.226   clientes (generadores de carga)
  VM2  10.43.100.247  GT principal, réplicas del RMC, Servicio de Cancelaciones
  VM3  10.43.99.241   Persistencia (principal y réplica de lectura), GT de respaldo,
                      servidor PostgreSQL (la base de datos)

Las IPs se pueden cambiar sin tocar el código con las variables de entorno
SRB_IP_VM2 y SRB_IP_VM3 (útil para probar todo en localhost).
"""

import os

# ---------------------------------------------------------------- máquinas
IP_VM2 = os.getenv("SRB_IP_VM2", "10.43.100.247")
IP_VM3 = os.getenv("SRB_IP_VM3", "10.43.99.241")

# ---------------------------------------------------------------- puertos
PUERTO_PERSISTENCIA = 5555          # REP de Persistencia (VM3)
PUERTO_RMC = 5556                   # REP del RMC; la réplica i usa 5556 + 10·i (VM2)
PUERTO_GT = 5557                    # ROUTER síncrono del GT (clientes REQ)
PUERTO_GT_ASINCRONO = PUERTO_GT + 1  # 5558 ROUTER asíncrono del GT (clientes DEALER)
PUERTO_CANCELACIONES = 5559         # PULL del Servicio de Cancelaciones (el GT le hace PUSH)
PUERTO_NOTIFICACIONES = 5560        # PUB de notificaciones (tópico = id_cliente)
PUERTO_LATIDO_GT = PUERTO_GT + 4    # 5561 PUB de latidos del GT activo
PUERTO_LATIDO_RMC = 5650            # PUB de latidos de la réplica i del RMC: 5650 + i
PUERTO_REPLICA_PUB = 5571           # PUB de deltas de Persistencia hacia su réplica de lectura
PUERTO_REPLICA_LECTURA = 5572       # REP de la réplica de lectura (consultas del mes)


def puerto_rmc(indice):
    return PUERTO_RMC + 10 * indice


def puerto_latido_rmc(indice):
    return PUERTO_LATIDO_RMC + indice


# ---------------------------------------------------------------- direcciones
# Las usa el RMC y el Servicio de Cancelaciones (VM2) para hablar con Persistencia (VM3)
DIR_PERSISTENCIA = f"tcp://{IP_VM3}:{PUERTO_PERSISTENCIA}"
DIR_REPLICA_LECTURA = f"tcp://{IP_VM3}:{PUERTO_REPLICA_LECTURA}"
DIR_REPLICA_PUB = f"tcp://{IP_VM3}:{PUERTO_REPLICA_PUB}"
# Las usan los clientes: primero el GT principal y después el de respaldo
DIRS_GT = [f"tcp://{IP_VM2}:{PUERTO_GT}", f"tcp://{IP_VM3}:{PUERTO_GT}"]
DIR_NOTIFICACIONES = f"tcp://{IP_VM2}:{PUERTO_NOTIFICACIONES}"
# La usa el GT (cualquiera de los dos) para empujar las cancelaciones
DIR_CANCELACIONES = f"tcp://{IP_VM2}:{PUERTO_CANCELACIONES}"

# ---------------------------------------------------------------- datos iniciales
# 50 eventos en un mes, 20 con dos ocurrencias, 100 asientos por ocurrencia
ANIO = 2026
MES = 11
NUM_EVENTOS = 50
EVENTOS_CON_DOS_OCURRENCIAS = 20
ASIENTOS_POR_OCURRENCIA = 100

# ---------------------------------------------------------------- base de datos (PostgreSQL)
# Servidor PostgreSQL en la VM3; solo Persistencia (y generar_bd.py / ver_bd.py) se conectan a él.
# Se pueden cambiar con variables de entorno sin tocar el código.
PG_HOST = os.getenv("SRB_PG_HOST", "127.0.0.1")
PG_PUERTO = int(os.getenv("SRB_PG_PUERTO", "5432"))
PG_BD = os.getenv("SRB_PG_BD", "srb")
PG_USUARIO = os.getenv("SRB_PG_USUARIO", "srb")
PG_CLAVE = os.getenv("SRB_PG_CLAVE", "srb")
PG_TIMEOUT_CONEXION_S = 3

# ---------------------------------------------------------------- archivos
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
DIR_RESULTADOS = os.getenv("SRB_DIR_RESULTADOS", os.path.join(DIR_BASE, "resultados"))
# Cuántos id_solicitud se conservan en la tabla solicitudes_procesadas para detectar repeticiones
# (los reintentos ocurren a los pocos segundos, así que no hace falta guardar todo el historial)
MAX_SOLICITUDES_GUARDADAS = 5000

# ---------------------------------------------------------------- tiempos (milisegundos)
TIMEOUT_CLIENTE_MS = 5000           # el cliente espera 5 s antes de pasar al otro GT
MAX_INTENTOS_CLIENTE = 2            # intento original + un reintento en el otro GT
TIMEOUT_PERSISTENCIA_MS = 3000      # el RMC y Cancelaciones esperan 3 s a Persistencia
TIMEOUT_REPLICA_LECTURA_MS = 1500   # el RMC espera 1,5 s a la réplica y si no, usa Persistencia
INTERVALO_LATIDO_MS = 1000          # cada proceso vigilado emite un latido por segundo
TIMEOUT_LATIDO_GT_MS = 2000         # el GT pasivo asume el rol tras 2 s sin latidos
TIMEOUT_LATIDO_RMC_MS = 3000        # el GT da por caída una réplica tras 3 latidos perdidos
ESPERA_INICIAL_PRINCIPAL_MS = 1500  # al arrancar, cuánto escucha cada GT antes de activarse
ESPERA_INICIAL_RESPALDO_MS = 3500   # (el respaldo espera más para no competir con el principal)
TIMEOUT_NOTIFICACION_MS = 10000     # el cliente reenvía la cancelación si no llega la notificación
MAX_REENVIOS_CANCELACION = 2
REINTENTOS_CANCELACIONES = 3        # intentos de Cancelaciones hacia Persistencia

# ---------------------------------------------------------------- carga
MIN_RPM = 20                        # al menos 20 solicitudes por minuto por cliente
