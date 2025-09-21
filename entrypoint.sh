#!/usr/bin/env bash
set -e

# Espera a Postgres si corresponde
if [ -n "$POSTGRES_HOST" ]; then
  echo "Esperando a Postgres en $POSTGRES_HOST:$POSTGRES_PORT..."
  until /usr/bin/env python - <<'PYCODE'
import os, sys, psycopg
host=os.getenv("POSTGRES_HOST","localhost")
port=int(os.getenv("POSTGRES_PORT","5432"))
user=os.getenv("POSTGRES_USER","postgres")
pwd=os.getenv("POSTGRES_PASSWORD","postgres")
db=os.getenv("POSTGRES_DB","postgres")
try:
    with psycopg.connect(host=host, port=port, user=user, password=pwd, dbname=db) as conn:
        pass
except Exception as e:
    sys.exit(1)
PYCODE
  do
    echo "Postgres no disponible aún, reintentando..."
    sleep 2
  done
fi

# Migraciones y collectstatic (seguro en prod; en local no hace daño)
python manage.py migrate --noinput
# Sólo en producción harás collectstatic con DEBUG=0
if [ "${DEBUG}" = "0" ] || [ "${DEBUG}" = "False" ] || [ "${DEBUG}" = "false" ]; then
    python manage.py collectstatic --noinput
fi

# Arranque: dev server o gunicorn según ENV
if [ "$DJANGO_RUNSERVER" = "1" ]; then
  echo "Iniciando Django runserver (desarrollo)..."
  exec python manage.py runserver 0.0.0.0:8000
else
  echo "Iniciando Gunicorn..."
  exec gunicorn main.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers ${GUNICORN_WORKERS:-3} \
      --threads ${GUNICORN_THREADS:-2} \
      --timeout ${GUNICORN_TIMEOUT:-120} \
      --access-logfile '-' --error-logfile '-'
fi
