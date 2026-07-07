"""
pruebas_validacion.py
----------------------
Orquesta el Ejercicio 4 de punta a punta usando datos reales generados por
el Ejercicio 3:

1. Carga outputs/eventos_auditoria.jsonl (eventos reales del Worker).
2. Construye una cadena con bloque genesis + 1 bloque por evento (>= 10).
3. Valida la cadena (debe ser valida).
4. Ejecuta una alteracion controlada sobre un bloque intermedio y vuelve
   a validar, mostrando en que bloque se rompe la consistencia.
5. Calcula raices de Merkle por task_id.
6. Corre un benchmark de PoW con dificultades 0, 00 y 000.
7. Guarda outputs/auditoria_cadena.json y outputs/benchmark_pow.csv
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from blockchain import Blockchain, hash_sha256
from merkle import raices_por_tarea, construir_raiz_merkle

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
EVENTOS_PATH = os.path.join(OUTPUT_DIR, "eventos_auditoria.jsonl")
CADENA_PATH = os.path.join(OUTPUT_DIR, "auditoria_cadena.json")
BENCHMARK_PATH = os.path.join(OUTPUT_DIR, "benchmark_pow.csv")


def cargar_eventos():
    eventos = []
    with open(EVENTOS_PATH, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                eventos.append(json.loads(linea))
    return eventos


def seccion(titulo):
    print("\n" + "=" * 70)
    print(titulo)
    print("=" * 70)


def main():
    eventos = cargar_eventos()
    print(f"Eventos de auditoria cargados: {len(eventos)}")
    assert len(eventos) >= 10, "Se requieren al menos 10 eventos para el Ejercicio 4"

    # --- 1) Construir cadena (dificultad baja para no demorar el batch completo) ---
    seccion("1) Construccion de la cadena (genesis + N bloques de eventos)")
    bc = Blockchain(dificultad_por_defecto=2)
    for evento in eventos:
        r = bc.minar_bloque(evento, dificultad=2)
        print(f"  Bloque #{r['block'].index} minado en {r['intentos']} intentos "
              f"({r['tiempo_segundos']:.4f}s) -> hash={r['block'].hash[:16]}...")

    print(f"Cadena construida con {len(bc.chain)} bloques (incluye genesis).")

    # --- 2) Validacion inicial ---
    seccion("2) Validacion de integridad (antes de alterar)")
    valida, primer_invalido, errores = bc.validar_cadena()
    print(f"Cadena valida: {valida}")
    assert valida, "La cadena recien construida deberia ser valida"

    # --- 3) Alteracion controlada ---
    seccion("3) Alteracion controlada de un bloque intermedio")
    idx_alterar = len(bc.chain) // 2
    data_original = bc.chain[idx_alterar].data
    print(f"Alterando bloque #{idx_alterar}. Data original (evento): "
          f"{json.dumps(data_original, ensure_ascii=False)[:100]}...")
    bc.alterar_bloque(idx_alterar, {"evento": "MANIPULADO", "detalle": "alteracion didactica de prueba"})

    valida2, primer_invalido2, errores2 = bc.validar_cadena()
    print(f"Cadena valida despues de alterar: {valida2}")
    print(f"Primer bloque donde se detecta inconsistencia: #{primer_invalido2}")
    for e in errores2[:6]:
        print(f"  - {e}")
    assert not valida2 and primer_invalido2 == idx_alterar, "La alteracion deberia detectarse en el bloque alterado"

    # revertir la alteracion para dejar la cadena guardada en estado valido + registro de la prueba
    bc.chain[idx_alterar].data = data_original
    bc.chain[idx_alterar].hash = bc.chain[idx_alterar].calcular_hash()
    # Nota: al recalcular el hash del bloque alterado, los bloques siguientes
    # (cuyo previous_hash apunta al hash ORIGINAL, no al de la data corrupta)
    # vuelven a ser consistentes, porque nunca llegamos a re-minar tras la alteracion.
    valida3, _, _ = bc.validar_cadena()
    print(f"Cadena revertida y valida nuevamente: {valida3}")

    bc.guardar(CADENA_PATH)
    print(f"Cadena guardada en {CADENA_PATH}")

    # --- 4) Merkle por tarea ---
    seccion("4) Raices de Merkle por task_id")
    raices = raices_por_tarea(eventos)
    for task_id, info in raices.items():
        print(f"  task_id={task_id}  n_eventos={info['n_eventos']}  merkle_root={info['merkle_root'][:20]}...")

    merkle_path = os.path.join(OUTPUT_DIR, "merkle_por_tarea.json")
    with open(merkle_path, "w", encoding="utf-8") as f:
        json.dump(raices, f, indent=2, ensure_ascii=False)
    print(f"Raices de Merkle guardadas en {merkle_path}")

    # --- 5) Benchmark de Prueba de Trabajo ---
    seccion("5) Benchmark de Prueba de Trabajo (PoW) con distintas dificultades")
    filas = []
    data_prueba = {"tipo": "benchmark", "mensaje": "bloque de prueba para medir PoW"}
    for dificultad in [1, 2, 3]:
        bc_bench = Blockchain(dificultad_por_defecto=dificultad)
        r = bc_bench.minar_bloque(data_prueba, dificultad=dificultad)
        prefijo = "0" * dificultad
        print(f"  Dificultad prefijo='{prefijo}': {r['intentos']} intentos, "
              f"{r['tiempo_segundos']:.4f}s, hash={r['block'].hash[:20]}...")
        filas.append({
            "dificultad_prefijo": prefijo,
            "intentos": r["intentos"],
            "tiempo_segundos": round(r["tiempo_segundos"], 6),
            "hash_obtenido": r["block"].hash,
        })

    with open(BENCHMARK_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["dificultad_prefijo", "intentos", "tiempo_segundos", "hash_obtenido"])
        writer.writeheader()
        writer.writerows(filas)
    print(f"Benchmark guardado en {BENCHMARK_PATH}")

    seccion("Resumen final")
    print(f"- Bloques en la cadena (incl. genesis): {len(bc.chain)}")
    print(f"- Cadena valida al finalizar: {valida3}")
    print(f"- Tareas distintas auditadas (Merkle): {len(raices)}")
    print(f"- Dificultades probadas en PoW: {[f['dificultad_prefijo'] for f in filas]}")


if __name__ == "__main__":
    main()
