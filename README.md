# SRB · Sistema de Reserva de Boletos

Primera entrega: arquitectura base con operaciones de consulta y reserva, desplegada en tres máquinas virtuales.

| VM | IP | Programas |
|---|---|---|
| VM1 | — | `cliente.py`, `vm1_escenario.sh` |
| VM2 | 10.43.100.247 | `servicio_rmc.py`, `gestor_transacciones.py` |
| VM3 | 10.43.99.241 | `generar_bd.py`, `servicio_persistencia.py`, `ver_bd.py` |

## Requisitos

En las tres VMs (Ubuntu):

```bash
sudo apt install -y python3 python3-zmq
```

Copiar la carpeta del proyecto a las tres VMs. Las IP de la VM2 y la VM3 están en `config.py`.

En la VM1, preparar el script de escenarios:

```bash
sed -i 's/\r$//' vm1_escenario.sh
chmod +x vm1_escenario.sh
```

## Ejecución

Cada servicio se ejecuta en su propia terminal, en este orden.

**1. VM3**

```bash
python3 generar_bd.py
python3 servicio_persistencia.py
```

**2. VM2, terminal 1**

```bash
python3 servicio_rmc.py
```

**3. VM2, terminal 2**

```bash
python3 gestor_transacciones.py
```

**4. VM1**

```bash
./vm1_escenario.sh 3
./vm1_escenario.sh 5
./vm1_escenario.sh 8
```

Antes de cada escenario, reiniciar la base de datos en la VM3 (detener la persistencia con Ctrl+C y repetir el paso 1).

## Estado de la base de datos

En la VM3, en otra terminal, durante la prueba:

```bash
watch -n 2 "python3 ver_bd.py | tail -1"
```

Estado completo:

```bash
python3 ver_bd.py
```

## Métricas

VM1 (usar la carpeta que imprime el escenario):

```bash
python3 metricas.py clientes resultados/esc3_AAAAMMDD_HHMMSS
```

VM2:

```bash
python3 metricas.py gestor resultados/gt_metricas.csv
mv resultados/gt_metricas.csv resultados/gt_esc3.csv
```


## Prueba con un solo cliente en VM1

En la VM1, una consulta y una reserva:

```bash
python3 cliente.py --id C1 --pct-consulta 100 --pct-reserva 0 --duracion 0.01
python3 cliente.py --id C1 --pct-consulta 0 --pct-reserva 100 --duracion 0.01
```

Un cliente con parámetros propios:

```bash
python3 cliente.py --id C1 --rpm 20 --pct-consulta 50 --pct-reserva 50 --duracion 1
```


matar proceso: pkill -f cliente.py

