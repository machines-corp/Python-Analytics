# Dockerfile
# Etapa 1: build (instala deps y compila ruedas)
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Paquetes del sistema para compilar dependencias (psycopg, Pillow, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requisitos primero (para cache eficiente)
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Etapa 2: runtime (ligera)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Paquetes mínimos de runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiamos ruedas y las instalamos
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

# Creamos usuario no root
RUN useradd -ms /bin/bash appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"
USER appuser

# Copiamos código
COPY --chown=appuser:appuser . /app

# Entrypoint (migraciones, collectstatic, etc.)
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
CMD ["/app/entrypoint.sh"]
