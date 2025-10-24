from django.db import models
from django.contrib.auth.models import User


class Cliente(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Gestor")
    nombre = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    carnet_identidad = models.CharField(max_length=11, unique=True)
    telefono = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_full_name(self):
        return f"{self.nombre} {self.apellidos}"

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['apellidos', 'nombre']
