"""
estado.py
---------
Logica de negocio del escenario aplicado: scoring de solicitudes de credito
de consumo para una fintech ficticia ("CrediRapido").

Esta logica es la "tarea costosa" que el Worker ejecuta fuera de la interfaz.
Se divide en pasos para poder publicar avances parciales (Ejercicio 3).
"""

class SolicitudInvalida(Exception):
    pass


CAMPOS_REQUERIDOS = [
    "nombre_solicitante", "monto_solicitado", "ingreso_mensual",
    "deuda_mensual_actual", "antiguedad_laboral_meses", "edad",
    "historial_crediticio", "region",
]

HISTORIAL_PUNTAJE = {"bueno": 100, "regular": 60, "malo": 20}


def validar_formato(payload: dict):
    """Paso 1. Valida presencia y tipos minimos. Lanza SolicitudInvalida si falla."""
    faltantes = [c for c in CAMPOS_REQUERIDOS if c not in payload]
    if faltantes:
        raise SolicitudInvalida(f"Campos faltantes: {faltantes}")

    numericos = ["monto_solicitado", "ingreso_mensual", "deuda_mensual_actual",
                 "antiguedad_laboral_meses", "edad"]
    for campo in numericos:
        try:
            float(payload[campo])
        except (TypeError, ValueError):
            raise SolicitudInvalida(f"Campo '{campo}' debe ser numerico")

    if payload["historial_crediticio"] not in HISTORIAL_PUNTAJE:
        raise SolicitudInvalida("historial_crediticio debe ser 'bueno', 'regular' o 'malo'")

    return True


def verificar_reglas_duras(payload: dict):
    """Paso 2. Reglas de rechazo automatico (anti-fraude / elegibilidad basica)."""
    edad = float(payload["edad"])
    ingreso = float(payload["ingreso_mensual"])
    monto = float(payload["monto_solicitado"])

    motivos = []
    if edad < 18 or edad > 75:
        motivos.append("edad fuera de rango permitido (18-75)")
    if ingreso <= 0:
        motivos.append("ingreso mensual invalido")
    if monto > ingreso * 20:
        motivos.append("monto solicitado excede 20x el ingreso mensual")

    return {"aprueba_reglas_duras": len(motivos) == 0, "motivos": motivos}


def calcular_score_financiero(payload: dict):
    """Paso 3. Score parcial por relacion deuda/ingreso y monto/ingreso (peso 50)."""
    ingreso = float(payload["ingreso_mensual"])
    deuda = float(payload["deuda_mensual_actual"])
    monto = float(payload["monto_solicitado"])

    ratio_deuda_ingreso = deuda / ingreso if ingreso > 0 else 1.0
    score_deuda = max(0.0, 100 - ratio_deuda_ingreso * 150)  # a mayor ratio, menor score

    ratio_monto_ingreso = monto / ingreso if ingreso > 0 else 20.0
    score_monto = max(0.0, 100 - ratio_monto_ingreso * 5)

    return {
        "score_deuda": round(score_deuda, 2),
        "score_monto": round(score_monto, 2),
        "ratio_deuda_ingreso": round(ratio_deuda_ingreso, 3),
    }


def calcular_score_historial(payload: dict):
    """Paso 4. Score parcial por antiguedad laboral e historial crediticio (peso 50)."""
    antiguedad = float(payload["antiguedad_laboral_meses"])
    score_antiguedad = min(100.0, antiguedad / 60 * 100)  # 60 meses = tope
    score_historial = HISTORIAL_PUNTAJE[payload["historial_crediticio"]]

    return {
        "score_antiguedad": round(score_antiguedad, 2),
        "score_historial": round(score_historial, 2),
    }


def consultar_buro_externo_simulado(payload: dict, seed: int):
    """
    Paso 5. Simula una consulta a un 'buro de credito' externo (latencia de red).
    Determinista via seed para que los resultados sean reproducibles en pruebas.
    """
    import random
    rnd = random.Random(seed)
    ajuste = rnd.uniform(-5, 5)
    return {"ajuste_buro_externo": round(ajuste, 2)}


def calcular_decision_final(parciales: dict):
    """Paso 6. Combina los sub-scores ponderados y determina la decision."""
    score_base = (
        parciales["score_deuda"] * 0.30
        + parciales["score_monto"] * 0.20
        + parciales["score_antiguedad"] * 0.20
        + parciales["score_historial"] * 0.30
    )
    score_final = max(0.0, min(100.0, score_base + parciales.get("ajuste_buro_externo", 0)))

    if score_final >= 70:
        decision = "aprobado"
    elif score_final >= 50:
        decision = "revision_manual"
    else:
        decision = "rechazado"

    return {"score_final": round(score_final, 2), "decision": decision}
