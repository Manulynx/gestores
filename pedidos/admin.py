from django.contrib import admin
from .models import Pedido, PedidoDetalle

class PedidoDetalleInline(admin.TabularInline):
    model = PedidoDetalle
    extra = 0

class PedidoAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'created_at']
    inlines = [PedidoDetalleInline]

admin.site.register(Pedido, PedidoAdmin)
admin.site.register(PedidoDetalle)
