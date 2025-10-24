from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from inventario.models import Material
from pedidos.models import Pedido
from .serializers import MaterialSerializer, PedidoSerializer, UserSerializer

class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]

class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.all()
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pedido.objects.filter(user=self.request.user)