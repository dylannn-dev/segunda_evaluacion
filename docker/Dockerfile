# Version fija de Python (reproducibilidad)
FROM python:3.11.9-slim

WORKDIR /app

# Dependencias del sistema minimas (ninguna extra requerida por redis-py/streamlit)
COPY docker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Codigo de la aplicacion (interfaz, worker, modulos de estado y blockchain)
COPY app_async/ /app/app_async/
COPY blockchain_audit/ /app/blockchain_audit/
COPY data/ /app/data/

ENV PYTHONUNBUFFERED=1 \
    OUTPUT_DIR=/app/outputs

RUN mkdir -p /app/outputs

# El comando real se sobreescribe por servicio en docker-compose.yml
CMD ["python3", "app_async/worker.py"]
