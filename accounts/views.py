from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import SeherAuthenticationForm, SignUpForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)

        login(self.request, self.object)

        messages.success(
            self.request,
            "Your Seher account has been created.",
        )

        return response


class SeherLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = SeherAuthenticationForm
