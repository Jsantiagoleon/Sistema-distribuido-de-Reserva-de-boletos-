#!/usr/bin/env bash
# Caso de prueba D1: verifica que los puertos de la VM2 y la VM3 respondan.
# Se ejecuta desde la VM1 (o la VM2) con los servicios ya corriendo.
#
# Uso:   ./scripts/probar_puertos.sh

IP_VM2="${SRB_IP_VM2:-127.0.0.1}"
IP_VM3="${SRB_IP_VM3:-127.0.0.1}"

probar () {
  if nc -z -w 2 "$1" "$2" 2>/dev/null; then
    echo "OK     $1:$2  $3"
  else
    echo "FALLA  $1:$2  $3"
  fi
}

probar "$IP_VM3" 5555 "Persistencia (REP)"
probar "$IP_VM2" 5556 "RMC (REP)"
probar "$IP_VM2" 5557 "GT síncrono (ROUTER)"
# Entrega 2:
# probar "$IP_VM2" 5558 "GT asíncrono (ROUTER)"
# probar "$IP_VM2" 5560 "Notificaciones (PUB)"
