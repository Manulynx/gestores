import time
from django.core.management.base import BaseCommand
from inventario.utils import limpiar_imagenes_huerfanas

class Command(BaseCommand):
    help = 'Limpia periódicamente las imágenes huérfanas del directorio media'

    def handle(self, *args, **options):
        HOURS_1 = 1 * 60 * 60  # 1 hora en segundos
        
        while True:
            try:
                self.stdout.write('Iniciando limpieza de imágenes huérfanas...')
                limpiar_imagenes_huerfanas()
                self.stdout.write(self.style.SUCCESS('Limpieza completada'))
                self.stdout.write(self.style.SUCCESS('Esperando 1 hora para la próxima limpieza...'))
                time.sleep(HOURS_1)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\nLimpieza detenida por el usuario'))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
                time.sleep(HOURS_1)  # También esperar 1 hora en caso de error