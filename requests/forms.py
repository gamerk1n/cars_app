from django import forms

from requests.models import Request


class RequestCreateForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ["start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "reason": forms.TextInput(
                attrs={"placeholder": "Например: ремонт / ДТП / ТО", "class": "input"}
            ),
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
