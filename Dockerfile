# ======================
# Etapa 1: builder
# ======================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Paquetes para compilar wheels (psycopg, Pillow, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requisitos primero (cache eficiente)
COPY requirements.txt ./requirements.txt

# Construir wheels (importante: pip + setuptools + wheel actualizados)
RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ======================
# Etapa 2: runtime
# ======================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias de runtime + librerías que Chromium/Playwright necesitan
# Lista consolidada para Debian slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl wget gnupg ca-certificates \
    libpq5 \
    # Playwright/Chromium deps
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libxshmfence1 \
    libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 libgtk-3-0 \
    libx11-6 libx11-xcb1 libxext6 libxi6 libxrender1 \
    libcairo2 libatspi2.0-0 libdbus-1-3 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar las wheels construidas en la etapa builder
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

# Crear usuario no root
RUN useradd -ms /bin/bash appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Copiar código de la app (propietario: appuser)
COPY --chown=appuser:appuser . /app

# Playwright: instalar browsers como appuser en su cache
USER appuser
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright
RUN mkdir -p /home/appuser/.cache/ms-playwright && \
    python -m playwright install chromium

# Entrypoint
USER appuser
RUN chmod +x /app/entrypoint.sh
EXPOSE 8000
CMD ["/app/entrypoint.sh"]