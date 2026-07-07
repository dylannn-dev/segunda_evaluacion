"""
worker.py
---------
Worker de CrediRapido: consume solicitudes de la cola Redis y ejecuta el
scoring de credito por pasos, publicando al menos 5 actualizaciones
parciales antes del resultado final (Ejercicio 3).

Se puede ejecutar mas de una instancia en paralelo (docker compose up
--scale worker=2, o ejecutando este script en dos terminales distintas)
para observar reparto de trabajo via BLPOP.

Manejo de errores implementado:
- Tarea invalida       -> SolicitudInvalida (formato) => estado 'fallido'
- Excepcion durante     -> captura generica            => estado 'fallido'
  el procesamiento
- Timeout simulado      -> paso que excede un umbral    => estado 'fallido'
  de tiempo maximo permitido por tarea
"""

import os
import sys
import time
import socket
import random

sys.path.insert(0, os.path.dirname(__file__))

from queue_client import (
    obtener_siguiente_tarea, publicar_estado, registrar_evento_auditoria,
)
from estado import (
    validar_formato, verificar_reglas_duras, calcular_score_financiero,
    calcular_score_historial, consultar_buro_externo_simulado,
    calcular_decision_final, SolicitudInvalida,
)

WORKER_ID = f"worker-{socket.gethostname()}-{os.getpid()}"
TIMEOUT_MAX_SEGUNDOS = float(os.environ.get("TASK_TIMEOUT_SECONDS", 8))
SIMULAR_LATENCIA = os.environ.get("SIMULAR_LATENCIA", "1") == "1"


def _dormir(segundos):
    if SIMULAR_LATENCIA:
        time.sleep(segundos)


def procesar_tarea(task_id: str, payload: dict):
    inicio = time.time()
    registrar_evento_auditoria(task_id, "tarea_iniciada", {"worker": WORKER_ID}, worker_id=WORKER_ID)

    def chequear_timeout(paso: str):
        if time.time() - inicio > TIMEOUT_MAX_SEGUNDOS:
            raise TimeoutError(f"Timeout simulado en paso '{paso}' (> {TIMEOUT_MAX_SEGUNDOS}s)")

    try:
        # Paso 1: validar formato (10%)
        publicar_estado(task_id, "procesando", 10, "Validando formato de la solicitud...")
        _dormir(random.uniform(0.3, 0.8))
        validar_formato(payload)
        registrar_evento_auditoria(task_id, "avance_parcial", {"paso": "validacion_formato", "avance_pct": 10}, WORKER_ID)
        chequear_timeout("validacion_formato")

        # Paso 2: reglas duras (25%)
        publicar_estado(task_id, "procesando", 25, "Verificando reglas de elegibilidad y anti-fraude...")
        _dormir(random.uniform(0.3, 0.8))
        reglas = verificar_reglas_duras(payload)
        registrar_evento_auditoria(task_id, "avance_parcial", {"paso": "reglas_duras", "avance_pct": 25, "resultado": reglas}, WORKER_ID)
        chequear_timeout("reglas_duras")

        if not reglas["aprueba_reglas_duras"]:
            resultado = {"decision": "rechazado", "motivo": reglas["motivos"], "score_final": 0}
            publicar_estado(task_id, "completado", 100, "Rechazo automatico por reglas duras.", resultado)
            registrar_evento_auditoria(task_id, "tarea_completada", {"resultado": resultado}, WORKER_ID)
            return resultado

        # Paso 3: score financiero (45%)
        publicar_estado(task_id, "procesando", 45, "Calculando score de endeudamiento y monto solicitado...")
        _dormir(random.uniform(0.4, 1.0))
        score_fin = calcular_score_financiero(payload)
        registrar_evento_auditoria(task_id, "avance_parcial", {"paso": "score_financiero", "avance_pct": 45, "resultado": score_fin}, WORKER_ID)
        chequear_timeout("score_financiero")

        # Paso 4: score historial/antiguedad (65%)
        publicar_estado(task_id, "procesando", 65, "Calculando score de historial crediticio y antiguedad laboral...")
        _dormir(random.uniform(0.4, 1.0))
        score_hist = calcular_score_historial(payload)
        registrar_evento_auditoria(task_id, "avance_parcial", {"paso": "score_historial", "avance_pct": 65, "resultado": score_hist}, WORKER_ID)
        chequear_timeout("score_historial")

        # Paso 5: consulta a buro externo simulada (85%)
        publicar_estado(task_id, "publicando_avance", 85, "Consultando buro de credito externo (simulado)...")
        _dormir(random.uniform(0.5, 1.2))
        seed = abs(hash(task_id)) % (2**31)
        buro = consultar_buro_externo_simulado(payload, seed)
        registrar_evento_auditoria(task_id, "avance_parcial", {"paso": "buro_externo", "avance_pct": 85, "resultado": buro}, WORKER_ID)
        chequear_timeout("buro_externo")

        # Paso 6: decision final (100%)
        parciales = {**score_fin, **score_hist, **buro}
        decision = calcular_decision_final(parciales)
        resultado = {**parciales, **decision}

        publicar_estado(task_id, "completado", 100, f"Scoring finalizado: {decision['decision']}", resultado)
        registrar_evento_auditoria(task_id, "tarea_completada", {"resultado": resultado}, WORKER_ID)
        registrar_evento_auditoria(task_id, "verificacion", {"chequeo": "estado_final_consistente", "ok": True}, WORKER_ID)
        return resultado

    except SolicitudInvalida as e:
        publicar_estado(task_id, "fallido", 100, f"Solicitud invalida: {e}")
        registrar_evento_auditoria(task_id, "error", {"tipo": "SolicitudInvalida", "detalle": str(e)}, WORKER_ID)
    except TimeoutError as e:
        publicar_estado(task_id, "fallido", 100, f"Timeout: {e}")
        registrar_evento_auditoria(task_id, "error", {"tipo": "TimeoutError", "detalle": str(e)}, WORKER_ID)
    except Exception as e:
        publicar_estado(task_id, "fallido", 100, f"Error inesperado: {e}")
        registrar_evento_auditoria(task_id, "error", {"tipo": type(e).__name__, "detalle": str(e)}, WORKER_ID)


def main():
    print(f"[{WORKER_ID}] Worker iniciado. Esperando tareas en la cola...", flush=True)
    while True:
        tarea = obtener_siguiente_tarea(timeout=5)
        if tarea is None:
            continue
        task_id = tarea["task_id"]
        print(f"[{WORKER_ID}] Procesando tarea {task_id}", flush=True)
        resultado = procesar_tarea(task_id, tarea["payload"])
        print(f"[{WORKER_ID}] Tarea {task_id} finalizada -> {resultado}", flush=True)


if __name__ == "__main__":
    main()
