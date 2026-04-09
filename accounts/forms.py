from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


User = get_user_model()


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "is_active", "groups"]


class UserUpdateForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ["username", "email", "is_active", "groups"]
