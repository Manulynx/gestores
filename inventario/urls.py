from django.urls import path

from . import views
from django.contrib.auth.decorators import user_passes_test

def admin_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.is_staff)(view_func)

urlpatterns = [
    path('', views.inventario, name='inventario'),
    path('categoria/<int:categoria_id>/', views.categoria, name='categoria'),
    path('editar-inventario/', admin_required(views.editar_inventario), name='editar_inventario'),
    path('editar-material/<int:material_id>/', admin_required(views.editar_material), name='editar_material'),
    path('eliminar-imagen/<int:imagen_id>/', admin_required(views.eliminar_imagen), name='eliminar_imagen'),
    path('crear-material/', admin_required(views.crear_material), name='crear_material'),
    path('eliminar-material/<int:material_id>/', admin_required(views.eliminar_material), name='eliminar_material'),
    path('pedidos-pendientes/<int:material_id>/', views.pedidos_pendientes, name='pedidos_pendientes'),
    path('toggle-destacado/<int:material_id>/', admin_required(views.toggle_destacado), name='toggle_destacado'),
    path('material/<int:material_id>/imagenes/', views.material_imagenes, name='material_imagenes'),
    path('toggle-activo/<int:material_id>/', admin_required(views.toggle_activo), name='toggle_activo'),
    path('crear-categoria/', admin_required(views.crear_categoria), name='crear_categoria'),
    path('toggle-oferta/<int:material_id>/', admin_required(views.toggle_oferta), name='toggle_oferta'),
    path('editar-categoria/<int:categoria_id>/', admin_required(views.editar_categoria), name='editar_categoria'),
    path('eliminar-categoria/<int:categoria_id>/', admin_required(views.eliminar_categoria), name='eliminar_categoria'),
]
