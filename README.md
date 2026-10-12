# SRB · Sistema de Reserva de Boletos

## Requisitos

Python 3 y pyzmq en las tres VMs:

```bash
pip3 install -r requirements.txt
```

## Configurar las IPs

En la VM1 y la VM2, agregar al final de `~/.bashrc` y abrir una terminal nueva:

```bash
export SRB_IP_VM2=<IP de la VM2>
export SRB_IP_VM3=<IP de la VM3>
```

## Ejecución

Cada servicio se ejecuta en su propia terminal, en este orden:

**VM3**

```bash
python3 generar_bd.py
python3 ver_bd.py
python3 servicio_persistencia.py
```

**VM2**

```bash
python3 servicio_rmc.py
python3 gestor_transacciones.py
```

**VM1**

```bash
chmod +x vm1_escenario.sh
./vm1_escenario.sh 3
./vm1_escenario.sh 5
./vm1_escenario.sh 8
```

Para ver el estado final de la base de datos, en la VM3:

```bash
python3 ver_bd.py
```

Los tiempos de cada cliente quedan en `resultados/` de la VM1 y los del Gestor en `resultados/` de la VM2.
