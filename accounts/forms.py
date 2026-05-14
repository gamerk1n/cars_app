from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.models import Employee
from accounts.roles import role_label


User = get_user_model()


class RoleMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return role_label(obj.name)


class UserCreateForm(forms.ModelForm):
    full_name = forms.CharField(max_length=Employee._meta.get_field("full_name").max_length, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    groups = RoleMultipleChoiceField(
        queryset=Group.objects.order_by("name"), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ["username", "email", "full_name", "password", "is_active", "groups"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "input", "placeholder": "Логин"})
        self.fields["email"].widget.attrs.update({"class": "input", "placeholder": "name@company.ru"})
        self.fields["full_name"].widget.attrs.update({"class": "input", "placeholder": "ФИО пользователя"})
        self.fields["password"].widget.attrs.update({"class": "input", "placeholder": "Пароль"})
        self.fields["is_active"].widget.attrs.update({"class": "checkbox"})


class UserUpdateForm(forms.ModelForm):
    full_name = forms.CharField(max_length=Employee._meta.get_field("full_name").max_length, required=False)
    groups = RoleMultipleChoiceField(
        queryset=Group.objects.order_by("name"), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ["username", "email", "full_name", "is_active", "groups"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        employee = getattr(self.instance, "employee", None)
        self.fields["full_name"].initial = employee.full_name if employee else ""
        self.fields["username"].widget.attrs.update({"class": "input", "placeholder": "Логин"})
        self.fields["email"].widget.attrs.update({"class": "input", "placeholder": "name@company.ru"})
        self.fields["full_name"].widget.attrs.update({"class": "input", "placeholder": "ФИО пользователя"})
        self.fields["is_active"].widget.attrs.update({"class": "checkbox"})
