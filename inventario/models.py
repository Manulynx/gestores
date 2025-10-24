from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
import io
import sys
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


class Categoria(models.Model):
    nombre = models.CharField(verbose_name='Nombre', max_length=50)
    imagen = models.ImageField(verbose_name='Imagen', upload_to='categorias', null=True, blank=True)
    def __str__(self):
        return self.nombre

class Material(models.Model):
    nombre = models.CharField(verbose_name='Nombre', max_length=50)
    codigo = models.CharField(verbose_name='Código', max_length=50, unique=True, null=True, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    imagen = models.ImageField(verbose_name='Imagen Principal', upload_to='inventario', null=True, blank=True)
    precio = models.FloatField(verbose_name='Precio', max_length=20)
    comision = models.FloatField(verbose_name='Comisión', max_length=20, default=0)
    cantidad = models.IntegerField(verbose_name='Cantidad')
    ficha_tecnica = models.FileField(verbose_name='Ficha técnica', upload_to='fichas_tecnicas', null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    destacado = models.BooleanField(verbose_name='Destacado', default=False, blank=True)
    activo = models.BooleanField(default=True)
    en_oferta = models.BooleanField(verbose_name='En Oferta', default=False)
    precio_oferta = models.FloatField(verbose_name='Precio en Oferta', null=True, blank=True)

    def __str__(self):
        return self.nombre

    def actualizar_stock(self, cantidad):
        """
        Actualiza el stock del material
        Args:
            cantidad: número positivo o negativo para sumar o restar del stock
        Returns:
            Boolean: True si la operación fue exitosa
        """
        nuevo_stock = self.cantidad + cantidad
        if nuevo_stock < 0:
            return False
        self.cantidad = nuevo_stock
        self.save()
        return True

    def get_cantidad_en_pedidos(self):
        """
        Obtiene la cantidad total en pedidos pendientes
        """
        from pedidos.models import PedidoDetalle
        cantidad = PedidoDetalle.objects.filter(
            material=self,
            pedido__estado='pendiente'
        ).aggregate(
            total=models.Sum('cantidad')
        )['total']
        return cantidad or 0

    def save(self, *args, **kwargs):
        if self.imagen:
            # Abrir imagen
            img = Image.open(self.imagen)
            
            # Convertir a RGB si es necesario
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Redimensionar manteniendo proporción
            output_size = (800, 800)
            img.thumbnail(output_size, Image.LANCZOS)
            
            # Guardar con buena calidad
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=90)
            output.seek(0)
            
            # Reemplazar la imagen original
            self.imagen = InMemoryUploadedFile(
                output,
                'ImageField',
                f"{self.imagen.name.split('.')[0]}.jpg",
                'image/jpeg',
                sys.getsizeof(output),
                None
            )
            
        super().save(*args, **kwargs)
    def calcular_precio_cup(self, precio):
        self.precio = precio * 350
        self.save()
        return True

    def soft_delete(self):
        self.activo = False
        self.save()

    @property
    def descuento_porcentaje(self):
        """Calcula el porcentaje de descuento entre el precio original y el precio de oferta"""
        if self.en_oferta and self.precio_oferta and self.precio:
            return ((self.precio - self.precio_oferta) / self.precio) * 100
        return 0

    @property
    def precio_actual(self):
        """Retorna el precio en oferta si está en oferta, sino el precio regular"""
        if self.en_oferta and self.precio_oferta is not None:
            return self.precio_oferta
        return self.precio

class MaterialImagen(models.Model):
    material = models.ForeignKey(Material, related_name='imagenes', on_delete=models.CASCADE)
    imagen = models.ImageField(verbose_name='Imagen', upload_to='inventario/materiales')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imagen de Material'
        verbose_name_plural = 'Imágenes de Materiales'
        ordering = ['created']

    def save(self, *args, **kwargs):
        if self.imagen:
            img = Image.open(self.imagen)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            output_size = (800, 800)
            img.thumbnail(output_size, Image.LANCZOS)
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=90)
            output.seek(0)
            self.imagen = InMemoryUploadedFile(
                output,
                'ImageField',
                f"{self.imagen.name.split('.')[0]}.jpg",
                'image/jpeg',
                sys.getsizeof(output),
                None
            )
        super().save(*args, **kwargs)

@login_required
def editar_material(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    
    if request.method == 'POST':
        try:
            # Validar campos obligatorios primero
            if not request.POST.get('nombre'):
                raise ValueError("El nombre es obligatorio")

            # Validar y convertir precio - mantener valor existente si está vacío
            precio_str = request.POST.get('precio', '').strip()
            if precio_str:
                try:
                    precio = float(precio_str)
                    if precio < 0:
                        raise ValueError("El precio no puede ser negativo")
                    material.precio = precio
                except ValueError:
                    raise ValueError("El precio debe ser un número válido")

            # Validar y convertir cantidad
            try:
                cantidad = int(request.POST.get('cantidad', 0))
                if cantidad < 0:
                    raise ValueError("La cantidad no puede ser negativa")
                material.cantidad = cantidad
            except ValueError:
                raise ValueError("La cantidad debe ser un número entero")

            # Validar y convertir comisión - mantener valor existente si está vacía
            comision_str = request.POST.get('comision', '').strip()
            if comision_str:
                try:
                    comision = float(comision_str)
                    if comision < 0:
                        raise ValueError("La comisión no puede ser negativa")
                    material.comision = comision
                except ValueError:
                    raise ValueError("La comisión debe ser un número válido")

            # Validar categoría
            try:
                categoria_id = int(request.POST.get('categoria'))
                material.categoria_id = categoria_id
            except (ValueError, TypeError):
                raise ValueError("Categoría inválida")

            # Actualizar campos básicos
            material.nombre = request.POST['nombre']
            
            # Validar código único
            codigo = request.POST.get('codigo', '').strip() or None
            if codigo:
                existing = Material.objects.filter(codigo=codigo).exclude(id=material_id).exists()
                if existing:
                    raise ValueError(f"Ya existe un material con el código {codigo}")
            material.codigo = codigo
            
            # Manejar archivos
            if 'imagen' in request.FILES:
                if material.imagen:
                    material.imagen.delete(save=False)
                material.imagen = request.FILES['imagen']
                
            if 'ficha_tecnica' in request.FILES:
                if material.ficha_tecnica:
                    material.ficha_tecnica.delete(save=False)
                material.ficha_tecnica = request.FILES['ficha_tecnica']
                
            if 'imagenes_secundarias' in request.FILES:
                for imagen in request.FILES.getlist('imagenes_secundarias'):
                    MaterialImagen.objects.create(
                        material=material,
                        imagen=imagen
                    )
            
            material.save()
            messages.success(request, f'Material {material.nombre} actualizado correctamente')
            
        except ValueError as e:
            messages.error(request, f'Error de validación: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error al actualizar el material: {str(e)}')
            
    return redirect('editar_inventario')
