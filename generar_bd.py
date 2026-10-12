"""
Crea events.json con los datos iniciales · VM3

50 eventos en noviembre de 2026: E1 a E20 con dos ocurrencias y E21 a E50
con una, todas con 100 asientos libres (70 ocurrencias, 7.000 asientos).
Si events.json ya existe, se reemplaza (sirve para reiniciar la BD).

Uso: python3 generar_bd.py
"""

import json
from dataclasses import asdict
from datetime import date

import config
from modelos import Evento, Ocurrencia


def main():
    eventos = {}
    for i in range(1, config.NUM_EVENTOS + 1):
        if i <= config.EVENTOS_CON_DOS_OCURRENCIAS:
            ocurrencias = [Ocurrencia(1, date(config.ANIO, config.MES, i)),
                           Ocurrencia(2, date(config.ANIO, config.MES, i + 10))]
        else:
            ocurrencias = [Ocurrencia(1, date(config.ANIO, config.MES, i - 20))]
        eventos[f"E{i}"] = Evento(f"E{i}", len(ocurrencias), ocurrencias)

    bd = {
        "eventos": {id_evento: asdict(e) for id_evento, e in eventos.items()},
        "reservas": {},
        "solicitudes_procesadas": {},
    }
    with open(config.RUTA_BD, "w", encoding="utf-8") as f:
        json.dump(bd, f, ensure_ascii=False, indent=2, default=str)

    total = sum(e.num_ocurrencias for e in eventos.values())
    print(f"Base de datos creada en {config.RUTA_BD}")
    print(f"{len(eventos)} eventos · {total} ocurrencias · "
          f"{total * config.ASIENTOS_POR_OCURRENCIA} asientos libres")


if __name__ == "__main__":
    main()