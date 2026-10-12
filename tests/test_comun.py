"""Pruebas del formato de mensajes compartido (comun.py)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comun  # noqa: E402


def test_solicitud_tiene_todos_los_campos():
    s = comun.crear_solicitud("C1-0001", "C1", comun.CONSULTA, mes=11)
    assert set(s) == {"id_solicitud", "id_cliente", "tipo", "mes", "id_evento",
                      "num_ocurrencia", "id_reserva", "asientos"}
    assert s["mes"] == 11 and s["id_evento"] is None


def test_respuesta_formato():
    r = comun.crear_respuesta("C1-0001", comun.EXITO, {"libres": 98})
    assert r == {"id_solicitud": "C1-0001", "estado": "EXITO", "datos": {"libres": 98}}
    assert comun.crear_respuesta("C1-0002", comun.ERROR)["datos"] == {}
