from django.db import models
from django.contrib.auth import get_user_model
from clientes.models import Cliente
from inventario.models import Material
import uuid
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
# Create your models here.

User = get_user_model()

class Pedido(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('efectuado', 'Efectuado'),
        ('cancelado', 'Cancelado'),
        ('reactivado', 'Reactivado'),      # Nuevo estado
        ('reactivacion', 'Reactivación'),  # Nuevo estado
    ]

    def generate_unique_code():
        return str(uuid.uuid4())[:10]  # Genera un código aleatorio de 10 caracteres

    codigo_unico = models.CharField(
        max_length=10, 
        unique=True, 
        editable=False,
        default=generate_unique_code
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado del pedido'
    )
    transportista = models.CharField(max_length=100, null=True, blank=True, verbose_name='Transportista')
    pedido_original = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reactivaciones'
    )
    numero_reactivacion = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if self.pedido_original:
            # Contar el número de reactivaciones previas
            self.numero_reactivacion = self.pedido_original.reactivaciones.count() + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Pedido #{self.id} - {self.user.username}- {self.created_at}'

    class Meta:
        db_table = 'pedidos'
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'
        ordering = ['id']

    def actualizar_cantidades_material(self):
        """Actualiza las cantidades de materiales cuando se efectúa un pedido"""
        try:
            with transaction.atomic():
                for detalle in self.pedidodetalle_set.all():
                    material = detalle.material
                    # Ya no es necesario restar la cantidad aquí porque ya se restó cuando se creó el pedido
                    # Solo necesitamos verificar que haya suficiente stock
                    if material.cantidad < 0:
                        raise ValueError(f"Stock insuficiente para {material.nombre}")
                    material.save()
            return True
        except Exception as e:
            print(f"Error actualizando cantidades: {str(e)}")
            return False

    def efectuar(self):
        with transaction.atomic():
            self.estado = 'efectuado'
            self.save()

    @property
    def comision_total(self):
        """Calcula la comisión total del pedido basada en los detalles"""
        return sum(detalle.comision for detalle in self.pedidodetalle_set.all())
    
class PedidoDetalle(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    precio_unitario = models.FloatField(verbose_name='Precio Unitario Usado', null=True, blank=True)
    en_oferta = models.BooleanField(default=False)
    precio_regular = models.FloatField(verbose_name='Precio Regular', null=True, blank=True)
    
    @property
    def comision(self):
        """Calcula la comisión para este detalle"""
        if self.material and self.material.comision:
            return self.cantidad * self.material.comision
        return 0

    @property
    def descuento_aplicado(self):
        if self.en_oferta:
            return ((self.precio_regular - self.precio_unitario) / self.precio_regular) * 100
        return 0

    def __str__(self):
        return f'{self.cantidad}x {self.material.nombre} - Pedido #{self.pedido.nombre_cliente} - {self.created_at}'

    class Meta:
        db_table = 'pedidosdetalle'
        verbose_name = 'Detalle de pedido'
        verbose_name_plural = 'Detalles de pedidos'

class ConfiguracionPedidos(models.Model):
    tiempo_eliminacion = models.IntegerField(
        default=24,
        verbose_name="Tiempo de cancelación (horas)",
        help_text="Tiempo después del cual se cancelarán automáticamente los pedidos pendientes"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Cancelación automática activa"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de Pedidos"
        verbose_name_plural = "Configuraciones de Pedidos"

@login_required(login_url='/autenticacion/logear')
def efectuar_pedido(request, pedido_id):
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id, user=request.user)
        
        if pedido.estado == 'efectuado':
            return JsonResponse({
                'status': 'warning',
                'message': 'Este pedido ya fue efectuado'
            })

        if not pedido.pedidodetalle_set.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'El pedido no tiene detalles'
            })

        with transaction.atomic():
            # Verificar stock disponible
            for detalle in pedido.pedidodetalle_set.all():
                if detalle.material.cantidad < 0:
                    raise ValueError(f"Stock insuficiente para {detalle.material.nombre}")

            # Actualizar estado del pedido
            pedido.estado = 'efectuado'
            pedido.save()
            
            # No es necesario llamar a actualizar_cantidades_material() 
            # porque el stock ya se restó cuando se creó el pedido
            
            return JsonResponse({
                'status': 'success',
                'message': 'Pedido efectuado correctamente',
                'refresh': True
            })
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error al efectuar el pedido: {str(e)}'
        }, status=500)
