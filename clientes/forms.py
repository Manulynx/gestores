from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellidos', 'carnet_identidad', 'telefono']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del cliente'
            }),
            'apellidos': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apellidos del cliente'
            }),
            'carnet_identidad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Carnet de identidad',
                'maxlength': '11'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de teléfono'
            }),
        }
        labels = {
            'nombre': 'Nombre',
            'apellidos': 'Apellidos',
            'carnet_identidad': 'Carnet de Identidad',
            'telefono': 'Teléfono',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True

    def clean_carnet_identidad(self):
        carnet = self.cleaned_data['carnet_identidad']
        
        # Validar que tenga exactamente 11 caracteres
        if len(carnet) != 11:
            raise forms.ValidationError('El carnet de identidad debe tener exactamente 11 caracteres.')
        
        # Validar que solo contenga números
        if not carnet.isdigit():
            raise forms.ValidationError('El carnet de identidad solo debe contener números.')
        
        # Verificar si ya existe otro cliente con este carnet (excluyendo el actual en caso de edición)
        queryset = Cliente.objects.filter(carnet_identidad=carnet)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise forms.ValidationError('Ya existe un cliente registrado con este carnet de identidad.')
        
        return carnet

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        
        if len(nombre) < 2:
            raise forms.ValidationError('El nombre debe tener al menos 2 caracteres.')
        
        # Validar que solo contenga letras y espacios
        if not all(char.isalpha() or char.isspace() for char in nombre):
            raise forms.ValidationError('El nombre solo debe contener letras y espacios.')
        
        return nombre.title()  # Capitalizar correctamente

    def clean_apellidos(self):
        apellidos = self.cleaned_data['apellidos'].strip()
        
        if len(apellidos) < 2:
            raise forms.ValidationError('Los apellidos deben tener al menos 2 caracteres.')
        
        # Validar que solo contenga letras y espacios
        if not all(char.isalpha() or char.isspace() for char in apellidos):
            raise forms.ValidationError('Los apellidos solo deben contener letras y espacios.')
        
        return apellidos.title()  # Capitalizar correctamente

    def clean_telefono(self):
        telefono = self.cleaned_data['telefono'].strip()
        
        # Remover espacios, guiones y paréntesis para validación
        telefono_clean = telefono.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
        
        if len(telefono_clean) < 8:
            raise forms.ValidationError('El número de teléfono debe tener al menos 8 dígitos.')
        
        if not telefono_clean.isdigit():
            raise forms.ValidationError('El teléfono solo debe contener números, espacios, guiones y paréntesis.')
        
        return telefono