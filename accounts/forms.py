from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='نام کاربری',
        widget=forms.TextInput(attrs={'autocomplete': 'username', 'spellcheck': 'false'}),
    )
    password = forms.CharField(
        label='گذرواژه',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        label='ایمیل',
        required=True,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'spellcheck': 'false', 'dir': 'ltr'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')
        labels = {'username': 'نام کاربری'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'نام کاربری'
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['username'].widget.attrs['spellcheck'] = 'false'
        self.fields['password1'].label = 'گذرواژه'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].label = 'تکرار گذرواژه'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('حساب کاربری با این ایمیل از قبل وجود دارد.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
