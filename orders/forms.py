from django import forms


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        label='نام و نام خانوادگی',
        max_length=200,
        widget=forms.TextInput(attrs={'autocomplete': 'name'}),
    )
    email = forms.EmailField(
        label='ایمیل',
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'spellcheck': 'false', 'dir': 'ltr'}),
    )
    phone = forms.CharField(
        label='شماره تماس',
        max_length=30,
        widget=forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel', 'type': 'tel', 'dir': 'ltr'}),
    )
    address = forms.CharField(
        label='آدرس کامل',
        widget=forms.Textarea(attrs={'rows': 4, 'autocomplete': 'street-address'}),
    )
    city = forms.CharField(
        label='شهر',
        max_length=100,
        widget=forms.TextInput(attrs={'autocomplete': 'address-level2'}),
    )
    state = forms.CharField(
        label='استان',
        max_length=100,
        widget=forms.TextInput(attrs={'autocomplete': 'address-level1'}),
    )
    notes = forms.CharField(
        label='یادداشت سفارش (اختیاری)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    payment_method = forms.ChoiceField(
        label='روش پرداخت',
        choices=(('cash', 'پرداخت در محل (هنگام تحویل)'),),
        initial='cash',
        widget=forms.RadioSelect,
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not any(character.isdigit() for character in phone):
            raise forms.ValidationError('شماره تماس معتبر نیست.')
        return phone

    def clean_payment_method(self):
        payment_method = self.cleaned_data['payment_method']
        if payment_method != 'cash':
            raise forms.ValidationError('در حال حاضر فقط پرداخت هنگام تحویل امکان‌پذیر است.')
        return payment_method
