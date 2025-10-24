from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MaterialViewSet, PedidoViewSet

router = DefaultRouter()
router.register(r'materiales', MaterialViewSet)
router.register(r'pedidos', PedidoViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls')),
]