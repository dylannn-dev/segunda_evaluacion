"""
merkle.py
---------
Raiz de Merkle simplificada para agrupar los eventos de auditoria de una
misma tarea (task_id) en un unico resumen verificable. Util para el
Ejercicio 4 (registro verificable) y como insumo de trazabilidad en el
informe.

Construccion clasica de arbol binario:
- Nivel 0: hash de cada evento individual (hoja).
- Niveles superiores: hash(concat(hijo_izq, hijo_der)).
- Si un nivel tiene numero impar de nodos, el ultimo se duplica.
"""

import hashlib
import json
from typing import List


def _hash_par(a: str, b: str) -> str:
    return hashlib.sha256((a + b).encode("utf-8")).hexdigest()


def hash_evento(evento: dict) -> str:
    serializado = json.dumps(evento, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def construir_raiz_merkle(eventos: List[dict]) -> str:
    """Retorna la raiz de Merkle (hex) para una lista de eventos de una tarea."""
    if not eventos:
        return hashlib.sha256(b"").hexdigest()

    nivel = [hash_evento(e) for e in eventos]

    while len(nivel) > 1:
        if len(nivel) % 2 == 1:
            nivel.append(nivel[-1])  # duplicar el ultimo si es impar
        siguiente_nivel = []
        for i in range(0, len(nivel), 2):
            siguiente_nivel.append(_hash_par(nivel[i], nivel[i + 1]))
        nivel = siguiente_nivel

    return nivel[0]


def raices_por_tarea(eventos: List[dict]) -> dict:
    """Agrupa eventos por task_id y calcula la raiz de Merkle de cada grupo."""
    agrupados = {}
    for e in eventos:
        agrupados.setdefault(e["task_id"], []).append(e)

    return {
        task_id: {
            "n_eventos": len(evs),
            "merkle_root": construir_raiz_merkle(evs),
        }
        for task_id, evs in agrupados.items()
    }
