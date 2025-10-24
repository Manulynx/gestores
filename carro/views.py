from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from .carro import Carro
from inventario.models import Material

# Create your views here.

def agregar_material(request, material_id):
    carro = Carro(request)
    material = Material.objects.get(id=material_id)
    result = carro.agregar(material=material)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if result:
            return JsonResponse({
                'status': 'success',
                'message': f'¡{material.nombre} agregado al carrito!',
                'cart_count': len(request.session.get('carro', {}))
            })
        else:
            return JsonResponse({
                'status': 'danger',
                'message': 'No hay suficiente stock disponible',
                'cart_count': len(request.session.get('carro', {}))
            })
    
    return redirect(request.META.get('HTTP_REFERER'))

def eliminar_material(request, material_id):
    carro = Carro(request)
    material = Material.objects.get(id=material_id)
    
    try:
        carro.eliminar(material)
        return JsonResponse({
            'status': 'success',
            'message': 'Material eliminado correctamente',
            'cart_count': len(request.session.get('carro', {}))
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

def restar_material(request, material_id):
    carro = Carro(request)
    material = Material.objects.get(id=material_id)
    carro.restar_material(material)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': f'Cantidad de {material.nombre} reducida',
            'cart_count': len(request.session.get('carro', {}))
        })
    
    return redirect(request.META.get('HTTP_REFERER'))

def limpiar_carro(request):
    carro = Carro(request)
    carro.limpiar_carro()
    return redirect(request.META.get('HTTP_REFERER'))

def widget_cart(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'carro/widget.html')
    return HttpResponse(status=400)

def actualizar_cantidad(request, material_id, cantidad):
    carro = Carro(request)
    material = Material.objects.get(id=material_id)
    
    # Verificar stock disponible
    if material.cantidad < cantidad:
        return JsonResponse({
            'status': 'danger',
            'message': 'No hay suficiente stock disponible',
            'cart_count': len(request.session.get('carro', {}))
        })
    
    # Actualizar cantidad
    result = carro.actualizar_cantidad(material, cantidad)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if result:
            # Calcular el nuevo total
            total = sum(float(item['precio']) for item in request.session['carro'].values())
            return JsonResponse({
                'status': 'success',
                'message': 'Cantidad actualizada',
                'cart_count': len(request.session.get('carro', {})),
                'total': total
            })
        else:
            return JsonResponse({
                'status': 'danger',
                'message': 'Error al actualizar cantidad',
                'cart_count': len(request.session.get('carro', {}))
            })
    
    return redirect(request.META.get('HTTP_REFERER'))