"""
Configuración central del SRB (Sistema de Reserva de Boletos).

Todas las direcciones, puertos y constantes del sistema están aquí, para no
repetirlas en cada programa.

Las IP de las VMs todavía no están definidas, así que se leen de variables de
entorno. Si no existen, se usa 127.0.0.1 y todo el sistema corre en un solo
computador, lo que sirve para desarrollar y probar antes de tener las VMs.

En cada VM basta con agregar al final de ~/.bashrc:
    export SRB_IP_VM2=<IP de la VM2>
    export SRB_IP_VM3=<IP de la VM3>
"""

import os

# ---------------------------------------------------------------------------
# Máquinas (VM1 = consumidores, VM2 = lógica de negocio, VM3 = almacenamiento)
# ---------------------------------------------------------------------------
IP_VM2 = os.getenv("SRB_IP_VM2", "127.0.0.1")
IP_VM3 = os.getenv("SRB_IP_VM3", "127.0.0.1")

# ---------------------------------------------------------------------------
# Puertos (lado que hace bind)
# ---------------------------------------------------------------------------
PUERTO_PERSISTENCIA = 5555      # VM3 · Persistencia            · REP
PUERTO_RMC = 5556               # VM2 · RMC                     · REP
PUERTO_GT_SINCRONO = 5557       # VM2 · GT, consulta/reserva    · ROUTER
PUERTO_GT_ASINCRONO = 5558      # VM2 · GT, cancelaciones       · ROUTER (Entrega 2)
PUERTO_COLA_CANCELACIONES = 5559  # VM2 · GT -> Cancelaciones   · PUSH   (Entrega 2)
PUERTO_NOTIFICACIONES = 5560    # VM2 · Cancelaciones -> Cliente · PUB    (Entrega 2)


def direccion_bind(puerto):
    """Dirección para abrir un puerto en todas las interfaces de la máquina."""
    return f"tcp://*:{puerto}"


def direccion(ip, puerto):
    """Dirección para conectarse (connect) a un puerto de otra máquina."""
    return f"tcp://{ip}:{puerto}"


# Direcciones a las que se conecta cada componente
DIR_GT_SINCRONO = direccion(IP_VM2, PUERTO_GT_SINCRONO)          # usa el cliente
DIR_GT_ASINCRONO = direccion(IP_VM2, PUERTO_GT_ASINCRONO)        # usa el cliente (E2)
DIR_NOTIFICACIONES = direccion(IP_VM2, PUERTO_NOTIFICACIONES)    # usa el cliente (E2)
DIR_RMC = direccion("127.0.0.1", PUERTO_RMC)                     # usa el GT (misma VM)
DIR_COLA_CANCELACIONES = direccion("127.0.0.1", PUERTO_COLA_CANCELACIONES)  # (E2)
DIR_PERSISTENCIA = direccion(IP_VM3, PUERTO_PERSISTENCIA)        # usan RMC y Cancelaciones

# ---------------------------------------------------------------------------
# Datos iniciales (enunciado: 50 eventos en un mes, 20 con dos ocurrencias,
# 100 asientos por evento)
# ---------------------------------------------------------------------------
ANIO = 2026
MES = 11                        # noviembre
NUM_EVENTOS = 50
EVENTOS_CON_DOS_OCURRENCIAS = 20  # E1..E20 tienen dos; E21..E50 una
ASIENTOS_POR_OCURRENCIA = 100
MIN_ASIENTOS_POR_RESERVA = 1
MAX_ASIENTOS_POR_RESERVA = 4    # lo que pide al azar el generador de carga

# ---------------------------------------------------------------------------
# Rutas de archivos
# ---------------------------------------------------------------------------
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_BD = os.getenv("SRB_RUTA_BD", os.path.join(DIR_BASE, "datos", "events.json"))
DIR_RESULTADOS = os.getenv("SRB_DIR_RESULTADOS", os.path.join(DIR_BASE, "resultados"))

# ---------------------------------------------------------------------------
# Tiempos y carga
# ---------------------------------------------------------------------------
TIMEOUT_CLIENTE_MS = 5000       # el cliente espera como máximo 5 s
ESPERA_NOTIFICACION_S = 10      # reenvío de cancelación sin notificación (E2)
MIN_RPM = 20                    # al menos 20 solicitudes por minuto por cliente
DURACION_MIN_DEFECTO = 3        # el enunciado pide cargas de 2-3 min
DESCARTE_INICIAL_S = 15         # se descartan los primeros 15 s en las métricas
