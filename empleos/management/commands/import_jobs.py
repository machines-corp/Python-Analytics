import json
from django.core.management.base import BaseCommand
from empleos.models import Source, Company, Location, JobPosting, Tag, JobTag, Benefit, JobBenefit

def _get_or_create(model, **kwargs):
    obj, _ = model.objects.get_or_create(**kwargs)
    return obj

def _split_tags(raw):
    if not raw:
        return []
    # vienen como "kw1;kw2;kw3"
    return [t.strip() for t in str(raw).split(";") if t.strip()]

class Command(BaseCommand):
    help = "Importa empleos desde JSONL (Computrabajo y Laborum)"

    def add_arguments(self, parser):
        parser.add_argument("--computrabajo", type=str, help="Ruta JSONL computrabajo", required=False)
        parser.add_argument("--laborum", type=str, help="Ruta JSONL laborum", required=False)

    def handle(self, *args, **opts):
        if opts.get("computrabajo"):
            self.import_file(opts["computrabajo"], source_name="Computrabajo")
        if opts.get("laborum"):
            self.import_file(opts["laborum"], source_name="Laborum")

    def import_file(self, path, source_name):
        self.stdout.write(self.style.WARNING(f"Importando {source_name} desde {path} ..."))
        src = _get_or_create(Source, name=source_name)

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)

                # Company
                company = _get_or_create(Company, name=(row.get("empresa") or "Desconocida"))
                # En Laborum, podemos traer señales
                if "empresa_verificada" in row and row["empresa_verificada"] is not None:
                    company.verified = bool(row["empresa_verificada"])
                if "rating_empresa" in row and row["rating_empresa"] is not None:
                    try:
                        company.rating = float(row["rating_empresa"])
                    except:
                        pass
                company.save()

                # Location
                loc = None
                if row.get("ubicacion"):
                    loc = _get_or_create(Location, raw_text=row["ubicacion"])

                # Job
                job, created = JobPosting.objects.get_or_create(
                    url=row["url"],
                    defaults=dict(
                        source=src,
                        source_job_id=row.get("id_oferta"),
                        hash=row.get("hash"),
                        title=row.get("titulo") or "(sin título)",
                        company=company,
                        location=loc,
                        published_date=row.get("fecha_publicacion") or None,
                        description=row.get("descripcion") or None,
                        work_modality=row.get("modalidad_trabajo") or None,
                        contract_type=row.get("tipo_contrato") or None,
                        workday=row.get("jornada") or None,
                        salary_text=row.get("salario") or None,
                        accessibility_mentioned=bool(row.get("accesibilidad_mencionada")),
                        transport_mentioned=bool(row.get("transporte_mencionado")),
                        disability_friendly=bool(row.get("apto_discapacidad")) if "apto_discapacidad" in row else False,
                        multiple_vacancies=bool(row.get("multiple_vacantes")) if "multiple_vacantes" in row else False,
                        area=row.get("area") or None,
                        subarea=row.get("subarea") or None,
                        min_experience=row.get("experiencia_min") or None,
                        min_education=row.get("educacion_min") or None,
                    )
                )

                # Tags (accesibilidad / transporte)
                for tag_name in _split_tags(row.get("tags_accesibilidad")):
                    tag = _get_or_create(Tag, name=tag_name)
                    _ = _get_or_create(JobTag, job=job, tag=tag, kind="accessibility")

                for tag_name in _split_tags(row.get("tags_transporte")):
                    tag = _get_or_create(Tag, name=tag_name)
                    _ = _get_or_create(JobTag, job=job, tag=tag, kind="transport")

                # Beneficios (Laborum puede traer lista)
                if isinstance(row.get("beneficios"), list):
                    for bname in row["beneficios"]:
                        if not bname: 
                            continue
                        ben = _get_or_create(Benefit, name=str(bname))
                        _ = _get_or_create(JobBenefit, job=job, benefit=ben)

        self.stdout.write(self.style.SUCCESS(f"OK {source_name}"))