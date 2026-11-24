from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(label='نام و نام خانوادگی', max_length=100, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    email = forms.EmailField(label='ایمیل', widget=forms.EmailInput(attrs={'autocomplete': 'email', 'spellcheck': 'false', 'dir': 'ltr'}))
    subject = forms.CharField(label='موضوع', max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    message = forms.CharField(label='پیام شما', widget=forms.Textarea(attrs={'rows': 5, 'autocomplete': 'off'}), max_length=3000)


class ReviewForm(forms.Form):
    rating = forms.IntegerField(min_value=1, max_value=5)
    title = forms.CharField(max_length=200)
    content = forms.CharField(max_length=5000)
