from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "you_are@depressed.com",
            }
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Choose a username",
            }
        )

        self.fields["password1"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Create a password",
            }
        )

        self.fields["password2"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Confirm your password",
            }
        )

    def clean_email(self):
        email = self.cleaned_data["email"]

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")

        return email


class SeherAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Username",
            }
        )

        self.fields["password"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Password",
            }
        )
