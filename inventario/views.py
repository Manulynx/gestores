from django.shortcuts import render, get_object_or_404
from django.contrib import messages

from django.shortcuts import render, redirect
from inventario.models import Categoria, Material, MaterialImagen
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.http import JsonResponse
from django.db.models import Q
from pedidos.models import PedidoDetalle
from django.db.models import F
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import user_passes_test

# Create your views here.
def inventario(request):
    categoria_id = request.GET.get('categoria')
    search_query = request.GET.get('search', '')
    categorias = Categoria.objects.all()
    
    # Start with all active materials
    materiales = Material.objects.filter(activo=True)
    
    # Apply category filter if selected
    if categoria_id:
        materiales = materiales.filter(categoria_id=categoria_id)
    
    # Apply search filter if provided
    if search_query:
        materiales = materiales.filter(
            Q(nombre__icontains=search_query) | 
            Q(codigo__icontains=search_query)
        )
    
    # Order the materials based on multiple criteria using annotate and Case
    from django.db.models import Case, When, Value, IntegerField
    materiales = materiales.annotate(
        order_priority=Case(
            # First priority: en_oferta=True
            When(en_oferta=True, then=Value(1)),
            # Second priority: destacado=True
            When(destacado=True, then=Value(2)),
            # Third priority: everything else
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by(
        'order_priority',  # First by priority (ofertas, destacados, resto)
        'categoria__nombre',  # Then by category name
        'nombre'  # Finally alphabetically
    )
    
    context = {
        'materiales': materiales,
        'categorias': categorias,
        'categoria_seleccionada': categoria_id,
        'search_query': search_query
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'inventario/inventario.html', context)
    return render(request, 'inventario/inventario.html', context)

def categoria(request, categoria_id):
    # Obtener la categoría usando get(id=categoria_id)
    categoria = Categoria.objects.get(id=categoria_id)
    # Obtener los materiales filtrados por esa categoría
    materiales = Material.objects.filter(categoria=categoria)
    return render(request, 'inventario/categoria.html', {
        'categoria': categoria,
        'materiales': materiales
    })

@login_required
def editar_inventario(request):
    # Usar Case y When para ordenar como en la vista inventario
    from django.db.models import Case, When, Value, IntegerField
    
    materiales = Material.objects.all().order_by('categoria', 'nombre')
    
    categoria_id = request.GET.get('categoria')
    search_query = request.GET.get('search', '')
    categorias = Categoria.objects.all()

    if categoria_id:
        materiales = materiales.filter(categoria_id=categoria_id)
    
    if search_query:
        materiales = materiales.filter(
            Q(nombre__icontains=search_query) |
            Q(codigo__icontains=search_query)
        )

    context = {
        'materiales': materiales,
        'categorias': categorias,
        'categoria_seleccionada': categoria_id,
        'search_query': search_query
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'inventario/editar_inventario.html', context)
    return render(request, 'inventario/editar_inventario.html', context)

@login_required
def editar_material(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    
    if request.method == 'POST':
        try:
            # Validar campos obligatorios primero
            if not request.POST.get('nombre'):
                raise ValueError("El nombre es obligatorio")

            # Actualizar campos básicos que no son archivos
            material.nombre = request.POST['nombre']
            material.categoria_id = int(request.POST['categoria'])
            
            # Manejar código
            codigo = request.POST.get('codigo', '').strip() or None
            if codigo != material.codigo:
                if codigo:
                    existing = Material.objects.filter(codigo=codigo).exclude(id=material_id).exists()
                    if existing:
                        raise ValueError(f"Ya existe un material con el código {codigo}")
                material.codigo = codigo

            # Manejar precio - permitir vacío
            precio_str = request.POST.get('precio', '').strip()
            if precio_str:
                try:
                    precio = float(precio_str)
                    if precio < 0:
                        raise ValueError("El precio no puede ser negativo")
                    material.precio = precio
                except ValueError:
                    raise ValueError("El precio debe ser un número válido")

            # Manejar comisión - permitir vacío
            comision_str = request.POST.get('comision', '').strip()
            if comision_str:
                try:
                    comision = float(comision_str)
                    if comision < 0:
                        raise ValueError("La comisión no puede ser negativa")
                    material.comision = comision
                except ValueError:
                    raise ValueError("La comisión debe ser un número válido")

            # Manejar cantidad
            try:
                cantidad = int(request.POST.get('cantidad', 0))
                if cantidad < 0:
                    raise ValueError("La cantidad no puede ser negativa")
                material.cantidad = cantidad
            except ValueError:
                raise ValueError("La cantidad debe ser un número entero")

            # Manejar archivos SOLO si se proporcionan nuevos archivos
            if 'imagen' in request.FILES:
                nueva_imagen = request.FILES.get('imagen')
                if nueva_imagen and nueva_imagen.size > 0:
                    # Solo eliminar y actualizar si realmente hay una nueva imagen
                    if material.imagen:
                        old_imagen = material.imagen
                        material.imagen = nueva_imagen
                        old_imagen.delete(save=False)
                    else:
                        material.imagen = nueva_imagen

            # Manejar la ficha técnica
            nueva_ficha = request.FILES.get('ficha_tecnica')
            if nueva_ficha and nueva_ficha.size > 0:
                # Si ya existe una ficha técnica, la eliminamos
                if material.ficha_tecnica:
                    old_ficha = material.ficha_tecnica
                    material.ficha_tecnica = nueva_ficha
                    old_ficha.delete(save=False)
                else:
                    material.ficha_tecnica = nueva_ficha

            if 'imagenes_secundarias' in request.FILES:
                imagenes_nuevas = request.FILES.getlist('imagenes_secundarias')
                if any(img.size > 0 for img in imagenes_nuevas):
                    for imagen in imagenes_nuevas:
                        if imagen.size > 0:  # Solo procesar imágenes que realmente se subieron
                            MaterialImagen.objects.create(
                                material=material,
                                imagen=imagen
                            )

            # Manejar estado de oferta y precio de oferta
            material.en_oferta = request.POST.get('en_oferta') == 'on'
            
            # Solo procesar precio_oferta si está en oferta
            if material.en_oferta:
                precio_oferta_str = request.POST.get('precio_oferta', '').strip()
                if precio_oferta_str:
                    try:
                        precio_oferta = float(precio_oferta_str)
                        if precio_oferta < 0:
                            raise ValueError("El precio de oferta no puede ser negativo")
                        if precio_oferta >= material.precio:
                            raise ValueError("El precio de oferta debe ser menor al precio regular")
                        material.precio_oferta = precio_oferta
                    except ValueError as e:
                        raise ValueError("El precio de oferta debe ser un número válido y menor al precio regular")
                else:
                    raise ValueError("Debe especificar un precio de oferta")
            else:
                material.precio_oferta = None

            material.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': f'Material {material.nombre} actualizado correctamente'
                })
            
            messages.success(request, f'Material {material.nombre} actualizado correctamente')
            
        except ValueError as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
            messages.error(request, f'Error de validación: {str(e)}')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error al actualizar el material: {str(e)}'
                })
            messages.error(request, f'Error al actualizar el material: {str(e)}')
            
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'error',
            'message': 'Método no permitido'
        })
    return redirect('editar_inventario')

@login_required
def crear_material(request):
    if request.method == 'POST':
        try:
            # Crear nuevo material
            material = Material.objects.create(
                nombre=request.POST['nombre'],
                codigo=request.POST.get('codigo'),
                precio=float(request.POST['precio']),
                comision=float(request.POST.get('comision', 0)),
                cantidad=int(request.POST['cantidad']),
                categoria_id=int(request.POST['categoria']),
                imagen=request.FILES['imagen']
            )
            
            # Procesar imágenes secundarias
            for imagen in request.FILES.getlist('imagenes_secundarias'):
                MaterialImagen.objects.create(
                    material=material,
                    imagen=imagen
                )
            
            # Procesar ficha técnica
            if 'ficha_tecnica' in request.FILES:
                material.ficha_tecnica = request.FILES['ficha_tecnica']
                material.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Material creado correctamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
        
        return redirect('editar_inventario')

@login_required
def eliminar_imagen(request, imagen_id):
    if request.method == 'POST':
        try:
            imagen = MaterialImagen.objects.get(id=imagen_id)
            imagen.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

@login_required
def eliminar_material(request, material_id):
    if not request.user.is_superuser:
        return JsonResponse({
            'status': 'error',
            'message': 'No tienes permisos para realizar esta acción'
        }, status=403)

    try:
        material = get_object_or_404(Material, id=material_id)
        material.soft_delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Material eliminado correctamente'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error al eliminar el material: {str(e)}'
        }, status=500)

def pedidos_pendientes(request, material_id):
    pedidos = PedidoDetalle.objects.filter(
        material_id=material_id,
        pedido__estado='pendiente'
    ).select_related('pedido', 'pedido__user').values(
        'pedido_id',
        'cantidad',
        'pedido__created_at',
        'pedido__user__first_name',
        'pedido__user__last_name',
        'pedido__user__username'
    )

    data = {
        'pedidos': [
            {
                'id': p['pedido_id'],
                'cantidad': p['cantidad'],
                'fecha': p['pedido__created_at'].strftime('%d/%m/%Y %H:%M'),
                'gestor': f"{p['pedido__user__first_name']} {p['pedido__user__last_name']}" 
                         or p['pedido__user__username']  # Fallback al username si no hay nombre completo
            } for p in pedidos
        ]
    }
    
    return JsonResponse(data)

@require_POST
def toggle_destacado(request, material_id):
    try:
        material = Material.objects.get(id=material_id)
        material.destacado = not material.destacado
        material.save()
        return JsonResponse({
            'status': 'success',
            'destacado': material.destacado
        })
    except Material.DoesNotExist as error:
        return JsonResponse({
            'status': 'error',
            'message': str(error)
        })

@require_POST
def toggle_activo(request, material_id):
    try:
        material = Material.objects.get(id=material_id)
        material.activo = not material.activo
        material.save()
        return JsonResponse({
            'status': 'success',
            'activo': material.activo
        })
    except Material.DoesNotExist as error:
        return JsonResponse({
            'status': 'error',
            'message': str(error)
        })

def material_imagenes(request, material_id):
    """Vista para obtener las imágenes de un material"""
    material = get_object_or_404(Material, id=material_id)
    
    # Preparar datos para la respuesta
    data = {
        'imagen_principal': material.imagen.url if material.imagen else None,
        'imagenes_secundarias': []
    }
    
    # Obtener imágenes secundarias si existen
    imagenes_secundarias = MaterialImagen.objects.filter(material=material)
    if imagenes_secundarias.exists():
        data['imagenes_secundarias'] = [
            {'url': imagen.imagen.url} 
            for imagen in imagenes_secundarias
        ]
    
    return JsonResponse(data)

class MaterialListView(ListView):
    model = Material
    template_name = 'inventario/material_list.html'
    context_object_name = 'materiales'

    def get_queryset(self):
        queryset = super().get_queryset()
        for material in queryset:
            material.cantidad_en_pedidos = material.get_cantidad_en_pedidos()
        return queryset

@user_passes_test(lambda u: u.is_superuser)
def crear_categoria(request):
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre')
            categoria = Categoria.objects.create(nombre=nombre)
            return JsonResponse({
                'status': 'success',
                'message': 'Categoría creada exitosamente',
                'id': categoria.id,
                'nombre': categoria.nombre
            })
        except Exception as error:
            return JsonResponse({
                'status': 'error',
                'message': str(error)
            }, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@require_POST
def toggle_oferta(request, material_id):
    try:
        material = Material.objects.get(id=material_id)
        material.en_oferta = not material.en_oferta
        
        # Si se activa la oferta y no hay precio de oferta, establecer uno por defecto
        if material.en_oferta and not material.precio_oferta:
            material.precio_oferta = material.precio * 1  # 10% de descuento por defecto
        # Si se quita la oferta, limpiar el precio de oferta
        elif not material.en_oferta:
            material.precio_oferta = None
        
        material.save()
        return JsonResponse({
            'status': 'success',
            'en_oferta': material.en_oferta,
            'precio_oferta': material.precio_oferta,
            'descuento': material.descuento_porcentaje
        })
    except Material.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Material no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_POST
@user_passes_test(lambda u: u.is_superuser)
def editar_categoria(request, categoria_id):
    try:
        categoria = get_object_or_404(Categoria, id=categoria_id)
        nombre = request.POST.get('nombre')
        
        # Validar que el nombre no esté vacío
        if not nombre:
            return JsonResponse({
                'status': 'error',
                'message': 'El nombre es requerido'
            }, status=400)
        
        # Validar que el nombre no exista para otra categoría
        if Categoria.objects.filter(nombre=nombre).exclude(id=categoria_id).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Ya existe una categoría con ese nombre'
            }, status=400)
        
        categoria.nombre = nombre
        categoria.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Categoría actualizada exitosamente',
            'id': categoria.id,
            'nombre': categoria.nombre
        })
    except Exception as error:
        return JsonResponse({
            'status': 'error',
            'message': str(error)
        }, status=500)

@require_POST
@user_passes_test(lambda u: u.is_superuser)
def eliminar_categoria(request, categoria_id):
    try:
        categoria = get_object_or_404(Categoria, id=categoria_id)
        
        # Verificar si hay materiales usando esta categoría
        materiales_count = Material.objects.filter(categoria=categoria).count()
        
        if materiales_count > 0:
            # Si hay confirmación para eliminar todo
            if request.POST.get('confirm_delete') == 'true':
                # Eliminar los materiales asociados primero
                Material.objects.filter(categoria=categoria).delete()
                # Luego eliminar la categoría
                categoria.delete()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Categoría y materiales asociados eliminados exitosamente'
                })
            else:
                # Si no hay confirmación, devolver información sobre los materiales
                return JsonResponse({
                    'status': 'warning',
                    'message': f'Esta categoría tiene {materiales_count} materiales asociados',
                    'requires_confirmation': True,
                    'materiales_count': materiales_count
                })
        
        # Si no hay materiales, eliminar directamente
        categoria.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Categoría eliminada exitosamente'
        })
    except Exception as error:
        return JsonResponse({
            'status': 'error',
            'message': str(error)
        }, status=500)