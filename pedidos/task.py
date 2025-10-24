from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
import logging
from .models import Pedido, ConfiguracionPedidos, PedidoDetalle

'''@shared_task
def eliminar_pedidos_antiguos():
    try:
        config = ConfiguracionPedidos.objects.first()
        if not config or not config.activo:
            return "Eliminación automática desactivada"

        limite = timezone.now() - timedelta(hours=config.tiempo_eliminacion)
        pedidos = Pedido.objects.filter(
            created_at__lte=limite,
            estado='pendiente'
        )
        
        count = pedidos.count()
        pedidos.delete()
        
        return f"Se eliminaron {count} pedidos antiguos"
    except Exception as e:
        return f"Error al eliminar pedidos: {str(e)}"'''

@shared_task
def cancelar_pedidos_antiguos():
    logger = logging.getLogger(__name__)
    try:
        config = ConfiguracionPedidos.objects.first()
        logger.info(f"Iniciando cancelación automática de pedidos. Configuración: {config}")
        if not config or not config.activo:
            return "Cancelación automática desactivada"

        limite = timezone.now() - timedelta(hours=config.tiempo_eliminacion)
        pedidos = Pedido.objects.filter(
            created_at__lte=limite,
            estado='pendiente'
        )
        
        count = 0
        for pedido in pedidos:
            try:
                with transaction.atomic():
                    # Verificar consistencia antes de restaurar
                    for detalle in pedido.pedidodetalle_set.all():
                        if detalle.cantidad <= 0:
                            raise ValueError(f"Cantidad inválida en detalle {detalle.id}")
                        
                    # Restaurar stock y cancelar
                    for detalle in pedido.pedidodetalle_set.all():
                        detalle.material.actualizar_stock(detalle.cantidad)
                    
                    pedido.estado = 'cancelado'
                    pedido.save()
                    count += 1
                    logger.info(f"Pedido {pedido.id} cancelado exitosamente")
            except Exception as e:
                logger.error(f"Error en pedido {pedido.id}: {str(e)}")
                continue
        
        return f"Se cancelaron {count} pedidos antiguos"
    except Exception as e:
        logger.error(f"Error en cancelación automática: {str(e)}")
        return f"Error al cancelar pedidos: {str(e)}"


