# Python-Analytics

python empleos/scraping_2.py \
    --pages 2 \
    --out-json out/empleos_laborum_discapacidad.jsonl \
    --out-csv out/empleos_laborum_discapacidad.csv


python manage.py import_jobs \
  --computrabajo /app/out/empleos_inclusivos.jsonl \
  --laborum /app/out/empleos_laborum_discapacidad.jsonl

  PGPASSWORD=apppass psql -h db -p 5432 -U appuser -d appdb

  \dt ver tablas


📊 Resultados de la Prueba:
El sistema está funcionando correctamente y encontró:
4 industrias reales (Tecnología, Servicios, Retail, Finanzas)
3 modalidades reales (Remoto, Presencial, Híbrido)
2 áreas reales (asdasd, Desarrollo / datos)
13 ubicaciones reales (Santiago, Concepción, Talca, etc.)
191 roles reales de la base de datos
27 categorías de sinónimos dinámicos generados

# Importar empleos con límite por defecto (100)
python manage.py import_bne

# Importar con límite personalizado
python manage.py import_bne --limit 50

# Importar con offset para paginación
python manage.py import_bne --limit 100 --offset 100