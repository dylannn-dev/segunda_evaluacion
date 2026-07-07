# CrediRapido — Segunda Evaluación Integral (INFB6074)

Sistema de scoring de solicitudes de crédito de consumo con orquestación
asíncrona (Redis + Workers), ambiente reproducible (Docker) y registro
verificable de auditoría (blockchain didáctica).

**Modalidad:** 1 estudiante. Ejercicios obligatorios: **2, 3 y 4**
(Ejercicio 1 y 5 no aplican — N/A).

## Estructura del repositorio

```
segunda_evaluacion_integral/
├── README.md
├── informe/
│   └── informe_segunda_evaluacion.pdf
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── .env.example
├── app_async/           # Ejercicio 3
│   ├── app.py            (interfaz Streamlit)
│   ├── worker.py          (Worker)
│   ├── queue_client.py     (comunicación con Redis)
│   └── estado.py           (lógica de scoring)
├── blockchain_audit/    # Ejercicio 4
│   ├── blockchain.py
│   ├── merkle.py
│   └── pruebas_validacion.py
├── data/
│   ├── eventos_entrada.jsonl
│   └── muestra_resultados.csv
├── outputs/
│   ├── estados_tareas.jsonl
│   ├── eventos_auditoria.jsonl
│   ├── auditoria_cadena.json
│   ├── merkle_por_tarea.json
│   ├── benchmark_pow.csv
│   └── evidencias/
└── referencias/
```

## Registro mínimo obligatorio (sección 7 de la pauta)

- **Sistema operativo usado para el desarrollo y pruebas:** Ubuntu 24.04 (contenedor Linux del entorno de trabajo).
- **CPU / RAM aproximada:** entorno contenedorizado estándar (recursos compartidos, no dedicados; ver limitaciones).
- **Versión de Python:** 3.12.3 (pruebas locales) / 3.11.9 (imagen Docker fijada en el `Dockerfile`).
- **Versión de Docker / Compose:** especificadas en `docker-compose.yml` (`version: "3.9"`); imágenes `python:3.11.9-slim` y `redis:7.2-alpine`.
- **Redis:** versión de servidor de pruebas locales `redis-server` (paquete Ubuntu); imagen Docker `redis:7.2-alpine`.
- **Librerías Python relevantes:** `redis==5.0.4`, `streamlit==1.35.0` (ver `docker/requirements.txt`).
- **Estructura de carpetas:** ver arriba.
- **Número de Workers probados:** 2 (`worker1`, `worker2`), ejecutados en paralelo.
- **Número de tareas ejecutadas en la prueba registrada:** 4 solicitudes (1 aprobada, 2 rechazadas, 1 fallida por dato inválido).
- **Eventos de auditoría generados:** 26 (ver `outputs/eventos_auditoria.jsonl`).
- **Bloques en la cadena verificable:** 27 (1 génesis + 26 eventos).

## Cómo ejecutar — Opción A: con Docker (recomendado, forma prevista por la pauta)

> Nota de transparencia: el entorno donde se desarrolló y probó este
> repositorio (sandbox de trabajo) no tenía Docker Engine disponible, por
> lo que el flujo asíncrono se validó de punta a punta con Redis nativo
> (ver Opción B) y los archivos Docker se construyeron siguiendo la
> especificación exacta de la pauta y las buenas prácticas del curso, pero
> no se ejecutó `docker compose up` en ese entorno. **Se recomienda
> ejecutar esta Opción A en tu equipo local para generar tu propia
> evidencia con captura de pantalla**, ya que sí depende de Docker Desktop
> / Docker Engine instalado.

```bash
cd segunda_evaluacion_integral
cp docker/.env.example docker/.env   # ajustar si es necesario

docker compose -f docker/docker-compose.yml --env-file docker/.env up --build
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs worker1
docker compose -f docker/docker-compose.yml logs worker2

# Interfaz disponible en http://localhost:8501

docker compose -f docker/docker-compose.yml down
```

Prueba de verificación (Redis responde, Worker activo, se puede encolar):
```bash
docker compose -f docker/docker-compose.yml exec redis redis-cli ping
docker compose -f docker/docker-compose.yml exec worker1 python3 -c "from app_async.queue_client import largo_cola; print(largo_cola())"
```

## Cómo ejecutar — Opción B: local sin Docker (la que generó las evidencias de este repositorio)

Requiere Redis instalado localmente (`sudo apt-get install redis-server` en Ubuntu/Debian).

```bash
cd segunda_evaluacion_integral

# 1. Levantar Redis
redis-server --daemonize yes --port 6379
redis-cli ping   # debe responder PONG

# 2. Instalar dependencias
pip install -r docker/requirements.txt --break-system-packages

# 3. Preparar carpeta de outputs
export OUTPUT_DIR=$(pwd)/outputs
mkdir -p $OUTPUT_DIR

# 4. Levantar 2 Workers (en dos terminales, o en background)
cd app_async
python3 worker.py &   # worker 1
python3 worker.py &   # worker 2

# 5a. Interfaz Streamlit
streamlit run app.py

# 5b. O bien, encolar solicitudes de prueba directamente (sin UI)
python3 - <<'EOF'
import json
from queue_client import encolar_solicitud
with open("../data/eventos_entrada.jsonl") as f:
    for line in f:
        payload = json.loads(line)
        print(encolar_solicitud(payload))
EOF

# 6. Ejercicio 4: construir y validar la cadena a partir de los eventos reales
cd ../blockchain_audit
python3 pruebas_validacion.py
```

## Verificación rápida

```bash
redis-cli ping                                  # PONG
tail -n 5 outputs/estados_tareas.jsonl           # últimos estados publicados
wc -l outputs/eventos_auditoria.jsonl            # >= 10 eventos
cat outputs/benchmark_pow.csv                    # tiempos de PoW por dificultad
python3 -c "import json; print(len(json.load(open('outputs/auditoria_cadena.json'))))"  # nº de bloques
```

## Comandos de limpieza

```bash
# Docker
docker compose -f docker/docker-compose.yml down -v

# Local
redis-cli shutdown nosave
pkill -f worker.py
```

## Declaración de uso de herramientas de apoyo

Se utilizó Claude (Anthropic) como asistente en depuracion y dudad sobre
el proyecto y documentación. Todo el código fue
ejecutado y validado en un entorno real con Redis (evidencias en
`outputs/` y `outputs/evidencias/`), 
