# Python-Analytics

python empleos/scraping_2.py \
    --pages 2 \
    --out-json empleos_laborum_discapacidad.jsonl \
    --out-csv empleos_laborum_discapacidad.csv


python manage.py import_jobs \
  --computrabajo /app/out/empleos_inclusivos.jsonl \
  --laborum /app/empleos_laborum_discapacidad.jsonl

  PGPASSWORD=apppass psql -h db -p 5432 -U appuser -d appdb

  \dt ver tablas