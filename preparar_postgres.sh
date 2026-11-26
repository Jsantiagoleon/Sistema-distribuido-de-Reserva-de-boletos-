#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v psql >/dev/null 2>&1 || ! command -v pg_lsclusters >/dev/null 2>&1; then
    echo ">> Instalando PostgreSQL..."
    sudo apt-get update -y
    sudo apt-get install -y postgresql postgresql-contrib
fi
sudo systemctl enable --now postgresql >/dev/null 2>&1 || sudo service postgresql start || true

echo ">> Creando el usuario y la base de datos 'srb'..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'srb') THEN
    CREATE ROLE srb LOGIN PASSWORD 'srb' CREATEDB;
  END IF;
END $$;
SELECT 'CREATE DATABASE srb OWNER srb' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'srb')\gexec
SQL

echo ">> Instalando el driver de Python (psycopg2)..."
pip3 install --user --break-system-packages -r requirements.txt 2>/dev/null || pip3 install --user -r requirements.txt

echo ">> Comprobando la conexión..."
PGPASSWORD=srb psql -h 127.0.0.1 -U srb -d srb -Atc "select 'PostgreSQL listo: ' || version()"
echo "Listo. Siguiente paso: python3 generar_bd.py"
