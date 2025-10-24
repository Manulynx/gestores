from django.db import models
from django.contrib.auth.models import User

class SesionUsuario(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, null=True)
    ip_address = models.GenericIPAddressField(null=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sesión de Usuario"
        verbose_name_plural = "Sesiones de Usuarios"

class PerfilGestor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    nombre_gestor = models.CharField(max_length=100, verbose_name="Nombre del Gestor")
    
    class Meta:
        verbose_name = "Perfil de Gestor"
        verbose_name_plural = "Perfiles de Gestores"

    def __str__(self):
        return f"Perfil de {self.user.username}"
