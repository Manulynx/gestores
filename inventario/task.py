'''from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Pedido

@shared_task
def eliminar_pedidos_antiguos():
    limite = timezone.now() - timedelta(hours=24)
    Pedido.objects.filter(created_at__lte=limite).delete()'''