# SRB · Sistema de Reserva de Boletos

Proyecto de **Introducción a los Sistemas Distribuidos** · Pontificia Universidad Javeriana · Prof. Rafael Páez.

Integrantes: Julián Santiago León Pérez · Harold Alejandro Vargas Martínez · Matias

Sistema distribuido en tres capas que permite consultar y reservar asientos de eventos. Los procesos se comunican con **ZeroMQ (pyzmq)** sobre TCP y los mensajes viajan en JSON.

> **Estado actual: Entrega 1** — arquitectura base con consulta y reserva, sin tolerancia a fallas.
> Avance por commits en [`docs/plan_de_trabajo.md`](docs/plan_de_trabajo.md).

## Arquitectura

| VM | Capa | Procesos | Puertos (bind) |
|---|---|---|---|
| VM1 | Consumidores | `cliente.py` (1 a 8 procesos) | ninguno, solo se conectan |
| VM2 | Lógica de negocio | `gestor_transacciones.py`, `servicio_rmc.py`, `servicio_cancelaciones.py`* | 5557 ROUTER · 5556 REP |
| VM3 | Almacenamiento | `servicio_persistencia.py` + `datos/events.json` | 5555 REP |

\* Cancelaciones y notificaciones se implementan en la Entrega 2 (puertos 5558, 5559 y 5560).

Canal síncrono (consulta y reserva):

```
Cliente (REQ) → GT (ROUTER :5557 | DEALER) → RMC (REP :5556 | REQ) → Persistencia (REP :5555)
```

Diagramas en [`docs/diagramas/`](docs/diagramas/) y formato de mensajes en [`docs/protocolo.md`](docs/protocolo.md).

## Estructura

```
├── config.py                  IPs, puertos y constantes del sistema
├── comun.py                   formato de mensajes y línea de log
├── cliente.py                 VM1 · generador de carga
├── vm1_escenario.sh           VM1 · lanza los escenarios de 3, 5 y 8 clientes
├── gestor_transacciones.py    VM2 · Gestor de Transacciones
├── servicio_rmc.py            VM2 · Reserva, Modificación y Consultas
├── servicio_cancelaciones.py  VM2 · Entrega 2
├── servicio_persistencia.py   VM3 · acceso a events.json
├── generar_bd.py              VM3 · crea la BD inicial (50 eventos)
├── ver_bd.py                  VM3 · muestra libres y ocupados
├── metricas.py                procesa los CSV de resultados
├── scripts/
│   ├── preparar_vm.sh         instala dependencias en una VM
│   └── probar_puertos.sh      verifica que los puertos respondan
├── tests/                     pruebas con pytest
├── docs/                      protocolo, plan de trabajo y diagramas
├── datos/                     aquí se genera events.json (no se versiona)
└── resultados/                aquí quedan los CSV de cada corrida (no se versionan)
```

## Requisitos

- Python 3.10 o superior (Ubuntu 22.04 trae 3.10).
- Dependencias: `pip3 install -r requirements.txt`

## Configuración de IPs

Las direcciones se leen de variables de entorno. **Si no se definen, todo usa `127.0.0.1`**, así que el sistema completo puede correr en un solo computador para desarrollar.

En cada VM, agregar una vez al final de `~/.bashrc` y abrir una terminal nueva:

```bash
export SRB_IP_VM2=<IP de la VM2>
export SRB_IP_VM3=<IP de la VM3>
```

## Ejecución

Cada servicio queda corriendo en su propia terminal. Se arranca primero lo que hace bind: **VM3 → VM2 → VM1**.

| Paso | VM | Comando |
|---|---|---|
| 1 | VM3 | `python3 generar_bd.py` |
| 2 | VM3 | `python3 ver_bd.py` (estado inicial) |
| 3 | VM3 | `python3 servicio_persistencia.py` |
| 4 | VM2 | `python3 servicio_rmc.py` |
| 5 | VM2 | `python3 gestor_transacciones.py` |
| 6 | VM1 | `./scripts/probar_puertos.sh` |
| 7 | VM1 | `./vm1_escenario.sh 3` (luego 5 y 8) |
| 8 | VM3 | `python3 ver_bd.py` (estado final) |
| 9 | — | `python3 metricas.py resultados/` |

Un cliente suelto:

```bash
python3 cliente.py --id C1 --rpm 20 --modo fija --pct-consulta 50 --pct-reserva 50 --duracion 3
```

Para detener un servicio: `Ctrl+C`.

### En un solo computador (desarrollo)

Mismos pasos, todos en terminales del mismo equipo y sin definir las variables de entorno. En Windows se usa `python` en vez de `python3`, y `vm1_escenario.sh` se ejecuta desde Git Bash o WSL.

## Pruebas

```bash
python3 -m pytest
```

Casos de prueba del informe (Tabla 3): U1, U2, I1, F1, C1, D1, R1, P1 y P2 en esta entrega.

## Métricas (Tabla 1 del enunciado)

Por cada escenario (3, 5 y 8 clientes), corridas de 3 minutos, 3 repeticiones:

- Tiempo promedio de respuesta y desviación estándar de consultas y de reservas (medido en el cliente).
- TPM de consultas y de reservas (medido en el GT).
