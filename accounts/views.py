from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import RegisterForm, StyledAuthenticationForm


class StoreLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True
    next_page = reverse_lazy('profile')

    def form_valid(self, form):
        # Importing cart.views registers its user_logged_in receiver.
        from cart import views as cart_views  # noqa: F401
        old_session_key = self.request.session.session_key
        guest_cart_ids = list(
            cart_views.ShoppingCart.objects.filter(
                session_key=old_session_key, user__isnull=True,
            ).values_list('pk', flat=True)
        ) if old_session_key else []
        response = super().form_valid(form)
        # session_key is rotated before Django emits user_logged_in.
        cart_views.merge_guest_cart_on_login(
            sender=form.get_user().__class__,
            request=self.request,
            user=form.get_user(),
            guest_cart_ids=guest_cart_ids,
        )
        return response


class StoreLogoutView(LogoutView):
    # Django's built-in LogoutView accepts POST only.
    next_page = reverse_lazy('product_list')


@login_required
def profile(request):
    recent_orders = request.user.orders.prefetch_related('items')[:5]
    return render(request, 'accounts/profile.html', {'recent_orders': recent_orders})


def register(request):
    if request.user.is_authenticated:
        return redirect('profile')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Capture the guest cart before login rotates the session key.
            from cart import views as cart_views
            old_session_key = request.session.session_key
            guest_cart_ids = list(cart_views.ShoppingCart.objects.filter(
                session_key=old_session_key, user__isnull=True,
            ).values_list('pk', flat=True)) if old_session_key else []
            auth_login(request, user)
            cart_views._merge_login_carts(request, user, guest_cart_ids)
            messages.success(request, 'حساب کاربری شما ایجاد شد و وارد شدید.')
            return redirect('profile')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})
