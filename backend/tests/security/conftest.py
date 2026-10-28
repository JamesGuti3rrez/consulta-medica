"""Hooks de las pruebas de seguridad: guardan la evidencia de cada caso de TA-011 con su resultado real."""

import os

import pytest

from tests.security.ta011_evidencia import SECRETS, Caso


def pytest_configure(config):
    config.addinivalue_line("markers", "ta011(id, criterio, titulo, nombre, esperado): caso de TA-011")
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
    marker = request.node.get_closest_marker("ta011")
    return Caso(**marker.kwargs)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if item.get_closest_marker("ta011") is None:
        return
    caso_obj = item.funcargs.get("caso") if hasattr(item, "funcargs") else None
    # El resultado del JSON es el de pytest: PASA solo si la prueba terminó sin fallar.
    if report.when == "call":
        if caso_obj is not None:
            error = "" if report.passed else SECRETS.scrub(str(report.longrepr))[-3000:]
            caso_obj.escribir("PASA" if report.passed else "FALLA", error)
    elif report.when == "setup" and report.failed:
        marker = item.get_closest_marker("ta011")
        Caso(**marker.kwargs).escribir("FALLA", "Falló la preparación: " + SECRETS.scrub(str(report.longrepr))[-3000:])
