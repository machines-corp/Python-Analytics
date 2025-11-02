from django.db import models


class Conversation(models.Model):

    state = models.JSONField(default=dict, blank=True)     
    history = models.JSONField(default=list, blank=True)   
    created_at = models.DateTimeField(auto_now_add=True)


class Source(models.Model):
    """
    Portal/fuente del empleo (Computrabajo, Laborum, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name


class Company(models.Model):
    """
    Empresa normalizada. Útil para agrupar empleos de la misma empresa,
    aunque provengan de distintos portales.
    """
    name = models.CharField(max_length=255, db_index=True)
    verified = models.BooleanField(default=False, help_text="Solo algunos portales lo exponen (Laborum)")
    rating = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)

    class Meta:
        unique_together = [("name",)]  # simple dedupe por nombre

    def __str__(self):
        return self.name


class Location(models.Model):
    """
    Ubicación textual (puede ser comuna + región).
    Si más adelante necesitas normalizar a regiones/comunas, puedes
    añadir campos o una jerarquía.
    """
    raw_text = models.CharField(max_length=255, db_index=True)

    class Meta:
        unique_together = [("raw_text",)]

    def __str__(self):
        return self.raw_text


class JobPosting(models.Model):
    """
    Oferta de empleo unificada. Une lo común y lo opcional de ambos sitios.
    """
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="jobs")
    source_job_id = models.CharField(max_length=64, blank=True, null=True, help_text="ID del portal si existe (p.ej. Laborum id_oferta).")
    url = models.URLField(max_length=1000, unique=True)
    hash = models.CharField(max_length=64, db_index=True, blank=True, null=True)

    title = models.CharField(max_length=500)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="jobs")
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, blank=True, null=True, related_name="jobs")

    published_date = models.DateField(blank=True, null=True)

    # Campos comunes / heurísticos
    description = models.TextField(blank=True, null=True)
    work_modality = models.CharField(max_length=30, blank=True, null=True, help_text="remoto/híbrido/presencial")
    contract_type = models.CharField(max_length=60, blank=True, null=True)
    workday = models.CharField(max_length=30, blank=True, null=True, help_text="full-time/part-time")
    salary_text = models.CharField(max_length=200, blank=True, null=True)

    # Inclusión / transporte
    accessibility_mentioned = models.BooleanField(default=False)
    transport_mentioned = models.BooleanField(default=False)

    # Señales específicas de Laborum (opcionales)
    disability_friendly = models.BooleanField(default=False)       # apto_discapacidad
    multiple_vacancies = models.BooleanField(default=False)
    # Company.verified / rating quedan en Company

    # Clasificación opcional
    area = models.CharField(max_length=120, blank=True, null=True)
    subarea = models.CharField(max_length=120, blank=True, null=True)
    min_experience = models.CharField(max_length=120, blank=True, null=True)
    min_education = models.CharField(max_length=120, blank=True, null=True)

    # Timestamps locales
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["published_date"]),
            models.Index(fields=["title"]),
            models.Index(fields=["hash"]),
        ]

    def __str__(self):
        return f"{self.title} @ {self.company.name}"


class Tag(models.Model):
    """
    Tag genérico (accesibilidad/transporte u otros).
    """
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class JobTag(models.Model):
    """
    Relación N:M entre JobPosting y Tag, con un 'kind' para distinguir
    si el tag es de accesibilidad, transporte, etc.
    """
    KIND_CHOICES = (
        ("accessibility", "Accessibility"),
        ("transport", "Transport"),
        ("other", "Other"),
    )
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="job_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="tagged_jobs")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="other")

    class Meta:
        unique_together = [("job", "tag", "kind")]


class Benefit(models.Model):
    """
    Beneficio normalizado (si el portal lo expone; Laborum a veces lista algunos)
    """
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name


class JobBenefit(models.Model):
    """
    Relación N:M de JobPosting con Benefit.
    """
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="job_benefits")
    benefit = models.ForeignKey(Benefit, on_delete=models.CASCADE, related_name="benefit_jobs")

    class Meta:
        unique_together = [("job", "benefit")]