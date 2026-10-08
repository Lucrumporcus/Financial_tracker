from django import forms
from django.contrib.auth import login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

User = get_user_model()


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, label='Пароль')
    password_confirm = forms.CharField(widget=forms.PasswordInput, label='Повторите пароль')

    class Meta:
        model = User
        fields = ('username', 'email')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password_confirm'):
            self.add_error('password_confirm', 'Пароли не совпадают.')
        elif cleaned.get('password'):
            try:
                validate_password(cleaned['password'], self.instance or User(username=cleaned.get('username', '')))
            except ValidationError as exc:
                self.add_error('password', exc.messages)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


@require_http_methods(['GET', 'POST'])
def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')
    return render(request, 'finance/login.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def register_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'finance/register.html', {'form': form})


@require_POST
def logout_page(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_page(request):
    return render(request, 'finance/dashboard.html')


@login_required
def groups_page(request):
    return render(request, 'finance/groups.html')


@login_required
def operations_page(request):
    return render(request, 'finance/operations.html')


@login_required
def statistics_page(request):
    return render(request, 'finance/statistics.html')
