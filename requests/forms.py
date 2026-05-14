from django import forms

from requests.models import Request, VehicleInspection, VehicleInspectionPhoto


class RequestCreateForm(forms.ModelForm):
    rules_accepted = forms.BooleanField(
        required=True,
        label="Я прочитал(а) правила предоставления автомобиля",
        error_messages={"required": "Подтвердите, что вы прочитали правила."},
        widget=forms.CheckboxInput(attrs={"class": "checkbox"}),
    )

    class Meta:
        model = Request
        fields = [
            "start_date",
            "end_date",
            "reason",
            "attachment",
            "rules_accepted",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "reason": forms.TextInput(
                attrs={"placeholder": "Например: ремонт / ДТП / ТО", "class": "input"}
            ),
            "attachment": forms.ClearableFileInput(attrs={"class": "input"}),
        }


class ReturnForm(forms.Form):
    defects = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 4,
                "placeholder": "Опишите дефекты (если есть). Например: царапина на бампере, трещина стекла…",
            }
        ),
        label="Дефекты",
    )


class VehicleInspectionForm(forms.ModelForm):
    damage_zones = forms.MultipleChoiceField(
        required=False,
        choices=VehicleInspection.DAMAGE_ZONE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "damage-zone-options"}),
        label="Зоны повреждений",
    )
    photo_exterior = forms.FileField(
        required=False,
        label="Фото кузова",
        widget=forms.ClearableFileInput(attrs={"class": "input", "accept": "image/*"}),
    )
    photo_interior = forms.FileField(
        required=False,
        label="Фото салона",
        widget=forms.ClearableFileInput(attrs={"class": "input", "accept": "image/*"}),
    )
    photo_damage = forms.FileField(
        required=False,
        label="Фото повреждений",
        widget=forms.ClearableFileInput(attrs={"class": "input", "accept": "image/*"}),
    )

    class Meta:
        model = VehicleInspection
        fields = [
            "mileage",
            "fuel_level",
            "exterior_condition",
            "interior_condition",
            "damage_zones",
            "defects",
            "employee_signature",
            "inspector_signature",
        ]
        widgets = {
            "mileage": forms.NumberInput(attrs={"class": "input", "min": 0}),
            "fuel_level": forms.NumberInput(
                attrs={"class": "input", "min": 0, "max": 100}
            ),
            "exterior_condition": forms.Textarea(
                attrs={"class": "input", "rows": 3}
            ),
            "interior_condition": forms.Textarea(
                attrs={"class": "input", "rows": 3}
            ),
            "defects": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 4,
                    "placeholder": "Опишите дефекты, если они есть.",
                }
            ),
            "employee_signature": forms.TextInput(attrs={"class": "input"}),
            "inspector_signature": forms.TextInput(attrs={"class": "input"}),
        }

    def clean_damage_zones(self):
        return list(self.cleaned_data.get("damage_zones") or [])

    def photo_files(self):
        return [
            (VehicleInspectionPhoto.Label.EXTERIOR, self.cleaned_data.get("photo_exterior")),
            (VehicleInspectionPhoto.Label.INTERIOR, self.cleaned_data.get("photo_interior")),
            (VehicleInspectionPhoto.Label.DAMAGE, self.cleaned_data.get("photo_damage")),
        ]
