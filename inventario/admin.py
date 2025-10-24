from django.contrib import admin
from .models import Categoria, Material, MaterialImagen


# Register your models here.

class ServicioAdmin(admin.ModelAdmin):
    readonly_fields = ('created', 'updated')

admin.site.register(MaterialImagen)
admin.site.register(Categoria)
admin.site.register(Material, ServicioAdmin)
