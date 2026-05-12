from django import forms

from fleet.models import Car, MaintenanceRecord


class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = [
            "brand_model",
            "vin",
            "color",
            "type",
            "status",
            "current_mileage",
            "next_service_date",
            "next_service_mileage",
        ]
        widgets = {
            "brand_model": forms.TextInput(attrs={"class": "input"}),
            "vin": forms.TextInput(attrs={"class": "input"}),
            "color": forms.TextInput(attrs={"class": "input"}),
            "type": forms.TextInput(attrs={"class": "input"}),
            "status": forms.Select(attrs={"class": "select"}),
            "current_mileage": forms.NumberInput(attrs={"class": "input", "min": 0}),
            "next_service_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "next_service_mileage": forms.NumberInput(attrs={"class": "input", "min": 0}),
        }


class MaintenanceRecordForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = [
            "kind",
            "service_date",
            "title",
            "description",
            "contractor",
            "mileage",
            "cost",
        ]
        widgets = {
            "kind": forms.Select(attrs={"class": "select"}),
            "service_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "title": forms.TextInput(attrs={"class": "input"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 4}),
            "contractor": forms.TextInput(attrs={"class": "input"}),
            "mileage": forms.NumberInput(attrs={"class": "input", "min": 0}),
            "cost": forms.NumberInput(attrs={"class": "input", "min": 0, "step": "0.01"}),
        }
