from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import View
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Count, Sum, Q, F, Case, When, DecimalField as DjangoDecimalField
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from pedidos.models import Pedido
from .models import SesionUsuario

# Create your views here.

class Vregistro(View):
    def get(self, request):
        form = UserCreationForm()
        return render(request, 'registro/registro.html', {'form': form})
    
    def post(self, request):
        form= UserCreationForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            return redirect('home') 
        else:
            for msg in form.error_messages:
                messages.error(request, form.error_messages[msg])

            return render(request, 'registro/registro.html', {'form': form})
        
def cerrar_sesion(request):
    if request.user.is_authenticated:
        try:
            sesion = SesionUsuario.objects.get(usuario=request.user)
            sesion.delete()
        except SesionUsuario.DoesNotExist:
            pass
    logout(request)
    return redirect('home')

def logear(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            usuario = authenticate(username=username, password=password)
            
            if usuario is not None:
                # Verificar si el usuario ya tiene una sesión activa
                try:
                    sesion_existente = SesionUsuario.objects.get(usuario=usuario)
                    if sesion_existente.session_key != request.session.session_key:
                        # Forzar cierre de la sesión anterior
                        logout(request)
                        messages.warning(request, 
                            "Se ha cerrado tu sesión en otro dispositivo")
                except SesionUsuario.DoesNotExist:
                    pass

                login(request, usuario)
                
                # Actualizar o crear registro de sesión
                SesionUsuario.objects.update_or_create(
                    usuario=usuario,
                    defaults={
                        'session_key': request.session.session_key,
                        'ip_address': request.META.get('REMOTE_ADDR')
                    }
                )
                
                return redirect('home')

        else:
            messages.error(request, "Usuario o contraseña incorrectos")

    form = AuthenticationForm()
    return render(request, "login/login.html", {"form": form})

def is_superuser(user):
    return user.is_superuser

@user_passes_test(is_superuser)
def administrar_usuarios(request):
    try:
        # Obtener fechas del filtro
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')
        search_term = request.GET.get('search', '').strip()
        
        # Obtener usuarios base
        usuarios = User.objects.all().order_by('username')

        # Aplicar búsqueda si existe
        if search_term:
            usuarios = usuarios.filter(
                Q(username__icontains=search_term) |
                Q(first_name__icontains=search_term) |
                Q(last_name__icontains=search_term)
            )

        # Crear el filtro base para pedidos efectuados
        pedidos_query = Pedido.objects.filter(estado='efectuado')
        
        # Aplicar filtro de fechas a los pedidos si se especifican
        if fecha_desde and fecha_hasta:
            pedidos_query = pedidos_query.filter(
                created_at__date__range=[fecha_desde, fecha_hasta]
            )

        # Obtener usuarios con sus estadísticas
        usuarios = usuarios.annotate(
            pedidos_count=Count('pedido', distinct=True),
            ventas_mes=Sum(
                Case(
                    When(pedido__in=pedidos_query, then=F('pedido__total')),
                    default=0,
                    output_field=DjangoDecimalField(max_digits=10, decimal_places=2)
                )
            )
        )

        # Calcular comisiones
        for usuario in usuarios:
            comision_total = (pedidos_query.filter(user=usuario)
                .annotate(
                    comision_pedido=Sum(F('pedidodetalle__cantidad') * F('pedidodetalle__material__comision'))
                )
                .aggregate(total=Sum('comision_pedido'))['total'] or 0)
            usuario.comision_total = comision_total

        # Obtener usuarios activos en las últimas 24 horas
        ultima_actividad = timezone.now() - timezone.timedelta(hours=24)
        usuarios_activos = SesionUsuario.objects.filter(
            last_activity__gte=ultima_actividad
        ).count()

        context = {
            'usuarios': usuarios,
            'usuarios_activos_hoy': usuarios_activos,
            'total_pedidos': pedidos_query.count(),
            'total_ventas': pedidos_query.aggregate(total=Sum('total'))['total'] or 0,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta
        }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, 'autenticacion/administrar_usuarios.html', context)
        return render(request, 'autenticacion/administrar_usuarios.html', context)
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
        raise e

@login_required
def crear_usuario(request):
    if request.method == 'POST':
        try:
            # Validar campos
            username = request.POST.get('username')
            password = request.POST.get('password')
            nombre_gestor = request.POST.get('nombre_gestor')
            apellidos = request.POST.get('apellidos')
            is_superuser = request.POST.get('is_superuser') == 'on'
            
            if not all([username, password, nombre_gestor, apellidos]):
                raise ValueError("Todos los campos son obligatorios")
            
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=nombre_gestor,
                last_name=apellidos,
                is_superuser=is_superuser,
                is_staff=is_superuser
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': f'Gestor {username} creado correctamente'
                })
            
            messages.success(request, f'Gestor {username} creado correctamente')
            return redirect('administrar_usuarios')
            
        except ValueError as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
            messages.error(request, str(e))
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': 'Error al crear el gestor'
                })
            messages.error(request, f'Error al crear el gestor: {str(e)}')
    
    return redirect('administrar_usuarios')

@login_required
def editar_usuario(request, user_id):
    if request.method == 'POST':
        try:
            user = User.objects.get(id=user_id)
            
            # Actualizar campos básicos
            user.username = request.POST.get('username')
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            
            # Actualizar contraseña solo si se proporciona una nueva
            new_password = request.POST.get('password')
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Usuario actualizado correctamente'
            })
        except User.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Usuario no encontrado'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Método no permitido'
    })

from django.http import JsonResponse

def eliminar_usuario(request, user_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            user = User.objects.get(id=user_id)
            user.delete()
            return JsonResponse({
                'status': 'success',
                'message': 'Usuario eliminado correctamente'
            })
        except User.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Usuario no encontrado'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    return JsonResponse({
        'status': 'error',
        'message': 'Método no permitido'
    }, status=405)

@login_required
def historial_usuario(request, user_id):
    try:
        # Verificar si el usuario es admin o si está intentando ver su propio historial
        user_to_view = get_object_or_404(User, id=user_id)
        if not request.user.is_staff and request.user.id != user_id:
            messages.error(request, "No tienes permiso para ver el historial de otros usuarios")
            return redirect('home')

        usuario = get_object_or_404(User, id=user_id)
        
        # Obtener fechas del filtro si existen
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')
        
        # Crear el filtro base
        fecha_filter = Q()
        if fecha_desde:
            fecha_filter &= Q(created_at__date__gte=fecha_desde)
        if fecha_hasta:
            fecha_filter &= Q(created_at__date__lte=fecha_hasta)

        # Obtener pedidos con filtros
        pedidos = Pedido.objects.filter(user=usuario)
        if fecha_desde or fecha_hasta:
            pedidos = pedidos.filter(fecha_filter)
        
        # Calcular totales solo para pedidos efectuados
        pedidos_efectuados = pedidos.filter(estado='efectuado')
        total_ventas = pedidos_efectuados.aggregate(
            total=Sum('total'))['total'] or 0
            
        # Calcular comisiones utilizando la relación con PedidoDetalle
        total_comisiones = (pedidos_efectuados
            .annotate(
                comision=Sum(F('pedidodetalle__material__comision') * 
                           F('pedidodetalle__cantidad'))
            )
            .aggregate(total=Sum('comision'))['total'] or 0)

        context = {
            'usuario': usuario,
            'pedidos': pedidos.order_by('-created_at'),
            'pedidos_count': pedidos.count(),
            'total_ventas': total_ventas,
            'total_comisiones': total_comisiones,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta
        }
        
        return render(request, 'autenticacion/historial_usuario.html', context)
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
        raise e

@login_required
def toggle_estado_usuario(request, user_id):
    if request.method == 'POST':
        try:
            user = User.objects.get(id=user_id)
            
            # No permitir desactivar super usuarios si no eres superusuario
            if user.is_superuser and not request.user.is_superuser:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No tienes permisos para modificar administradores'
                })
            
            user.is_active = not user.is_active
            user.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Usuario {"activado" if user.is_active else "desactivado"} correctamente',
                'is_active': user.is_active
            })
        except User.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Usuario no encontrado'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Método no permitido'
    })

@login_required
def obtener_usuario(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        return JsonResponse({
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_superuser': user.is_superuser
        })
    except User.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Usuario no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)