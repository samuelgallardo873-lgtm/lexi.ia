"""Importación de expedientes y barrido de actuaciones nuevas del SAE."""

from dataclasses import dataclass

import database
from sae_connector import ConectorSAE, ErrorPortalSAE

ACTUACIONES_RECIENTES_LIMITE = 5


@dataclass(frozen=True)
class ResultadoBarrido:
    expedientes_listados: int
    expedientes_revisados: int
    actuaciones_nuevas: int


def sincronizar_expedientes(cuit, password):
    """Actualiza por consulta SAE los expedientes locales en monitoreo activo."""
    expedientes = database.listar_expedientes(
        solo_monitoreados=True, solo_sae=False)
    with ConectorSAE(cuit, password, headless=False) as sae:
        sae.iniciar_sesion()
        for expediente in expedientes:
            _sincronizar_un_expediente(sae, expediente)
    return len(expedientes)


def sincronizar_expediente(cuit, password, numero_expediente):
    """Actualiza un solo expediente local y guarda sus actuaciones nuevas."""
    expediente = database.obtener_expediente(numero_expediente)
    with ConectorSAE(cuit, password, headless=False) as sae:
        sae.iniciar_sesion()
        return _sincronizar_un_expediente(sae, expediente)


def sincronizar_actuacion(cuit, password, numero_expediente, fecha, titulo):
    """Descarga y guarda únicamente el texto modal de un movimiento solicitado."""
    expediente = database.obtener_expediente(numero_expediente)
    with ConectorSAE(cuit, password, headless=False) as sae:
        sae.iniciar_sesion()
        actuacion = _leer_actuacion(sae, expediente, fecha, titulo)
    actuacion["expediente"] = expediente["expediente"]
    database.guardar_novedad(actuacion)
    return actuacion


def ejecutar_barrido_diario(cuit, password):
    """Lee causas monitoreadas usando la consulta SAE o su URL de detalle."""
    database.inicializar()
    expedientes_monitoreados = database.listar_expedientes(
        solo_monitoreados=True, solo_sae=False)
    with ConectorSAE(
            cuit, password, headless=False) as sae:
        sae.iniciar_sesion()
        nuevas = 0
        revisados = 0
        for expediente in expedientes_monitoreados:
            nuevas += _sincronizar_un_expediente(sae, expediente)
            revisados += 1

    return ResultadoBarrido(
        expedientes_listados=len(expedientes_monitoreados),
        expedientes_revisados=revisados,
        actuaciones_nuevas=nuevas,
    )


def _sincronizar_un_expediente(sae, expediente):
    actuaciones = _leer_actuaciones(sae, expediente)
    database.guardar_expediente(expediente, desde_sae=True)
    return _guardar_actuaciones(expediente, actuaciones)


def _leer_actuaciones(sae, expediente):
    centro = str(expediente.get("centro_judicial") or "").strip()
    fuero = str(expediente.get("fuero") or "").strip()
    numero = str(
        expediente.get("numero_expediente") or expediente.get("expediente") or ""
    ).strip()
    faltantes = [
        nombre for nombre, valor in (
            ("centro judicial", centro),
            ("fuero", fuero),
            ("número de expediente", numero),
        ) if not valor
    ]
    if faltantes:
        raise ErrorPortalSAE(
            f"El expediente {numero or expediente.get('expediente', '')} "
            f"no tiene {', '.join(faltantes)} guardado. Completá esos datos "
            "antes de sincronizar."
        )
    return sae.leer_actuaciones_por_consulta(
        centro, fuero, numero, limite=ACTUACIONES_RECIENTES_LIMITE)


def _leer_actuacion(sae, expediente, fecha, titulo):
    centro = str(expediente.get("centro_judicial") or "").strip()
    fuero = str(expediente.get("fuero") or "").strip()
    numero = str(
        expediente.get("numero_expediente") or expediente.get("expediente") or ""
    ).strip()
    faltantes = [
        nombre for nombre, valor in (
            ("centro judicial", centro),
            ("fuero", fuero),
            ("número de expediente", numero),
            ("fecha", str(fecha).strip()),
            ("descripción", str(titulo).strip()),
        ) if not valor
    ]
    if faltantes:
        raise ErrorPortalSAE(
            f"El expediente {numero or expediente.get('expediente', '')} "
            f"no tiene {', '.join(faltantes)} para consultar la actuación."
        )
    return sae.leer_actuacion_por_consulta(
        centro, fuero, numero, fecha, titulo)


def _guardar_actuaciones(expediente, actuaciones):
    nuevas = 0
    for actuacion in actuaciones:
        actuacion["expediente"] = expediente["expediente"]
        nuevas += database.guardar_novedad(actuacion)
    return nuevas
