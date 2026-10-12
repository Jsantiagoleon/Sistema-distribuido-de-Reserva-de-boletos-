"""
Configuración del SRB: IPs, puertos y constantes.

Las IP de las VMs se leen de variables de entorno. Si no existen se usa
127.0.0.1 y todo el sistema corre en un solo computador.
"""

import os

# Máquinas (VM1 = clientes, VM2 = GT y RMC, VM3 = Persistencia)
IP_VM2 = os.getenv("SRB_IP_VM2", "127.0.0.1")
IP_VM3 = os.getenv("SRB_IP_VM3", "127.0.0.1")

# Puertos
PUERTO_PERSISTENCIA = 5555   # VM3 · Persistencia · REP
PUERTO_RMC = 5556            # VM2 · RMC          · REP
PUERTO_GT = 5557             # VM2 · GT           · ROUTER

# Direcciones
DIR_GT = f"tcp://{IP_VM2}:{PUERTO_GT}"                     # la usa el cliente
DIR_RMC = f"tcp://127.0.0.1:{PUERTO_RMC}"                  # la usa el GT (misma VM)
DIR_PERSISTENCIA = f"tcp://{IP_VM3}:{PUERTO_PERSISTENCIA}"  # la usa el RMC

# Datos iniciales: 50 eventos en un mes, 20 con dos ocurrencias, 100 asientos
ANIO = 2026
MES = 11
NUM_EVENTOS = 50
EVENTOS_CON_DOS_OCURRENCIAS = 20
ASIENTOS_POR_OCURRENCIA = 100

# Archivos
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_BD = os.path.join(DIR_BASE, "events.json")
DIR_RESULTADOS = os.getenv("SRB_DIR_RESULTADOS", os.path.join(DIR_BASE, "resultados"))

# Tiempos y carga
TIMEOUT_CLIENTE_MS = 5000   # el cliente espera como máximo 5 s
MIN_RPM = 20                # al menos 20 solicitudes por minuto por cliente
