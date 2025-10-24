from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import resolve
from .models import SesionUsuario
from django.contrib.auth.models import User

class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                session = SesionUsuario.objects.get(usuario=request.user)
                if session.session_key != request.session.session_key:
                    logout(request)
                    messages.warning(request, 
                        "Tu sesión se ha iniciado en otro dispositivo")
                    return redirect('Logear')
            except SesionUsuario.DoesNotExist:
                pass

        response = self.get_response(request)
        return response

class PermissionsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Rutas que requieren permisos de administrador
        self.admin_routes = [
            'administrar_usuarios',
            'crear_usuario',
            'editar_usuario',
            'eliminar_usuario',
            'toggle_estado_usuario',
            'editar_inventario',
            'crear_material',
            'editar_material',
            'eliminar_material'
        ]

    def __call__(self, request):
        if request.user.is_authenticated:
            current_url_name = resolve(request.path_info).url_name
            
            if current_url_name in self.admin_routes and not request.user.is_staff:
                messages.error(request, 
                    "No tienes permisos para acceder a esta sección")
                return redirect('home')

        response = self.get_response(request)
        return response