"""Hooks de las pruebas de seguridad: guardan la evidencia de cada caso de TA-011, HU-006 y HU-007 con su resultado real."""

import os

import pytest

from tests.security.ta011_evidencia import SECRETS, Caso

# Marcador de cada suite y la variable con su carpeta de evidencia.
SUITES = {"ta011": "TA011_EVIDENCIA", "hu006": "HU006_EVIDENCIA", "hu007": "HU007_EVIDENCIA"}


def _marcador(node):
    for name in SUITES:
        marker = node.get_closest_marker(name)
        if marker is not None:
            return marker, SUITES[name]
    return None, None


def pytest_configure(config):
    config.addinivalue_line("markers", "ta011(id, criterio, titulo, nombre, esperado): caso de TA-011")
    config.addinivalue_line("markers", "hu006(id, criterio, titulo, nombre, esperado): caso de HU-006 (diagnóstico final)")
    config.addinivalue_line("markers", "hu007(id, criterio, titulo, nombre, esperado): caso de HU-007 (reporte final)")
    config.addinivalue_line("markers", "vivo: necesita servidor y Supabase reales (TA011_MODO=vivo)")
    config.addinivalue_line("markers", "logs_servidor: lee el log del servidor (en vivo, TA011_SERVER_LOG)")


def pytest_collection_modifyitems(config, items):
    # Los casos «vivo» necesitan el servidor y el Supabase reales: fuera de TA011_MODO=vivo se deseleccionan
    # (pytest los cuenta como «deselected» en el resumen) en lugar de fallar por falta de red.
    if os.getenv("TA011_MODO", "local") == "vivo":
        return
    selected = [item for item in items if item.get_closest_marker("vivo") is None]
    deselected = [item for item in items if item.get_closest_marker("vivo") is not None]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


@pytest.fixture
def caso(request) -> Caso:
    marker, carpeta_env = _marcador(request.node)
    return Caso(**marker.kwargs, carpeta_env=carpeta_env)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    marker, carpeta_env = _marcador(item)
    if marker is None:
        return
    caso_obj = item.funcargs.get("caso") if hasattr(item, "funcargs") else None
    # El resultado del JSON es el de pytest: PASA solo si la prueba terminó sin fallar.
    if report.when == "call":
        if caso_obj is not None:
            error = "" if report.passed else SECRETS.scrub(str(report.longrepr))[-3000:]
            caso_obj.escribir("PASA" if report.passed else "FALLA", error)
    elif report.when == "setup" and report.failed:
        Caso(**marker.kwargs, carpeta_env=carpeta_env).escribir("FALLA", "Falló la preparación: " + SECRETS.scrub(str(report.longrepr))[-3000:])
