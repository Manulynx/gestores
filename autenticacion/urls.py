from django.urls import path

from .views import Vregistro, cerrar_sesion, logear, administrar_usuarios, crear_usuario, editar_usuario, eliminar_usuario, historial_usuario, toggle_estado_usuario, obtener_usuario
from django.contrib.auth.decorators import user_passes_test, login_required

def admin_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.is_staff)(view_func)

urlpatterns = [
    path('', Vregistro.as_view(), name='Autenticacion'),
    path('cerrar_sesion', cerrar_sesion, name='cerrar_sesion'),
    path('logear', logear, name='Logear'),
    path('administrar-usuarios/', admin_required(administrar_usuarios), name='administrar_usuarios'),
    path('crear-usuario/', admin_required(crear_usuario), name='crear_usuario'),
    path('editar/<int:user_id>/', admin_required(editar_usuario), name='editar_usuario'),
    path('eliminar/<int:user_id>/', admin_required(eliminar_usuario), name='eliminar_usuario'),
    path('toggle-estado/<int:user_id>/', admin_required(toggle_estado_usuario), name='toggle_estado_usuario'),
    path('historial-usuario/<int:user_id>/', login_required(historial_usuario), name='historial_usuario'),
    path('eliminar-usuario/<int:user_id>/', eliminar_usuario, name='eliminar_usuario'),
    path('usuario/<int:user_id>/', admin_required(obtener_usuario), name='obtener_usuario'),
]
