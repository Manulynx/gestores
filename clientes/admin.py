from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellidos', 'telefono', 'carnet_identidad')
    search_fields = ('nombre', 'apellidos', 'carnet_identidad')
    ordering = ('apellidos', 'nombre')
