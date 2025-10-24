from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    path('', views.lista_clientes, name='lista_clientes'),
    path('crear/', views.crear_cliente, name='crear_cliente'),
    path('crear-modal/', views.crear_cliente_modal, name='crear_cliente_modal'),
    path('buscar-ajax/', views.buscar_clientes_ajax, name='buscar_clientes_ajax'),
    path('<int:cliente_id>/', views.detalle_cliente, name='detalle_cliente'),
    path('<int:cliente_id>/editar/', views.editar_cliente, name='editar_cliente'),
    path('<int:cliente_id>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),
    path('buscar/<str:carnet>/', views.buscar_cliente, name='buscar_cliente'),
]