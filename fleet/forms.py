from django import forms

from fleet.models import Car


class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = ["brand_model", "vin", "color", "type", "status"]
        widgets = {
            "brand_model": forms.TextInput(attrs={"class": "input"}),
            "vin": forms.TextInput(attrs={"class": "input"}),
            "color": forms.TextInput(attrs={"class": "input"}),
            "type": forms.TextInput(attrs={"class": "input"}),
            "status": forms.Select(attrs={"class": "select"}),
        }
