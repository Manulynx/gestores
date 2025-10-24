from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import PerfilGestor

class GestorCreationForm(UserCreationForm):
    nombre_gestor = forms.CharField(max_length=100, required=True, label="Nombre del Gestor")
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            PerfilGestor.objects.create(
                user=user,
                nombre_gestor=self.cleaned_data['nombre_gestor']
            )
        return user