from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from io import BytesIO
import logging
from django.contrib.auth.models import User
from django.urls import reverse
from clientes.models import Cliente
from django.db.models import Q, Sum, F
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
import os
from pathlib import Path
from background_task import background
from django.utils import timezone

logger = logging.getLogger(__name__)

from carro.carro import Carro
from inventario.models import Material
from pedidos.models import Pedido, PedidoDetalle, ConfiguracionPedidos
from .forms import PedidoForm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

@background(schedule=2*60)  # Tiempo para cancelar pedidos
def cancelar_pedido_no_efectuado(pedido_id):
    try:
        pedido = Pedido.objects.get(id=pedido_id)
        # Verificar si el pedido existe y está pendiente
        if pedido.estado == 'pendiente':
            with transaction.atomic():
                # Restaurar stock
                detalles = PedidoDetalle.objects.filter(pedido=pedido)
                for detalle in detalles:
                    material = detalle.material
                    material.actualizar_stock(detalle.cantidad)

                # Cambiar estado a cancelado
                pedido.estado = 'cancelado'
                pedido.save()

            logger.info(f"Pedido {pedido_id} cancelado automáticamente después de 20 segundos")
    except Pedido.DoesNotExist:
        logger.error(f"Pedido {pedido_id} no encontrado")
    except Exception as e:
        logger.error(f"Error al cancelar pedido {pedido_id}: {str(e)}")

@login_required(login_url='/autenticacion/logear')
def prosesar_pedido(request):
    if request.method == 'POST':
        form = PedidoForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Check if client exists
                    carnet = form.cleaned_data['carnet_identidad_cliente']
                    cliente = Cliente.objects.filter(carnet_identidad=carnet).first()

                    if (cliente):
                        # Check if the authenticated user owns this client
                        if cliente.user != request.user:
                            messages.error(request, "No puede usar este cliente ya que fue registrado por otro gestor.")
                            return redirect('pedidos:prosesar_pedido')
                    else:
                        # Create new client if doesn't exist
                        cliente = Cliente.objects.create(
                            user=request.user,
                            nombre=form.cleaned_data['nombre_cliente'],
                            apellidos=form.cleaned_data['apellidos_cliente'],
                            carnet_identidad=carnet,
                            telefono=form.cleaned_data['telefono_cliente']
                        )

                    carro = Carro(request)

                    # Verificar stock disponible antes de crear el pedido
                    for key, value in carro.carro.items():
                        material = Material.objects.get(id=key)
                        cantidad = int(value['cantidad'])
                        if material.cantidad < cantidad:
                            raise ValueError(f"No hay suficiente stock de {material.nombre}")

                    # Crear pedido
                    pedido = Pedido.objects.create(
                        user=request.user,
                        cliente=cliente,
                        transportista=form.cleaned_data.get('transportista', None),
                        estado='pendiente'
                    )

                    # Crear detalles y actualizar stock
                    detalles = []
                    total_pedido = 0

                    for key, value in carro.carro.items():
                        material = Material.objects.get(id=key)
                        cantidad = int(value['cantidad'])

                        # Actualizar stock
                        if not material.actualizar_stock(-cantidad):
                            raise ValueError(f"Error al actualizar stock de {material.nombre}")

                        # Usar el precio que estaba en el carro
                        precio_unitario = float(value['precio_unitario'])
                        subtotal = precio_unitario * cantidad

                        detalles.append(PedidoDetalle(
                            pedido=pedido,
                            material=material,
                            cantidad=cantidad,
                            precio_unitario=precio_unitario,  # Guardar el precio unitario usado
                            en_oferta=value.get('en_oferta', False),  # Guardar si estaba en oferta
                            precio_regular=float(value.get('precio_regular', precio_unitario)),  # Guardar precio regular
                            total=subtotal,
                            user=request.user
                        ))
                        total_pedido += subtotal

                    pedido.total = total_pedido
                    pedido.save()
                    PedidoDetalle.objects.bulk_create(detalles)
                    carro.limpiar_carro()

                    # Programar la cancelación automática
                    cancelar_pedido_no_efectuado(pedido.id)

                    messages.success(request, 'Pedido creado exitosamente')
                    return redirect('inventario')  # Redirigir al inventario

            except Exception as e:
                messages.error(request, f'Error al crear el pedido: {str(e)}')
    else:
        form = PedidoForm()

    return render(request, 'pedidos/crear_pedido.html', {
        'form': form,
        'carro': request.session.get('carro', {})
    })

@login_required(login_url='/autenticacion/logear')
def lista_pedidos(request):
    # Consulta base
    if request.user.is_superuser:
        pedidos = Pedido.objects.select_related('cliente', 'user').all()
        # Para admin, mostrar todos los clientes
        clientes = Cliente.objects.values('id', 'nombre', 'apellidos').distinct()
    else:
        pedidos = Pedido.objects.select_related('cliente', 'user').filter(user=request.user)
        # Para gestor normal, solo mostrar sus clientes
        clientes = Cliente.objects.filter(pedido__user=request.user).distinct().values('id', 'nombre', 'apellidos')

    # Filtrar por cliente
    if cliente_id := request.GET.get('cliente'):
        pedidos = pedidos.filter(cliente_id=cliente_id)

    # Filtrar por gestor (solo para admin)
    if request.user.is_superuser and (gestor_id := request.GET.get('gestor')):
        pedidos = pedidos.filter(user_id=gestor_id)

    # Filtrar por material
    if material_id := request.GET.get('material'):
        pedidos = pedidos.filter(pedidodetalle__material_id=material_id).distinct()

    # Filtrar por estado
    if estado := request.GET.get('estado'):
        if estado == 'reactivado':
            pedidos = pedidos.filter(reactivaciones__isnull=False).distinct()
        elif estado == 'reactivacion':
            pedidos = pedidos.filter(pedido_original__isnull=False)
        else:
            pedidos = pedidos.filter(estado=estado)

    # Filtrar por fechas
    if fecha_desde := request.GET.get('fecha_desde'):
        pedidos = pedidos.filter(created_at__date__gte=fecha_desde)
    if fecha_hasta := request.GET.get('fecha_hasta'):
        pedidos = pedidos.filter(created_at__date__lte=fecha_hasta)

    # Definir estados disponibles
    estados = [
        {'value': 'pendiente', 'label': 'Pendiente'},
        {'value': 'efectuado', 'label': 'Efectuado'},
        {'value': 'cancelado', 'label': 'Cancelado'},
        {'value': 'reactivacion', 'label': 'Reactivación'},
        {'value': 'reactivado', 'label': 'Reactivados'}
    ]

    # Ordenar pedidos por ID descendente
    pedidos = pedidos.distinct().order_by('-id')

    context = {
        'pedidos': pedidos,
        'clientes': clientes,
        'gestores': User.objects.filter(is_active=True).values('id', 'first_name', 'last_name', 'username').distinct() if request.user.is_superuser else None,
        'materiales': Material.objects.filter(activo=True).order_by('nombre'),
        'estados': estados,
        'filtros_activos': {
            'cliente': request.GET.get('cliente'),
            'gestor': request.GET.get('gestor'),
            'material': request.GET.get('material'),
            'estado': request.GET.get('estado'),
            'fecha_desde': request.GET.get('fecha_desde'),
            'fecha_hasta': request.GET.get('fecha_hasta')
        }
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'pedidos/includes/tabla_pedidos.html', context)
    return render(request, 'pedidos/lista_pedidos.html', context)

@login_required(login_url='/autenticacion/logear')
def detalle_pedido(request, pedido_id):
    # Obtener el pedido o devolver 404 si no existe
    if request.user.is_superuser:
        pedido = get_object_or_404(Pedido, id=pedido_id)
    else:
        pedido = get_object_or_404(Pedido, id=pedido_id, user=request.user)

    context = {
        'pedido': pedido,
        'detalles': pedido.pedidodetalle_set.all().select_related('material'),
        'cliente': pedido.cliente  # Now referencing cliente through relationship
    }

    return render(request, 'pedidos/detalle_pedido.html', context)

@login_required(login_url='/autenticacion/logear')
def eliminar_pedido(request, pedido_id):
    try:
        # Permitir al admin acceder a cualquier pedido
        pedido = get_object_or_404(Pedido, id=pedido_id) if request.user.is_superuser else get_object_or_404(Pedido, id=pedido_id, user=request.user)

        if pedido.estado == 'efectuado':
            return JsonResponse({
                'status': 'error',
                'message': "No se puede eliminar un pedido que ya ha sido efectuado"
            })

        with transaction.atomic():
            # Restaurar stock si el pedido estaba pendiente
            if pedido.estado == 'pendiente':
                for detalle in pedido.pedidodetalle_set.all():
                    detalle.material.actualizar_stock(detalle.cantidad)

            pedido.delete()
            return JsonResponse({
                'status': 'success',
                'message': "Pedido eliminado correctamente"
            })

    except Pedido.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': "Pedido no encontrado"
        }, status=404)
    except PermissionError:
        return JsonResponse({
            'status': 'error',
            'message': "No tienes permiso para eliminar este pedido"
        }, status=403)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f"Error al eliminar el pedido: {str(e)}"
        }, status=500)

@login_required(login_url='/autenticacion/logear')
def editar_pedido(request, pedido_id):
    # Verificar permisos y obtener pedido
    pedido = get_object_or_404(Pedido, id=pedido_id) if request.user.is_superuser else get_object_or_404(Pedido, id=pedido_id, user=request.user)

    # Verificar que el pedido esté pendiente
    if pedido.estado != 'pendiente':
        messages.error(request, "Solo se pueden editar pedidos pendientes")
        return redirect('pedidos:lista_pedidos')

    if request.method == 'POST':
        try:
            form = PedidoForm(request.POST, instance=pedido)
            if form.is_valid():
                # Obtener el cliente directamente del POST
                cliente_id = request.POST.get('cliente')
                if not cliente_id:
                    raise ValueError("El cliente es requerido")

                cliente = Cliente.objects.get(id=cliente_id)

                # Verificar permisos para el cliente seleccionado
                if not request.user.is_superuser and cliente.user != request.user:
                    messages.error(request, "No puede usar un cliente registrado por otro gestor")
                    return redirect('pedidos:editar_pedido', pedido_id=pedido.id)

                with transaction.atomic():
                    pedido = form.save(commit=False)
                    pedido.cliente = cliente

                    # Solo actualizar el usuario si es admin
                    if request.user.is_superuser:
                        user_id = request.POST.get('user')
                        if user_id:
                            pedido.user = User.objects.get(id=user_id)

                    # Actualizar transportista
                    pedido.transportista = form.cleaned_data.get('transportista')
                    pedido.save()

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'status': 'success',
                            'message': 'Pedido actualizado correctamente',
                            'redirect_url': reverse('pedidos:detalle_pedido', args=[pedido.id])
                        })

                    messages.success(request, "Pedido actualizado correctamente")
                    return redirect('pedidos:detalle_pedido', pedido_id=pedido.id)
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Error en el formulario',
                        'errors': form.errors
                    })
                messages.error(request, "Por favor corrija los errores en el formulario")
        except Cliente.DoesNotExist:
            messages.error(request, "El cliente seleccionado no existe")
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
            messages.error(request, f"Error al actualizar el pedido: {str(e)}")
    else:
        form = PedidoForm(instance=pedido, initial={
            'cliente': pedido.cliente,
            'transportista': pedido.transportista,
            'user': pedido.user if request.user.is_superuser else None
        })

    context = {
        'form': form,
        'pedido': pedido,
        'clientes': Cliente.objects.all() if request.user.is_superuser else Cliente.objects.filter(user=request.user)
    }
    return render(request, 'pedidos/editar_pedido.html', context)
    # Verificar permisos y obtener pedido
    pedido = get_object_or_404(Pedido, id=pedido_id) if request.user.is_superuser else get_object_or_404(Pedido, id=pedido_id, user=request.user)

    # Verificar que el pedido esté pendiente
    if pedido.estado != 'pendiente':
        messages.error(request, "Solo se pueden editar pedidos pendientes")
        return redirect('pedidos:lista_pedidos')

    if request.method == 'POST':
        try:
            form = PedidoForm(request.POST, instance=pedido)
            if form.is_valid():
                cliente = form.cleaned_data.get('cliente')

                # Verificar permisos para el cliente seleccionado
                if not request.user.is_superuser and cliente.user != request.user:
                    messages.error(request, "No puede usar un cliente registrado por otro gestor")
                    return redirect('pedidos:editar_pedido', pedido_id=pedido.id)

                with transaction.atomic():
                    pedido = form.save(commit=False)

                    # Solo actualizar el usuario si es admin
                    if request.user.is_superuser:
                        pedido.user = form.cleaned_data.get('user', request.user)

                    # Actualizar otros campos
                    pedido.cliente = cliente
                    pedido.transportista = form.cleaned_data.get('transportista')
                    pedido.save()

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'status': 'success',
                            'message': 'Pedido actualizado correctamente',
                            'redirect_url': reverse('pedidos:detalle_pedido', args=[pedido.id])
                        })

                    messages.success(request, "Pedido actualizado correctamente")
                    return redirect('pedidos:detalle_pedido', pedido_id=pedido.id)
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Error en el formulario',
                        'errors': form.errors
                    })
                messages.error(request, "Por favor corrija los errores en el formulario")
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
            messages.error(request, f"Error al actualizar el pedido: {str(e)}")
    else:
        # Para el formulario inicial, incluir campos adicionales si es admin
        initial_data = {
            'cliente': pedido.cliente,
            'transportista': pedido.transportista
        }
        if request.user.is_superuser:
            initial_data['user'] = pedido.user

        form = PedidoForm(instance=pedido, initial=initial_data)

    return render(request, 'pedidos/editar_pedido.html', {
        'form': form,
        'pedido': pedido
    })

@login_required(login_url='/autenticacion/logear')
def editar_detalle(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id) if request.user.is_superuser else get_object_or_404(Pedido, id=pedido_id, user=request.user)
    detalles_antiguos = {detalle.material_id: detalle.cantidad for detalle in PedidoDetalle.objects.filter(pedido=pedido)}

    if request.method == 'POST':
        try:
            articulos_ids = request.POST.getlist('articulo[]')
            cantidades = request.POST.getlist('cantidad[]')
            en_ofertas = request.POST.getlist('en_oferta[]')  # Obtener estados de oferta
            precios_regulares = request.POST.getlist('precio_regular[]')  # Obtener precios regulares
            precios_unitarios = request.POST.getlist('precio_unitario[]')  # Obtener precios unitarios

            # 1. Devolver el stock de los artículos anteriores
            for material_id, cantidad_antigua in detalles_antiguos.items():
                material = Material.objects.get(id=material_id)
                material.actualizar_stock(cantidad_antigua)

            # 2. Procesar las nuevas cantidades
            nuevos_detalles = []
            total_pedido = 0

            for i, (articulo_id, cantidad) in enumerate(zip(articulos_ids, cantidades)):
                if articulo_id and cantidad and float(cantidad) > 0:
                    material = Material.objects.get(id=articulo_id)
                    nueva_cantidad = float(cantidad)

                    # Verificar stock disponible
                    if (material.cantidad < nueva_cantidad):
                        # Restaurar estado original si falla
                        for mat_id, cant in detalles_antiguos.items():
                            mat = Material.objects.get(id=mat_id)
                            mat.actualizar_stock(-cant)
                        raise Exception(f"No hay suficiente stock de {material.nombre}")

                    # Descontar nuevo stock
                    if not material.actualizar_stock(-nueva_cantidad):
                        raise Exception(f"Error al actualizar stock de {material.nombre}")

                    # Crear nuevo detalle con la información de oferta
                    precio_unitario = float(precios_unitarios[i])
                    en_oferta = en_ofertas[i].lower() == 'true'
                    precio_regular = float(precios_regulares[i])
                    subtotal = precio_unitario * nueva_cantidad

                    detalle = PedidoDetalle(
                        pedido=pedido,
                        material=material,
                        cantidad=nueva_cantidad,
                        user=request.user,
                        precio_unitario=precio_unitario,
                        en_oferta=en_oferta,
                        precio_regular=precio_regular,
                        total=subtotal
                    )

                    nuevos_detalles.append(detalle)
                    total_pedido += subtotal

            # 3. Actualizar la base de datos
            PedidoDetalle.objects.filter(pedido=pedido).delete()
            PedidoDetalle.objects.bulk_create(nuevos_detalles)

            pedido.total = total_pedido
            pedido.save()

            messages.success(request, "Detalles del pedido actualizados correctamente")
            return redirect('pedidos:detalle_pedido', pedido_id=pedido.id)

        except Exception as e:
            messages.error(request, f"Error al actualizar el pedido: {str(e)}")

    return render(request, 'pedidos/editar_detalle.html', {
        'pedido': pedido,
        'detalles': PedidoDetalle.objects.filter(pedido=pedido),
        'articulos': Material.objects.all()
    })

@login_required(login_url='/autenticacion/logear')
def efectuar_pedido(request, pedido_id):
    try:
        # Permitir al admin acceder a cualquier pedido
        pedido = get_object_or_404(Pedido, id=pedido_id) if request.user.is_superuser else get_object_or_404(Pedido, id=pedido_id, user=request.user)

        if not request.user.is_superuser:
            return JsonResponse({
                'status': 'error',
                'message': 'Solo los administradores pueden efectuar pedidos'
            }, status=403)

        if pedido.estado != 'pendiente':
            return JsonResponse({
                'status': 'warning',
                'message': 'Solo se pueden efectuar pedidos pendientes'
            })

        with transaction.atomic():
            # No necesitamos actualizar el stock porque ya se actualizó cuando se creó el pedido
            pedido.estado = 'efectuado'
            pedido.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Pedido efectuado correctamente',
                'refresh': True
            })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error al efectuar el pedido: {str(e)}'
        }, status=500)

@login_required(login_url='/autenticacion/logear')
def cancelar_pedido(request, pedido_id):
    try:
        # Permitir al admin acceder a cualquier pedido
        pedido = get_object_or_404(Pedido, id=pedido_id) if request.user.is_superuser else get_object_or_404(Pedido, id=pedido_id, user=request.user)

        if pedido.estado != 'pendiente':
            return JsonResponse({
                'status': 'warning',
                'message': 'Solo se pueden cancelar pedidos pendientes'
            })

        with transaction.atomic():
            # Devolver stock al inventario
            for detalle in pedido.pedidodetalle_set.all():
                detalle.material.actualizar_stock(detalle.cantidad)

            # Actualizar estado del pedido
            pedido.estado = 'cancelado'
            pedido.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Pedido cancelado correctamente',
                'refresh': True
            })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error al cancelar el pedido: {str(e)}'
        }, status=500)

@login_required(login_url='/autenticacion/logear')
def reactivar_pedido(request, pedido_id):
    try:
        pedido_original = get_object_or_404(Pedido, id=pedido_id)
        if pedido_original.estado != 'cancelado':
            return JsonResponse({
                'status': 'warning',
                'message': 'Solo se pueden reactivar pedidos cancelados'
            })

        with transaction.atomic():
            # Crear nuevo pedido con los mismos datos
            nuevo_pedido = Pedido.objects.create(
                user=pedido_original.user,
                cliente=pedido_original.cliente,
                transportista=pedido_original.transportista,
                estado='pendiente',
                pedido_original=pedido_original  # Agregar referencia al pedido original
            )

            total_pedido = 0
            detalles_nuevos = []

            # Copiar los detalles del pedido original usando precios actuales
            for detalle in pedido_original.pedidodetalle_set.all():
                # Verificar stock disponible
                if detalle.material.cantidad < detalle.cantidad:
                    raise ValueError(f'No hay suficiente stock de {detalle.material.nombre}')

                # Obtener el precio actual del material
                precio_actual = detalle.material.precio_actual
                subtotal = precio_actual * detalle.cantidad

                # Crear nuevo detalle con precios actualizados
                detalle_nuevo = PedidoDetalle(
                    pedido=nuevo_pedido,
                    material=detalle.material,
                    cantidad=detalle.cantidad,
                    user=detalle.user,
                    precio_unitario=precio_actual,
                    en_oferta=detalle.material.en_oferta,
                    precio_regular=detalle.material.precio,
                    total=subtotal
                )

                detalles_nuevos.append(detalle_nuevo)
                total_pedido += subtotal

                # Actualizar stock
                if not detalle.material.actualizar_stock(-detalle.cantidad):
                    raise ValueError(f'Error al actualizar stock de {detalle.material.nombre}')

            # Guardar detalles y actualizar total
            PedidoDetalle.objects.bulk_create(detalles_nuevos)
            nuevo_pedido.total = total_pedido
            nuevo_pedido.save()

            # Programar la cancelación automática del pedido reactivado
            cancelar_pedido_no_efectuado(nuevo_pedido.id)

            return JsonResponse({
                'status': 'success',
                'message': 'Pedido reactivado como nuevo pedido con precios actualizados',
                'redirect_url': f'/pedidos/detalle/{nuevo_pedido.id}'
            })

    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error al reactivar el pedido: {str(e)}'
        }, status=500)

def generar_factura(request, pedido_id):
    try:
        logger.info(f"Generando factura para el pedido {pedido_id}")
        pedido = get_object_or_404(Pedido, id=pedido_id)
        detalles = PedidoDetalle.objects.filter(pedido=pedido)

        # Crear un buffer para el PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Buscar el logo en más ubicaciones posibles
        possible_logo_paths = [
            os.path.join(settings.STATIC_ROOT, 'img', 'logo.jpg'),
            os.path.join(settings.STATIC_ROOT, 'img', 'logo.png'),
            os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.jpg'),
            os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png'),
            os.path.join(settings.BASE_DIR, 'staticfiles', 'img', 'logo.jpg'),
            os.path.join(settings.BASE_DIR, 'staticfiles', 'img', 'logo.png'),
            # Buscar en la carpeta media también
            os.path.join(settings.MEDIA_ROOT, 'img', 'logo.jpg'),
            os.path.join(settings.MEDIA_ROOT, 'img', 'logo.png'),
        ]

        # Intentar encontrar el logo e imprimir información de debug
        logo_path = None
        for path in possible_logo_paths:
            if os.path.exists(path):
                logo_path = path
                logger.info(f"Logo encontrado en: {path}")
                break
            else:
                logger.debug(f"Logo no encontrado en: {path}")

        if logo_path:
            try:
                # Definir tamaño del logo aumentado un 40%
                logo_width = 252  # 180 * 1.4
                logo_height = 126 # 90 * 1.4
                # Posicionar en esquina superior derecha con un poco más de margen
                x_pos = width - logo_width - 40
                y_pos = height - logo_height - 20

                # Intentar dibujar el logo con manejo de errores
                p.drawImage(logo_path, x_pos, y_pos,
                           width=logo_width, height=logo_height,
                           preserveAspectRatio=True,
                           mask='auto')  # Añadido mask='auto' para mejor manejo de transparencias
                logger.info(f"Logo dibujado exitosamente desde: {logo_path}")
            except Exception as e:
                logger.error(f"Error al dibujar el logo: {str(e)}")
        else:
            logger.warning("No se encontró el archivo del logo en ninguna ubicación")

        # Encabezado
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "FACTURA")
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, f"Código: {pedido.codigo_unico}")
        p.drawString(50, height - 90, f"Fecha: {pedido.created_at.strftime('%d/%m/%Y %H:%M:%S')}")
        p.drawString(50, height - 110, f"Gestor: {pedido.user.get_full_name()}")

        # Datos del cliente
        p.drawString(50, height - 140, "Cliente:")
        p.drawString(70, height - 160, f"Nombre: {pedido.cliente.get_full_name()}")
        p.drawString(70, height - 180, f"CI: {pedido.cliente.carnet_identidad}")
        p.drawString(70, height - 200, f"Teléfono: {pedido.cliente.telefono}")
        p.drawString(70, height - 220, f"Transportista: {pedido.transportista or 'No especificado'}")

        # Tabla de productos
        y = height - 260
        p.drawString(50, y, "Producto")
        p.drawString(200, y, "Código")
        p.drawString(300, y, "Cantidad")
        p.drawString(380, y, "Precio Unit.")
        p.drawString(460, y, "Total")

        y -= 20
        for detalle in detalles:
            nombre_producto = f"(*) {detalle.material.nombre}" if detalle.en_oferta else detalle.material.nombre
            p.drawString(50, y, nombre_producto)
            p.drawString(200, y, str(detalle.material.codigo or 'N/A'))
            p.drawString(300, y, str(detalle.cantidad))

            if detalle.en_oferta:
                # Primero dibujamos el precio de oferta en rojo
                p.setFont("Helvetica", 12)
                p.setFillColorRGB(1, 0, 0)  # Rojo
                p.drawString(380, y, f"${detalle.precio_unitario:.2f}")

                # Luego dibujamos el precio regular tachado arriba
                p.setFont("Helvetica", 8)  # Más pequeño
                p.setFillColorRGB(0.5, 0.5, 0.5)  # Gris
                precio_str = f"${detalle.precio_regular:.2f}"
                precio_width = p.stringWidth(precio_str, "Helvetica", 8)

                # Dibujar precio regular
                p.drawString(380, y + 10, precio_str)
                # Dibujar línea de tachado
                p.line(380, y + 12, 380 + precio_width, y + 12)

                # Volver a negro para el resto del texto
                p.setFont("Helvetica", 12)
                p.setFillColorRGB(0, 0, 0)
            else:
                p.drawString(380, y, f"${detalle.precio_unitario:.2f}")

            p.drawString(460, y, f"${float(detalle.total):.2f}")
            y -= 20

        # Total
        p.line(50, y-10, 500, y-10)
        p.drawString(380, y-30, "Total:")
        p.drawString(460, y-30, f"${float(pedido.total):.2f}")

        p.showPage()
        p.save()

        # Obtener el valor del buffer y crear la respuesta HTTP
        pdf = buffer.getvalue()
        buffer.close()

        # Crear respuesta HTTP con el PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="factura_{pedido.codigo_unico}.pdf"'
        response.write(pdf)

        return response

    except Exception as e:
        logger.error(f"Error generando factura para pedido {pedido_id}: {str(e)}")
        return HttpResponse("Error generando la factura", status=500)

def generar_oferta(request, pedido_id):
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        detalles = PedidoDetalle.objects.filter(pedido=pedido)

        # Crear un buffer para el PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Buscar el logo en más ubicaciones posibles
        possible_logo_paths = [
            os.path.join(settings.STATIC_ROOT, 'img', 'logo.jpg'),
            os.path.join(settings.STATIC_ROOT, 'img', 'logo.png'),
            os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.jpg'),
            os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png'),
            os.path.join(settings.BASE_DIR, 'staticfiles', 'img', 'logo.jpg'),
            os.path.join(settings.BASE_DIR, 'staticfiles', 'img', 'logo.png'),
            # Buscar en la carpeta media también
            os.path.join(settings.MEDIA_ROOT, 'img', 'logo.jpg'),
            os.path.join(settings.MEDIA_ROOT, 'img', 'logo.png'),
        ]

        # Intentar encontrar el logo e imprimir información de debug
        logo_path = None
        for path in possible_logo_paths:
            if os.path.exists(path):
                logo_path = path
                logger.info(f"Logo encontrado en: {path}")
                break
            else:
                logger.debug(f"Logo no encontrado en: {path}")

        if logo_path:
            try:
                # Definir tamaño del logo aumentado un 40%
                logo_width = 252  # 180 * 1.4
                logo_height = 126 # 90 * 1.4
                # Posicionar en esquina superior derecha con un poco más de margen
                x_pos = width - logo_width - 40
                y_pos = height - logo_height - 20

                # Intentar dibujar el logo con manejo de errores
                p.drawImage(logo_path, x_pos, y_pos,
                           width=logo_width, height=logo_height,
                           preserveAspectRatio=True,
                           mask='auto')  # Añadido mask='auto' para mejor manejo de transparencias
                logger.info(f"Logo dibujado exitosamente desde: {logo_path}")
            except Exception as e:
                logger.error(f"Error al dibujar el logo: {str(e)}")
        else:
            logger.warning("No se encontró el archivo del logo en ninguna ubicación")

        # Encabezado
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "OFERTA")
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, f"Código: {pedido.codigo_unico}")
        p.drawString(50, height - 90, f"Fecha: {pedido.created_at.strftime('%d/%m/%Y %H:%M:%S')}")
        p.drawString(50, height - 110, f"Gestor: {pedido.user.get_full_name()}")

        # Datos del cliente
        p.drawString(50, height - 140, "Cliente:")
        p.drawString(70, height - 160, f"Nombre: {pedido.cliente.get_full_name()}")
        p.drawString(70, height - 180, f"CI: {pedido.cliente.carnet_identidad}")
        p.drawString(70, height - 200, f"Teléfono: {pedido.cliente.telefono}")
        p.drawString(70, height - 220, f"Transportista: {pedido.transportista or 'No especificado'}")

        # Tabla de productos
        y = height - 260
        p.drawString(50, y, "Producto")
        p.drawString(200, y, "Código")
        p.drawString(300, y, "Cantidad")
        p.drawString(380, y, "Precio Unit.")
        p.drawString(460, y, "Total")

        y -= 20
        for detalle in detalles:
            nombre_producto = f"(*) {detalle.material.nombre}" if detalle.en_oferta else detalle.material.nombre
            p.drawString(50, y, nombre_producto)
            p.drawString(200, y, str(detalle.material.codigo or 'N/A'))
            p.drawString(300, y, str(detalle.cantidad))

            if detalle.en_oferta:
                # Primero dibujamos el precio de oferta en rojo
                p.setFont("Helvetica", 12)
                p.setFillColorRGB(1, 0, 0)  # Rojo
                p.drawString(380, y, f"${detalle.precio_unitario:.2f}")

                # Luego dibujamos el precio regular tachado arriba
                p.setFont("Helvetica", 8)  # Más pequeño
                p.setFillColorRGB(0.5, 0.5, 0.5)  # Gris
                precio_str = f"${detalle.precio_regular:.2f}"
                precio_width = p.stringWidth(precio_str, "Helvetica", 8)

                # Dibujar precio regular
                p.drawString(380, y + 10, precio_str)
                # Dibujar línea de tachado
                p.line(380, y + 12, 380 + precio_width, y + 12)

                # Volver a negro para el resto del texto
                p.setFont("Helvetica", 12)
                p.setFillColorRGB(0, 0, 0)
            else:
                p.drawString(380, y, f"${detalle.precio_unitario:.2f}")

            p.drawString(460, y, f"${float(detalle.total):.2f}")
            y -= 20

        # Total
        p.line(50, y-10, 500, y-10)
        p.drawString(380, y-30, "Total:")
        p.drawString(460, y-30, f"${float(pedido.total):.2f}")

        p.showPage()
        p.save()

        # Obtener el valor del buffer y crear la respuesta HTTP
        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="oferta_{pedido.codigo_unico}.pdf"'
        response.write(pdf)

        return response

    except Exception as e:
        logger.error(f"Error generando oferta para pedido {pedido_id}: {str(e)}")
        return HttpResponse("Error generando la oferta", status=500)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def configurar_eliminacion(request):
    config = ConfiguracionPedidos.objects.first() or ConfiguracionPedidos()

    if request.method == 'POST':
        try:
            tiempo = int(request.POST.get('tiempo_eliminacion'))
            activo = request.POST.get('activo') == 'on'

            if tiempo < 1:
                raise ValueError("El tiempo debe ser mayor a 0 horas")

            config.tiempo_eliminacion = tiempo
            config.activo = activo
            config.save()

            # Si la configuración está activa, cancelar pedidos antiguos inmediatamente
            if activo:
                from .task import cancelar_pedidos_antiguos
                resultado = cancelar_pedidos_antiguos()
                if "Se cancelaron" in resultado:
                    messages.success(request, f"Configuración actualizada y {resultado.lower()}")
                else:
                    messages.success(request, "Configuración actualizada correctamente")
                    messages.info(request, resultado)
            else:
                messages.success(request, "Configuración actualizada correctamente")

        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Error al actualizar la configuración: {str(e)}")

    return render(request, 'pedidos/configurar_eliminacion.html', {
        'config': config
    })

@login_required
def estadisticas_usuario(request):
    try:
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
        pedidos = Pedido.objects.filter(user=request.user)
        if fecha_desde or fecha_hasta:
            pedidos = pedidos.filter(fecha_filter)

        # Calcular totales solo para pedidos efectuados
        pedidos_efectuados = pedidos.filter(estado='efectuado')
        total_ventas = pedidos_efectuados.aggregate(
            total=Sum('total'))['total'] or 0

        total_comisiones = pedidos_efectuados.annotate(
            comision=Sum(F('pedidodetalle__material__comision') *
                       F('pedidodetalle__cantidad'))
        ).aggregate(total=Sum('comision'))['total'] or 0

        context = {
            'usuario': request.user,
            'pedidos': pedidos.order_by('-created_at'),
            'pedidos_count': pedidos.count(),
            'total_ventas': total_ventas,
            'total_comisiones': total_comisiones,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta
        }

        return render(request, 'pedidos/historial_gestor.html', context)

    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
        raise e

@login_required(login_url='/autenticacion/logear')
def get_clientes_by_gestor(request):
    gestor_id = request.GET.get('gestor_id')
    if (gestor_id):
        # Obtener clientes relacionados con el gestor a través de los pedidos
        clientes = Cliente.objects.filter(pedido__user_id=gestor_id).distinct().values('id', 'nombre', 'apellidos')
    else:
        # Si no hay gestor seleccionado, devolver todos los clientes
        clientes = Cliente.objects.values('id', 'nombre', 'apellidos')

    return JsonResponse(list(clientes), safe=False)

@login_required
def buscar_cliente(request, carnet):
    try:
        cliente = Cliente.objects.get(carnet_identidad=carnet)

        # Solo retornar datos si el cliente pertenece al usuario autenticado
        if cliente.user == request.user or request.user.is_superuser:
            return JsonResponse({
                'status': 'success',
                'cliente': {
                    'nombre': cliente.nombre,
                    'apellidos': cliente.apellidos,
                    'telefono': cliente.telefono
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
