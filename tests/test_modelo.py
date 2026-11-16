import copy

import pytest

from grafo import cargar, validar


def test_red_del_paper_es_valida(datos):
    assert validar(datos) == []


def test_detecta_camara_inexistente(datos):
    d = copy.deepcopy(datos)
    d["aristas"].append({"de": "AV-01", "a": "XX-99", "km": 1, "min": 1})
    assert any("XX-99" in e for e in validar(d))


def test_detecta_peso_no_positivo(datos):
    d = copy.deepcopy(datos)
    d["aristas"][0]["km"] = 0
    assert any("positivos" in e for e in validar(d))


def test_detecta_heuristica_no_admisible(datos):
    # Si la recta entre cámaras supera al tramo, A* con heurística podría fallar.
    d = copy.deepcopy(datos)
    d["aristas"][0]["km"] = 1.0  # AV-01 -> AV-08 está a 2.9 km en línea recta
    assert any("línea recta" in e for e in validar(d))


def test_cargar_rechaza_red_invalida(tmp_path, datos):
    d = copy.deepcopy(datos)
    d["aristas"][0]["min"] = -1
    p = tmp_path / "red.json"
    p.write_text(__import__("json").dumps(d), encoding="utf-8")
    with pytest.raises(ValueError):
        cargar(p)
