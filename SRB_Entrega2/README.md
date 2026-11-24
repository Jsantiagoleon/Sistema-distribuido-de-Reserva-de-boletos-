# SRB · Sistema de Reserva de Boletos — Segunda entrega

Python 3 + ZeroMQ (pyzmq) + PostgreSQL. Arquitectura de tres capas sobre tres máquinas, con elementos de
escalabilidad (réplicas del RMC, réplica de lectura de Persistencia) y de tolerancia a fallas (GT
activo-pasivo, vigilancia de réplicas del RMC, reintentos idempotentes). Los datos viven en una base de
datos PostgreSQL (servidor cliente-servidor) en la VM3; ya no se usa ningún archivo JSON.

## 1. Despliegue

| Máquina | IP | Procesos |
|---|---|---|
| VM1 | 10.43.99.226 | `cliente.py` (uno por cliente simulado) |
| VM2 | 10.43.100.247 | GT principal, réplicas del RMC, Servicio de Cancelaciones |
| VM3 | 10.43.99.241 | **Servidor PostgreSQL**, Persistencia (principal), réplica de lectura, **GT de respaldo** |

El GT de respaldo está en una máquina distinta a la del principal. Las IPs se pueden cambiar con las
variables de entorno `SRB_IP_VM2` y `SRB_IP_VM3` (sin tocar el código).

| Puerto | Qué es | Patrón |
|---|---|---|
| 5555 | Persistencia (VM3) | REP ← REQ del RMC y de Cancelaciones |
| 5556 + 10·i | Réplica i del RMC (VM2) | REP ← DEALER del GT |
| 5557 | GT, canal síncrono | ROUTER ← REQ de los clientes |
| 5558 | GT, canal asíncrono | ROUTER ← DEALER de los clientes (cancelaciones) |
| 5559 | Servicio de Cancelaciones | PULL ← PUSH del GT |
| 5560 | Notificaciones | PUB → SUB de los clientes (tópico = id del cliente) |
| 5561 | Latido del GT activo | PUB → SUB del otro GT |
| 5650 + i | Latido de la réplica i del RMC | PUB → SUB del GT |
| 5571 / 5572 | Réplica de lectura | PUB de deltas de Persistencia / REP de consultas |
| 5432 | PostgreSQL (VM3) | Solo lo usa Persistencia, desde la misma VM3 (127.0.0.1) |

## 2. Requisitos

```
pip install -r requirements.txt        # pyzmq, psycopg2-binary (matplotlib solo para graficas.py)
```
Además, en la VM3 hace falta el servidor **PostgreSQL** (ver "Base de datos" abajo).
No hace falta sincronizar los relojes de las máquinas: `metricas.py` calcula la ventana de medición de los
clientes con el reloj de la VM1 y la del GT con el de la VM2, y el aporte de la red se obtiene restando
**promedios** (nunca marcas de hora de máquinas distintas).

## 3. Base de datos (PostgreSQL en la VM3)

Persistencia es el único proceso que habla con la base de datos. Las tablas (`bd.py`):

| Tabla | Contenido |
|---|---|
| `eventos` | 50 eventos (`id_evento`, `num_ocurrencias`) |
| `ocurrencias` | 70 ocurrencias: fecha, asientos disponibles / libres / ocupados. Restricciones `CHECK`: libres ≥ 0, ocupados ≥ 0 y libres + ocupados = disponibles |
| `reservas` | `id_reserva` (R1, R2, ... con una secuencia), cliente, asientos, evento, ocurrencia y estado (`activa` / `cancelada`) |
| `solicitudes_procesadas` | La respuesta de cada operación que escribió, indexada por `id_solicitud` (idempotencia); se conservan las últimas 5.000 |

**Instalación (una sola vez, en la VM3, necesita `sudo`):** `./preparar_postgres.sh` instala PostgreSQL, crea el usuario
`srb` (clave `srb`) y la base `srb` e instala el driver. Después `python3 generar_bd.py` crea las tablas con los datos
iniciales. Se puede apuntar a otro servidor o usuario con `SRB_PG_HOST`, `SRB_PG_PUERTO`, `SRB_PG_BD`,
`SRB_PG_USUARIO` y `SRB_PG_CLAVE`.

**Consultar a mano:** `python3 ver_bd.py` o, con `psql`:
```
PGPASSWORD=srb psql -h 127.0.0.1 -U srb srb -c "select id_evento, numero, asientos_libres, asientos_ocupados from ocurrencias order by length(id_evento), id_evento, numero"
PGPASSWORD=srb psql -h 127.0.0.1 -U srb srb -c "select * from reservas order by length(id_reserva), id_reserva limit 20"
```

## 4. Ejecución

Cada línea es una terminal. Orden: primero VM3, luego VM2.

**Arquitectura escalable (completa)**

```
# VM3
python3 generar_bd.py                              # crea las tablas en PostgreSQL (50 eventos, 70 ocurrencias, 7.000 asientos)
python3 servicio_persistencia.py                   # Persistencia principal (se conecta a PostgreSQL)
python3 servicio_persistencia.py --rol replica     # réplica de lectura
python3 gestor_transacciones.py --rol respaldo --replicas 2   # GT de respaldo (queda pasivo)

# VM2
python3 servicio_cancelaciones.py
python3 servicio_rmc.py 0 --replica-lectura
python3 servicio_rmc.py 1 --replica-lectura
python3 gestor_transacciones.py --replicas 2       # GT principal (se activa a los 1,5 s)

# VM1
python3 cliente.py --id C1 --duracion 1            # un cliente; usa los dos GT (principal y respaldo)
```

**Arquitectura base** (un GT, una réplica del RMC, sin réplica de lectura): igual pero solo
`servicio_persistencia.py` en VM3 y, en VM2, `servicio_cancelaciones.py`, `servicio_rmc.py 0`
y `gestor_transacciones.py --replicas 1`.

**Ver la base de datos (VM3):** `python3 ver_bd.py` muestra libres y ocupados por ocurrencia.
**Reiniciar la base de datos:** detener Persistencia, `python3 generar_bd.py` (borra las tablas y las vuelve a
crear), volver a iniciar Persistencia (la réplica de lectura se resincroniza sola). PostgreSQL debe estar encendido
(`systemctl status postgresql`).

**Todo en una sola máquina (para ensayar o depurar):** `python3 lanzar_local.py` levanta todos los
procesos en localhost (el respaldo en el puerto 6557) y muestra los pid y el comando del cliente. Crea una base
PostgreSQL temporal (`srb_local_xxxx`) y la borra al terminar; necesita un PostgreSQL accesible con el usuario `srb`
(rol con `CREATEDB`, como lo deja `preparar_postgres.sh`).

### Cliente

```
python3 cliente.py --id C1 [--rpm 20] [--modo fija|cerrado] [--duracion 3]
       [--pct-consulta 50 --pct-reserva 50 --pct-modificacion 0 --pct-cancelacion 0]
       [--gt tcp://IP:5557,tcp://IP2:5557] [--semilla N]
```
Los cuatro porcentajes deben sumar 100. Una modificación o cancelación necesita una reserva propia; si el
cliente todavía no tiene ninguna, reserva. La modificación cambia el número de asientos **o** pasa la
reserva a la otra ocurrencia del evento (conservando los asientos; los eventos de una sola ocurrencia solo
admiten cambiar asientos). Al terminar, el cliente espera las notificaciones de cancelación pendientes.

## 5. Cómo funciona

- **Consulta / reserva / modificación (síncronas):** cliente REQ → GT ROUTER → réplica del RMC (DEALER del
  GT, por turnos entre las réplicas vivas) → Persistencia (REQ/REP) → PostgreSQL. La reserva consulta la
  disponibilidad y luego pide una confirmación condicional: Persistencia descuenta con un `UPDATE ... WHERE
  asientos_libres >= n`, por lo que dos réplicas del RMC nunca venden de más.
- **Cancelación (asíncrona):** cliente DEALER → GT ROUTER asíncrono, que responde `ACEPTADA` de inmediato y
  empuja la orden (PUSH) al Servicio de Cancelaciones; éste libera los asientos en Persistencia y publica la
  notificación (PUB) con el id del cliente como tópico.
- **Consultas del mes:** el RMC las envía a la réplica de lectura (se actualiza con los cambios que publica
  Persistencia; si no responde en 1,5 s, el RMC usa la principal).
- **Concurrencia:** cada proceso atiende en un solo hilo (el GT con un `zmq.Poller`); las réplicas del RMC
  son procesos separados; Persistencia procesa un mensaje a la vez y cada operación que escribe es **una
  transacción** de PostgreSQL (asientos, reserva y respuesta guardada, todo o nada); además la base impide por sí
  misma vender de más (UPDATE condicional, `CHECK` y bloqueo de filas con `FOR UPDATE`). Un hilo auxiliar del RMC solo emite latidos con su propio socket.

### Tolerancia a fallas

| Falla | Detección | Recuperación |
|---|---|---|
| GT principal | El GT de respaldo no recibe latidos (1 por segundo) durante 2 s | El respaldo abre sus puertos 5557/5558 (en la VM3; en localhost usa 6557/6558) y se activa. Los clientes, tras 5 s sin respuesta, reenvían la **misma** solicitud al otro GT y se quedan con él. |
| GT que regresa | Al arrancar escucha 1,5 s (principal) o 3,5 s (respaldo) | Si el otro GT está activo, queda pasivo y lo vigila; no hay dos GT activos. |
| Réplica del RMC | El GT no recibe 3 latidos seguidos (3 s) | El GT desconecta la réplica y reenvía a otra las solicitudes que tenía en curso; si la réplica regresa, se reincorpora. |
| Persistencia no responde | El RMC espera 3 s | Responde `ERROR` con `reintentar: true` y recrea su socket; Cancelaciones reintenta hasta 3 veces. Al volver, retoma los datos de PostgreSQL. |
| PostgreSQL no responde | Persistencia no logra conectarse o pierde la conexión | Responde `ERROR "base de datos no disponible"` con `reintentar: true`; las consultas del mes siguen saliendo de la réplica de lectura. Persistencia vuelve a conectarse sola cuando PostgreSQL regresa; lo que ya tenía confirmado (`COMMIT`) no se pierde y lo incompleto se deshace. |
| Notificación que no llega | El cliente espera 10 s | Reenvía la cancelación (máx. 2 veces) con el mismo id. |

**Sin repetir ni perder operaciones:** cada solicitud lleva un `id_solicitud` único que se conserva en los
reintentos. Persistencia guarda la respuesta de cada operación que escribe en la tabla `solicitudes_procesadas`,
dentro de la **misma transacción** que el cambio de asientos. Si el mismo id vuelve a llegar (aunque Persistencia
se haya reiniciado), devuelve la respuesta guardada sin volver a descontar asientos (también cuando la primera
ejecución agotó el cupo). Se conservan los últimos 5.000 ids.

**Durabilidad:** un `COMMIT` de PostgreSQL ya está en el registro de escritura (WAL) en disco. Si se cae Persistencia
(`kill -9`), reinicia la VM3 o se corta la red, lo confirmado sigue ahí; una transacción a medias se deshace.

**Límites conocidos:** el servidor PostgreSQL, Persistencia principal y el Servicio de Cancelaciones son únicos
(el enunciado exige tolerar la falla del GT y del RMC; con más tiempo se añadiría un standby de PostgreSQL en otra VM).
Las réplicas del RMC están en la VM2: la falla de **un proceso** se
tolera; si cae toda la VM2, para seguir atendiendo habría que correr una réplica del RMC en la VM3
(`python3 servicio_rmc.py 2` allí) y arrancar ambos GT con `--rmc 10.43.99.241:2`.

## 6. Pruebas

### Automáticas en una máquina (14 pruebas, ~1,5 min)

```
python3 -m unittest pruebas.test_srb -v
```
U1 (cupo, sin cupo, asientos fuera de rango), U2 (idempotencia), I1 (consulta de punta a punta), F1 (reservas),
F2 (modificación y cancelación con notificación), réplica de lectura, C1 (8 clientes, últimos asientos),
R1 (mensajes mal formados), T1 (cae el GT principal), T2 (cae una réplica del RMC), T3 (cae Persistencia: ERROR
"persistencia no responde" en 3 s, el GT no se bloquea y todo se recupera al volver), T4 (la misma solicitud llega a
dos GT activos a la vez y se ejecuta una sola vez) y resincronización de la réplica de lectura. Usan una base PostgreSQL temporal
(`srb_local_xxxx`, se borra al terminar) y no tocan la base `srb`. Con un servidor distinto al predeterminado, definir antes
`SRB_PG_PUERTO`, `SRB_PG_USUARIO`, etc.

### En las 3 VM

| Prueba | Cómo |
|---|---|
| D1 puertos | `nc -zv 10.43.99.241 5555` (desde VM2); `nc -zv 10.43.100.247 5557` y `5560` (desde VM1); `nc -zv 10.43.100.247 5556` y `5650` (desde VM3); `nc -zv 10.43.99.241 5561`. El 5557/5558 del respaldo solo abre cuando asume el rol. |
| U2 idempotencia | `python3 prueba_idempotencia.py --gt tcp://10.43.100.247:5557` (usa E50 y E48; reiniciar la BD después) |
| C1 concurrencia | `python3 prueba_concurrencia.py --gt tcp://10.43.100.247:5557` (usa E49; en VM3 añadir `--bd` para revisar también PostgreSQL) |
| R1 robustez | `python3 prueba_robustez.py --gt tcp://10.43.100.247:5557` |
| S1 sustentación | `python3 generar_bd.py`, `python3 ver_bd.py` y las terminales de GT, RMC y Persistencia a la vista |

### Rendimiento (P1 y P2)

```
./vm1_escenario.sh <3|5|8> <base|escalable> [repeticion=1] [duracion=3]     # P1: Tabla 1
./vm1_escenario.sh capacidad <N> <base|escalable> [duracion=1]              # P2: saturación, modo cerrado
./monitor_recursos.sh vmstat_vm2.txt                                        # CPU y memoria cada 1 s (en cada VM)
```
- 3 clientes: C1 y C2 solo consultan; C3 consulta y reserva. 5 clientes: 3 consultan; 2 reservan y modifican.
  8 clientes: 4 consultan; 4 reservan y modifican. Cada cliente a 20 solicitudes/min.
- Antes de **cada** corrida: reiniciar la BD (ver arriba) y, en la VM2, correr `./reiniciar_metricas_gt.sh`. No usar `rm`: el GT
  mantiene abierto `resultados/gt_metricas.csv` y, si se borra con el GT en marcha, sigue escribiendo en un archivo que
  ya no existe y la corrida queda sin datos del GT. El script vacía el archivo y le pone el encabezado; si quedara una
  corrida anterior, el TPM del GT se mezcla y `metricas.py` avisa. Al terminar, copiar el `gt_metricas.csv` de la VM2 a la
  carpeta de la corrida: `scp <usuario>@10.43.100.247:<ruta>/resultados/gt_metricas.csv resultados/<carpeta>/`.
- Resultados:
```
python3 metricas.py corrida resultados/<carpeta>
python3 metricas.py resumen resultados/base_esc* resultados/escalable_esc* --csv resumen.csv
python3 metricas.py resumen resultados/*_cap* --csv resumen_cap.csv
python3 graficas.py g1 resumen.csv        # G1: tiempo de respuesta por tipo vs clientes
python3 graficas.py g2 resumen.csv        # G2: TPM total y por tipo vs clientes
python3 graficas.py g3 vmstat_vm1.txt vmstat_vm2.txt vmstat_vm3.txt   # G3: CPU y memoria de cada VM
python3 graficas.py g4 resumen_cap.csv    # G4: capacidad (TPM vs clientes en modo cerrado) y saturación
python3 graficas.py g6 resumen.csv        # G6: base vs escalable (latencia y TPM)
# G5 (línea de tiempo de una falla): ver "Pruebas de falla"
```
`metricas.py resumen` imprime también el punto de saturación de la prueba P2: el primer número de clientes cuyo
siguiente aumento sube el TPM menos de 5 % (`--umbral` lo cambia).
`metricas.py` solo usa la biblioteca estándar y corre en las VM. `graficas.py` necesita matplotlib: se puede correr
en el PC copiando los `resumen*.csv` (y la carpeta de la corrida para `g5`).
Definiciones: **tiempo de respuesta** = medido en el cliente con `time.perf_counter()` (columna `Media ms`);
**tiempo de servicio** = lo que tarda el GT en resolver la solicitud (`GT ms`); **red y colas** = diferencia de ambas
medias (`Red ms`); **TPM** = solicitudes procesadas por minuto contadas en el GT (`gt_metricas.csv`) y contrastadas con el
conteo de los clientes. Se descartan los primeros 15 s de cada corrida. Al combinar repeticiones, la media es la de
las medias de cada repetición y la desviación estándar es la que hay **entre** repeticiones (barras de error).

### Pruebas de falla (T1, T2, T3 y T5) en las 3 VM

1. Arrancar la arquitectura escalable y lanzar un escenario con `./vm1_escenario.sh 5 escalable 1 3`.
2. Pasados unos 60 s, **T1**: `kill -9 <pid del GT principal>` en VM2 (`pgrep -f "gestor_transacciones.py"`).
   **T2**: `kill -9 <pid de servicio_rmc.py 0>`. **T3** (en VM3): `kill -9 <pid de servicio_persistencia.py>`;
   los clientes reciben `ERROR {"motivo": "persistencia no responde", "reintentar": true}` a los 3 s hasta que se
   vuelva a arrancar Persistencia (los datos siguen en PostgreSQL). **T5** (en VM3): `sudo systemctl stop postgresql`;
   los clientes reciben `ERROR {"motivo": "base de datos no disponible", "reintentar": true}` hasta `sudo systemctl start postgresql`.
   T4 (dos GT activos) solo se prueba en una máquina.
3. Mensajes esperados:
   - GT de respaldo: `*** GT RESPALDO ACTIVO: 2.0 s sin latidos del otro GT: se asume su rol (falla detectada). ...`
   - Cliente: `sin respuesta del GT en 5 s para <id>; reenvía la misma solicitud: pasa al GT tcp://...`
   - GT, T2: `!!! RMC-0 sin latidos hace 3.0 s: se da por CAÍDA. Reasigna N solicitud(es) en curso`
4. Volver a arrancar el proceso caído: el GT regresa como `PASIVO`; la réplica del RMC se reincorpora
   (`RMC-0 volvió a emitir latidos: se reincorpora al reparto`).
5. Evidencia: `gt_eventos.csv` (hora de cada detección), la columna `intentos` de `resultados_Cn.csv` (solicitudes
   reenviadas), `sin_respuesta` en `metricas.py corrida` (debe ser 0) y `python3 graficas.py g5 resultados/<carpeta> --marca <s>`.

## 7. Archivos

| Archivo | Contenido |
|---|---|
| `config.py` | IPs, puertos, tiempos y constantes |
| `modelos.py` | Clases del diagrama (Solicitud, Respuesta, Evento, Ocurrencia, Reserva) |
| `bd.py` | Esquema SQL, conexión a PostgreSQL y consultas compartidas |
| `generar_bd.py`, `ver_bd.py` | Crea/reinicia las tablas con los datos iniciales y las muestra |
| `preparar_postgres.sh` | Instala PostgreSQL en la VM3 y crea el usuario y la base `srb` |
| `servicio_persistencia.py` | Persistencia principal (`--rol replica`: réplica de lectura) |
| `servicio_rmc.py` | Réplica del RMC (consulta, reserva, modificación) |
| `gestor_transacciones.py` | GT principal / respaldo, latidos y vigilancia de réplicas |
| `servicio_cancelaciones.py` | Libera asientos y publica la notificación |
| `cliente.py` | Generador de carga y receptor de notificaciones |
| `metricas.py`, `graficas.py` | Cálculo de métricas y gráficas del informe |
| `vm1_escenario.sh`, `monitor_recursos.sh`, `reiniciar_metricas_gt.sh` | Escenarios de la Tabla 1, vmstat y reinicio de las métricas del GT |
| `prueba_*.py`, `pruebas/test_srb.py`, `lanzar_local.py` | Pruebas |
