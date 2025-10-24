from django.urls import path

from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'carro'

urlpatterns = [
    path('agregar/<int:material_id>/', views.agregar_material, name='agregar'),
    path("eliminar/<int:material_id>/", views.eliminar_material, name='eliminar'),
    path("restar/<int:material_id>/", views.restar_material, name='restar'),
    path("limpiar/", views.limpiar_carro, name='limpiar'),
    path('widget/', views.widget_cart, name='widget'),
    path('actualizar/<int:material_id>/<int:cantidad>/', views.actualizar_cantidad, name='actualizar'),
]

