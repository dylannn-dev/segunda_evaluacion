"""
blockchain.py
-------------
Registro verificable didactico (Ejercicio 4) para los eventos de auditoria
generados por el motor de scoring de CrediRapido (Ejercicio 3).

Propiedades implementadas:
- Hash determinista (SHA-256) sobre una serializacion estable (JSON con
  sort_keys=True) de cada bloque.
- Bloques enlazados: cada bloque referencia el hash del bloque anterior.
- Validacion de integridad de toda la cadena.
- Alteracion controlada + deteccion del punto exacto donde se rompe la
  consistencia (efecto domino).
- Prueba de trabajo (PoW) didactica: busqueda de un nonce tal que el hash
  del bloque comience con N ceros ('0', '00', '000').

Este modulo NO pretende ser una blockchain productiva: no hay red P2P,
no hay consenso distribuido, no hay incentivos economicos ni resistencia
a un atacante con mas poder de computo que el propio proceso. Es una
cadena de hashes local que sirve como evidencia de integridad de un log
de auditoria, firmada por quien la genera (ver informe, seccion h).
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional


def hash_sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def serializar_estable(obj: dict) -> str:
    """Serializacion estable y determinista: mismas claves -> mismo string."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


@dataclass
class Block:
    index: int
    timestamp: str
    data: dict
    previous_hash: str
    nonce: int = 0
    hash: str = field(default="", repr=False)

    def calcular_hash(self) -> str:
        contenido = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        return hash_sha256(serializar_estable(contenido))

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class Blockchain:
    def __init__(self, dificultad_por_defecto: int = 2):
        self.chain: List[Block] = []
        self.dificultad_por_defecto = dificultad_por_defecto
        self._crear_bloque_genesis()

    def _crear_bloque_genesis(self):
        genesis = Block(
            index=0,
            timestamp="2026-01-01T00:00:00+00:00",
            data={"tipo": "genesis", "mensaje": "Bloque genesis - CrediRapido audit chain"},
            previous_hash="0" * 64,
            nonce=0,
        )
        genesis.hash = genesis.calcular_hash()
        self.chain.append(genesis)

    def ultimo_bloque(self) -> Block:
        return self.chain[-1]

    def minar_bloque(self, data: dict, dificultad: Optional[int] = None) -> dict:
        """
        Prueba de trabajo didactica: incrementa nonce hasta que el hash
        resultante comience con 'dificultad' ceros. Retorna metricas
        (intentos, tiempo) ademas de agregar el bloque a la cadena.
        """
        dificultad = self.dificultad_por_defecto if dificultad is None else dificultad
        prefijo = "0" * dificultad
        prev = self.ultimo_bloque()

        nuevo = Block(
            index=prev.index + 1,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            data=data,
            previous_hash=prev.hash,
            nonce=0,
        )

        intentos = 0
        t0 = time.time()
        while True:
            intentos += 1
            nuevo.hash = nuevo.calcular_hash()
            if nuevo.hash.startswith(prefijo):
                break
            nuevo.nonce += 1
        tiempo = time.time() - t0

        self.chain.append(nuevo)
        return {"block": nuevo, "intentos": intentos, "tiempo_segundos": tiempo, "dificultad": dificultad}

    def validar_cadena(self):
        """
        Recorre toda la cadena verificando:
        1) que el hash almacenado corresponda al recalculo (detecta
           alteracion de data, nonce o timestamp);
        2) que previous_hash del bloque i coincida con hash del bloque i-1
           (detecta ruptura del enlace / efecto domino).
        Retorna (es_valida, primer_indice_invalido_o_None, detalle_errores).
        """
        errores = []
        for i, bloque in enumerate(self.chain):
            hash_recalculado = bloque.calcular_hash()
            if hash_recalculado != bloque.hash:
                errores.append({
                    "index": i,
                    "problema": "hash_no_coincide",
                    "hash_almacenado": bloque.hash,
                    "hash_recalculado": hash_recalculado,
                })
            if i > 0:
                anterior = self.chain[i - 1]
                if bloque.previous_hash != anterior.hash:
                    errores.append({
                        "index": i,
                        "problema": "previous_hash_no_enlaza",
                        "previous_hash_declarado": bloque.previous_hash,
                        "hash_bloque_anterior": anterior.hash,
                    })
        primer_invalido = errores[0]["index"] if errores else None
        return (len(errores) == 0, primer_invalido, errores)

    def alterar_bloque(self, index: int, nueva_data: dict):
        """
        Alteracion controlada con fines didacticos: modifica los datos de
        un bloque SIN recalcular su hash (simulando un atacante que edita
        el registro directamente). El hash queda "viejo" y por eso
        validar_cadena() debe detectar la inconsistencia en ese bloque,
        y ademas todos los bloques siguientes quedan con previous_hash
        desincronizado (efecto domino).
        """
        self.chain[index].data = nueva_data

    def to_json(self) -> str:
        return json.dumps([b.to_dict() for b in self.chain], indent=2, ensure_ascii=False)

    def guardar(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def desde_eventos(cls, eventos: List[dict], dificultad: int = 2) -> "Blockchain":
        """Construye la cadena minando un bloque por cada evento de auditoria."""
        bc = cls(dificultad_por_defecto=dificultad)
        for evento in eventos:
            bc.minar_bloque(data=evento, dificultad=dificultad)
        return bc
