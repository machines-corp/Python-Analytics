from django.db import models

class Job(models.Model):
    CURRENCY_CHOICES = [("USD","USD"), ("CLP","CLP")]
    MODALITY_CHOICES = [("Remoto","Remoto"), ("Híbrido","Híbrido"), ("Presencial","Presencial")]
    SENIORITY_CHOICES = [("Junior","Junior"), ("Semi","Semi"), ("Senior","Senior")]

    title = models.CharField(max_length=200)
    industry = models.CharField(max_length=100)          # Tecnología, Educación, Salud, Finanzas, etc.
    area = models.CharField(max_length=100)              # Datos, Desarrollo, Docencia, etc.
    role = models.CharField(max_length=150)              # Data Analyst, Backend Developer, etc.
    seniority = models.CharField(max_length=20, choices=SENIORITY_CHOICES)
    modality = models.CharField(max_length=20, choices=MODALITY_CHOICES)
    schedule = models.CharField(max_length=20, default="Completa")  # Completa/Parcial
    location = models.CharField(max_length=100, default="Chile")    # Chile / LatAm / Ciudad
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="USD")
    salary_min = models.IntegerField(null=True, blank=True)
    salary_max = models.IntegerField(null=True, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.title} - {self.role}"

class Conversation(models.Model):

    state = models.JSONField(default=dict, blank=True)     
    history = models.JSONField(default=list, blank=True)   
    created_at = models.DateTimeField(auto_now_add=True)