import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import F
from .models import Material, MaterialImagen

def limpiar_imagenes_huerfanas():
    """Elimina las imágenes que no están asociadas a ningún material"""
    
    # Obtener todas las imágenes en la carpeta media/inventario
    media_path = os.path.join(settings.MEDIA_ROOT, 'inventario')
    archivos_media = []
    
    # Asegurarse de que el directorio existe
    if not os.path.exists(media_path):
        print(f"El directorio {media_path} no existe")
        return

    # Recolectar todos los archivos de imagen
    for root, dirs, files in os.walk(media_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                ruta_completa = os.path.join(root, file)
                ruta_relativa = os.path.relpath(ruta_completa, settings.MEDIA_ROOT)
                archivos_media.append(ruta_relativa.replace('\\', '/'))
                print(f"Archivo encontrado: {ruta_relativa}")

    # Obtener todas las imágenes referenciadas en la base de datos
    imagenes_db = set()
    
    # Imágenes principales
    principales = Material.objects.exclude(imagen='').values_list('imagen', flat=True)
    for img in principales:
        if img:
            img_path = str(img).replace('\\', '/')
            imagenes_db.add(img_path)
            print(f"Imagen principal en DB: {img_path}")
    
    # Imágenes secundarias (tanto de inventario/materiales como de inventario)
    secundarias = MaterialImagen.objects.exclude(imagen='')
    for img in secundarias:
        if img.imagen:
            img_path = str(img.imagen).replace('\\', '/')
            # Verificar tanto la ruta original como la ruta sin 'materiales'
            img_path_alt = img_path.replace('inventario/materiales/', 'inventario/')
            imagenes_db.add(img_path)
            imagenes_db.add(img_path_alt)
            print(f"Imagen secundaria en DB: {img_path}")
            print(f"Ruta alternativa: {img_path_alt}")

    # Encontrar y eliminar imágenes huérfanas
    total_eliminadas = 0
    for archivo in archivos_media:
        print(f"Verificando archivo: {archivo}")
        archivo_alt = archivo.replace('inventario/', 'inventario/materiales/')
        if archivo not in imagenes_db and archivo_alt not in imagenes_db:
            print(f"Archivo no encontrado en DB: {archivo}")
            ruta_completa = os.path.join(settings.MEDIA_ROOT, archivo.replace('/', os.sep))
            try:
                if os.path.exists(ruta_completa):
                    os.remove(ruta_completa)
                    total_eliminadas += 1
                    print(f"Imagen huérfana eliminada: {archivo}")
            except Exception as e:
                print(f"Error al eliminar {archivo}: {str(e)}")
        else:
            print(f"Archivo encontrado en DB: {archivo}")

    print(f"\nResumen de limpieza:")
    print(f"Total de archivos en media: {len(archivos_media)}")
    print(f"Total de imágenes en base de datos: {len(imagenes_db)}")
    print(f"Total de imágenes eliminadas: {total_eliminadas}")