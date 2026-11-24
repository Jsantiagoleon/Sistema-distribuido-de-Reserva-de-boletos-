# Cambios en el código por las correcciones de la primera entrega

El informe corregido promete cosas que el código debía cumplir. Esto es lo que se cambió y qué comentario
del profesor atiende (C#) cada cambio.

| Comentario | Qué cambió | Dónde |
|---|---|---|
| C10 Métricas: qué se mide y cómo | Se separa el **tiempo de respuesta** (cliente), el **tiempo de servicio** (GT) y el aporte de **red y colas** (resta de promedios). Nuevas columnas `gt_media_ms` y `red_colas_ms` en las tablas y en el CSV. | `metricas.py` |
| C10 / C13 Promedios y TPM correctos | El TPM del GT se calcula con la ventana del **propio reloj del GT** (antes se cruzaba con la ventana de los clientes y exigía NTP). Ya no hace falta sincronizar las VM. Aviso si `gt_metricas.csv` trae más de una corrida. | `metricas.py` |
| C13 Promedio de varias repeticiones | La media combinada es la media de las medias por repetición y la desviación es la que hay **entre** repeticiones (barras de error). Con una sola repetición, la de las muestras. | `metricas.py` |
| C12 Cuándo se satura | `metricas.py resumen` imprime el punto de saturación de P2 (primer número de clientes cuyo siguiente aumento sube el TPM menos de `--umbral`, 5 % por defecto). | `metricas.py` |
| C11 Gráficas | Se renombraron y completaron como en la Tabla 6 del informe: G1 latencia por tipo, G2 TPM, **G3 CPU y memoria (vmstat) de cada VM** (nueva), G4 capacidad con la saturación marcada, G5 falla, **G6 base vs escalable** (nueva). Se eliminó el comando `g1g2`. | `graficas.py` |
| C10 / C12 vmstat | Intervalo por defecto de 1 s (el informe dice 1 s; antes 2 s). | `monitor_recursos.sh` |
| C6 / C7 Modelo de fallas | **T3**: cae Persistencia → ERROR "persistencia no responde" en ~3 s, el GT no se bloquea y todo se recupera al volver. | `pruebas/test_srb.py` |
| C8 No repetir cambios del principal | **T4**: la misma solicitud llega a dos GT activos a la vez y se ejecuta una sola vez (una reserva, respuestas idénticas). | `pruebas/test_srb.py`, `lanzar_local.py` (`doble_activo`) |
| Documentación | README: sin requisito de NTP, definiciones de métricas, comandos G1–G6, T1–T4, borrar `gt_metricas.csv` antes de cada corrida. La prueba de la réplica de lectura usaba el id "T3"; ahora "RL". | `README.md` |

No cambió el comportamiento del GT, el RMC, Persistencia ni Cancelaciones: las pruebas de T1/T2 ya cubrían C6–C9 y
pasan igual. Resultado de la suite local: 14 pruebas, todas aprobadas.

Lo que sigue sin poder cambiarse desde el código: Persistencia es un punto único de falla (fuera del alcance del
enunciado) y los resultados de P1/P2 hay que medirlos en las 3 VM.


---

# Cambio de la segunda entrega: base de datos PostgreSQL

El profesor pidió una base de datos real porque un archivo JSON no es adecuado en un sistema distribuido. Se reemplazó
`events.json` por **PostgreSQL** (motor cliente-servidor) en la VM3. El protocolo ZeroMQ entre los componentes no cambió.

| Qué | Cambio | Dónde |
|---|---|---|
| Almacenamiento | Tablas `eventos`, `ocurrencias`, `reservas` y `solicitudes_procesadas` con llaves primarias, llaves foráneas y `CHECK` (libres + ocupados = disponibles) | `bd.py` |
| Atomicidad | Cada operación que escribe es una transacción: descuento condicional de asientos (`UPDATE ... WHERE asientos_libres >= n`), reserva y respuesta guardada, todo o nada. Antes se reescribía el JSON completo en cada operación | `servicio_persistencia.py` |
| Idempotencia | La respuesta se guarda en la misma transacción; sobrevive a reinicios de Persistencia | `servicio_persistencia.py` |
| Concurrencia | Además del bucle único, la base protege el cupo con UPDATE condicional, `FOR UPDATE` y las restricciones `CHECK` | `servicio_persistencia.py`, `bd.py` |
| Falla de PostgreSQL | `ERROR "base de datos no disponible"` con `reintentar: true`; reconexión automática; la réplica de lectura se resincroniza | `servicio_persistencia.py` |
| Datos iniciales y consulta | `generar_bd.py` crea/reinicia las tablas; `ver_bd.py` y `prueba_concurrencia.py --bd` consultan PostgreSQL | `generar_bd.py`, `ver_bd.py`, `prueba_concurrencia.py` |
| Instalación | `preparar_postgres.sh` (instala el servidor, crea usuario y base) y `psycopg2-binary` en `requirements.txt` | `preparar_postgres.sh`, `requirements.txt` |
| Pruebas | Cada prueba crea y borra su propia base PostgreSQL temporal; las 14 pruebas pasan | `lanzar_local.py`, `pruebas/test_srb.py` |
| Configuración | `SRB_PG_HOST/PUERTO/BD/USUARIO/CLAVE` (reemplazan `SRB_RUTA_BD`) | `config.py` |

Verificado además a mano: con PostgreSQL apagado de golpe la reserva recibe `ERROR` reintentable al instante y las
consultas del mes siguen respondiendo desde la réplica; al volver PostgreSQL se retoma sin intervención; tras un
`kill -9` de Persistencia los asientos y reservas siguen intactos. Costo medido en local: ~1,7 ms por reserva confirmada.
