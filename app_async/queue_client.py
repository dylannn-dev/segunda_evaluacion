"""
queue_client.py
----------------
Modulo de comunicacion con Redis para el sistema de scoring de solicitudes
de credito de consumo (CrediRapido).

Responsabilidades:
- Encolar solicitudes (tareas) en una lista Redis (broker FIFO).
- Publicar y leer el estado parcial/resultado de cada tarea (clave por task_id).
- Registrar eventos de auditoria en un archivo JSONL append-only, que luego
  alimenta la cadena de bloques del Ejercicio 4.

Decision de diseno: se usa una LISTA de Redis (RPUSH/BLPOP) como cola en vez
de un STREAM porque el escenario no requiere consumo por multiples grupos
de consumidores ni replay de mensajes; BLPOP entrega reparto de trabajo
(round-robin implicito) entre N workers de forma simple y bloqueante,
suficiente para el alcance didactico de esta evaluacion.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone

import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

QUEUE_KEY = "credirapido:cola:solicitudes"
STATE_KEY_PREFIX = "credirapido:estado:"
STATE_TTL_SECONDS = 3600  # las claves de estado expiran para no crecer indefinidamente

# Rutas de archivos de evidencia / auditoria (montadas como volumen en Docker)
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/app/outputs")
ESTADOS_LOG_PATH = os.path.join(OUTPUT_DIR, "estados_tareas.jsonl")


def get_redis_client():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def encolar_solicitud(payload: dict) -> str:
    """Crea un task_id, guarda el estado inicial 'recibido' y encola la tarea."""
    r = get_redis_client()
    task_id = str(uuid.uuid4())[:8]

    estado_inicial = {
        "task_id": task_id,
        "estado": "recibido",
        "timestamp": _now_iso(),
        "parametros": payload,
        "avance_pct": 0,
        "mensaje": "Solicitud recibida y validada en formato. En espera de un Worker.",
        "resultado": None,
    }
    r.set(f"{STATE_KEY_PREFIX}{task_id}", json.dumps(estado_inicial), ex=STATE_TTL_SECONDS)

    mensaje_cola = {"task_id": task_id, "payload": payload}
    r.rpush(QUEUE_KEY, json.dumps(mensaje_cola))

    registrar_evento_auditoria(
        task_id=task_id,
        evento="tarea_creada",
        detalle={"estado": "recibido", "origen": "interfaz"},
    )
    return task_id


def publicar_estado(task_id: str, estado: str, avance_pct: int, mensaje: str, resultado=None):
    """Sobrescribe el estado actual de una tarea (usado por el Worker en cada paso)."""
    r = get_redis_client()
    data = {
        "task_id": task_id,
        "estado": estado,
        "timestamp": _now_iso(),
        "avance_pct": avance_pct,
        "mensaje": mensaje,
        "resultado": resultado,
    }
    prev_raw = r.get(f"{STATE_KEY_PREFIX}{task_id}")
    if prev_raw:
        prev = json.loads(prev_raw)
        data["parametros"] = prev.get("parametros")
    r.set(f"{STATE_KEY_PREFIX}{task_id}", json.dumps(data), ex=STATE_TTL_SECONDS)

    # Registro persistente para trazabilidad y para el Ejercicio 4 (blockchain)
    with open(ESTADOS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

    return data


def leer_estado(task_id: str):
    r = get_redis_client()
    raw = r.get(f"{STATE_KEY_PREFIX}{task_id}")
    return json.loads(raw) if raw else None


def registrar_evento_auditoria(task_id: str, evento: str, detalle: dict, worker_id: str = "interfaz"):
    """
    Evento de auditoria independiente del 'estado' de negocio: sirve para
    reconstruir la linea de tiempo completa (creacion, inicio, avances,
    error, finalizacion, verificacion) que luego se agrupa en un arbol de
    Merkle por task_id (ver blockchain_audit/merkle.py).
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    registro = {
        "task_id": task_id,
        "evento": evento,
        "worker_id": worker_id,
        "timestamp": _now_iso(),
        "detalle": detalle,
    }
    eventos_path = os.path.join(OUTPUT_DIR, "eventos_auditoria.jsonl")
    with open(eventos_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro


def obtener_siguiente_tarea(timeout: int = 5):
    """BLPOP bloqueante: el Worker espera hasta 'timeout' segundos por una tarea nueva."""
    r = get_redis_client()
    item = r.blpop(QUEUE_KEY, timeout=timeout)
    if item is None:
        return None
    _, raw = item
    return json.loads(raw)


def largo_cola():
    r = get_redis_client()
    return r.llen(QUEUE_KEY)
