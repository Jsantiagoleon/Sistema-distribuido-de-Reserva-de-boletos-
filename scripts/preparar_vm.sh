#!/usr/bin/env bash
# Prepara una VM (Ubuntu) para correr el SRB. Se ejecuta una vez en cada VM.
#
# Uso:   ./scripts/preparar_vm.sh

set -e
cd "$(dirname "$0")/.."

echo "== Versión de Python =="
python3 --version

echo "== Instalando dependencias =="
if ! command -v pip3 >/dev/null 2>&1; then
  sudo apt update && sudo apt install -y python3-pip
fi
pip3 install --user -r requirements.txt

echo "== Herramientas de red (nc para probar puertos) =="
command -v nc >/dev/null 2>&1 || sudo apt install -y netcat-openbsd

echo "== Sincronización de reloj (NTP) =="
timedatectl | grep -i -E "synchronized|NTP" || true

echo "== IP de esta VM =="
hostname -I

echo
echo "Listo. Recuerde definir en ~/.bashrc las IP de las otras VMs:"
echo "  export SRB_IP_VM2=<IP de la VM2>"
echo "  export SRB_IP_VM3=<IP de la VM3>"
