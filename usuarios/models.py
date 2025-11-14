from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('talent', 'talento'),
        ('company', 'Empresa'),
        ('admin', 'Administrador'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='worker')

    company_name = models.CharField(max_length=255, blank=True, null=True)
    
    rut_empresa = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
