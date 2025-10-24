from django.core.validators import RegexValidator
from django import forms
from django.core.exceptions import ValidationError
from .models import Pedido

class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = [
            'nombre_cliente',
            'apellidos_cliente',
            'carnet_identidad_cliente',
            'telefono_cliente',
            'transportista',
        ]
    
    # Add these as form fields instead of model fields
    nombre_cliente = forms.CharField(
        max_length=100,
        validators=[RegexValidator(
            r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$',
            'El nombre solo puede contener letras y espacios'
        )],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'onkeypress': 'return soloLetras(event)'
        })
    )
    
    apellidos_cliente = forms.CharField(
        max_length=100,
        validators=[RegexValidator(
            r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$',
            'Los apellidos solo pueden contener letras y espacios'
        )],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'onkeypress': 'return soloLetras(event)'
        })
    )
    
    carnet_identidad_cliente = forms.CharField(
        max_length=11,
        validators=[RegexValidator(
            r'^\d{11}$',
            'El carnet de identidad debe tener exactamente 11 dígitos numéricos'
        )],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '11',
            'onkeypress': 'return soloNumeros(event)'
        })
    )
    
    telefono_cliente = forms.CharField(
        max_length=20,
        validators=[RegexValidator(
            r'^\d+$',
            'El teléfono solo puede contener números'
        )],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'onkeypress': 'return soloNumeros(event)'
        })
    )
    
    transportista = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )