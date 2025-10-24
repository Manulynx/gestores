from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Cliente
from .forms import ClienteForm

# Create your views here.

def buscar_cliente(request, carnet):
    try:
        cliente = Cliente.objects.get(carnet_identidad=carnet)
        
        # Only return client data if it belongs to the authenticated user
        if cliente.user == request.user:
            return JsonResponse({
                'status': 'success',
                'cliente': {
                    'id': cliente.id,
                    'nombre': cliente.nombre,
                    'apellidos': cliente.apellidos,
                    'telefono': cliente.telefono,
                    'nombre_completo': cliente.get_full_name()
                }
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Este cliente fue registrado por otro gestor'
            }, status=403)
            
    except Cliente.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Cliente no encontrado'
        }, status=404)

@login_required
def buscar_clientes_ajax(request):
    """Búsqueda AJAX de clientes para autocompletado"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'clientes': []})
    
    clientes = Cliente.objects.filter(
        user=request.user
    ).filter(
        Q(nombre__icontains=query) |
        Q(apellidos__icontains=query) |
        Q(carnet_identidad__icontains=query) |
        Q(telefono__icontains=query)
    )[:10]  # Limitar a 10 resultados
    
    clientes_data = [{
        'id': cliente.id,
        'nombre_completo': cliente.get_full_name(),
        'carnet_identidad': cliente.carnet_identidad,
        'telefono': cliente.telefono
    } for cliente in clientes]
    
    return JsonResponse({'clientes': clientes_data})

@login_required
def lista_clientes(request):
    """Vista para mostrar la lista de clientes del gestor"""
    search_query = request.GET.get('search', '')
    clientes_list = Cliente.objects.filter(user=request.user)
    
    if search_query:
        clientes_list = clientes_list.filter(
            Q(nombre__icontains=search_query) |
            Q(apellidos__icontains=search_query) |
            Q(carnet_identidad__icontains=search_query) |
            Q(telefono__icontains=search_query)
        )
    
    clientes_list = clientes_list.order_by('-created_at')
    
    # Paginación
    paginator = Paginator(clientes_list, 10)  # 10 clientes por página
    page_number = request.GET.get('page')
    clientes = paginator.get_page(page_number)
    
    context = {
        'clientes': clientes,
        'search_query': search_query,
        'total_clientes': clientes_list.count()
    }
    
    return render(request, 'clientes/lista_clientes.html', context)

@login_required
def crear_cliente(request):
    """Vista para crear un nuevo cliente"""
    if request.method == 'POST':
        form = ClienteForm(request.POST, user=request.user)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.user = request.user
            cliente.save()
            messages.success(request, f'Cliente {cliente.get_full_name()} creado exitosamente.')
            
            # Si viene desde AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': f'Cliente {cliente.get_full_name()} creado exitosamente.',
                    'cliente': {
                        'id': cliente.id,
                        'nombre_completo': cliente.get_full_name(),
                        'carnet_identidad': cliente.carnet_identidad,
                        'telefono': cliente.telefono
                    }
                })
            
            return redirect('clientes:lista_clientes')
        else:
            # Si viene desde AJAX y hay errores
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'errors': form.errors
                })
    else:
        form = ClienteForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Crear Cliente',
        'action': 'Crear'
    }
    
    return render(request, 'clientes/form_cliente.html', context)

@login_required
def editar_cliente(request, cliente_id):
    """Vista para editar un cliente existente"""
    cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)
    
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cliente {cliente.get_full_name()} actualizado exitosamente.')
            
            # Si viene desde AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': f'Cliente {cliente.get_full_name()} actualizado exitosamente.',
                    'cliente': {
                        'id': cliente.id,
                        'nombre_completo': cliente.get_full_name(),
                        'carnet_identidad': cliente.carnet_identidad,
                        'telefono': cliente.telefono
                    }
                })
            
            return redirect('clientes:lista_clientes')
        else:
            # Si viene desde AJAX y hay errores
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'errors': form.errors
                })
    else:
        form = ClienteForm(instance=cliente, user=request.user)
    
    context = {
        'form': form,
        'cliente': cliente,
        'title': 'Editar Cliente',
        'action': 'Actualizar'
    }
    
    return render(request, 'clientes/form_cliente.html', context)

@login_required
def eliminar_cliente(request, cliente_id):
    """Vista para eliminar un cliente"""
    cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)
    
    if request.method == 'POST':
        nombre_cliente = cliente.get_full_name()
        cliente.delete()
        messages.success(request, f'Cliente {nombre_cliente} eliminado exitosamente.')
        
        # Si viene desde AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': f'Cliente {nombre_cliente} eliminado exitosamente.'
            })
        
        return redirect('clientes:lista_clientes')
    
    context = {
        'cliente': cliente,
        'title': 'Eliminar Cliente'
    }
    
    return render(request, 'clientes/confirmar_eliminacion.html', context)

@login_required
def detalle_cliente(request, cliente_id):
    """Vista para ver detalles de un cliente"""
    cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)
    
    context = {
        'cliente': cliente,
        'title': 'Detalles del Cliente'
    }
    
    return render(request, 'clientes/detalle_cliente.html', context)

@login_required
def crear_cliente_modal(request):
    """Vista para crear cliente desde un modal (AJAX)"""
    if request.method == 'POST':
        form = ClienteForm(request.POST, user=request.user)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.user = request.user
            cliente.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Cliente {cliente.get_full_name()} creado exitosamente.',
                'cliente': {
                    'id': cliente.id,
                    'nombre_completo': cliente.get_full_name(),
                    'carnet_identidad': cliente.carnet_identidad,
                    'telefono': cliente.telefono
                }
            })
        else:
            return JsonResponse({
                'status': 'error',
                'errors': form.errors
            })
    
    # GET request - devolver el formulario
    form = ClienteForm(user=request.user)
    context = {
        'form': form,
        'modal': True
    }
    
    return render(request, 'clientes/form_cliente_modal.html', context)
