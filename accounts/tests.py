from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import CartItem, Order, Product, ShoppingCart


@override_settings(ROOT_URLCONF='cart.tests')
class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            code='ACCOUNT-1', name='محصول حساب', slug='account-product',
            price=2500, stock=10, status='active', is_active=True,
        )

    def registration_data(self, **overrides):
        data = {
            'username': 'new-buyer',
            'email': 'Buyer@Example.com',
            'password1': 'A-strong-password-483!',
            'password2': 'A-strong-password-483!',
        }
        data.update(overrides)
        return data

    def test_registration_page_and_successful_registration_login(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ایجاد حساب کاربری')
        response = self.client.post(reverse('register'), self.registration_data())
        self.assertRedirects(response, reverse('profile'))
        user = User.objects.get(username='new-buyer')
        self.assertEqual(user.email, 'buyer@example.com')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_registration_requires_valid_unique_email_and_matching_password(self):
        User.objects.create_user(username='existing', email='buyer@example.com', password='SafePass123!')
        response = self.client.post(reverse('register'), self.registration_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'حساب کاربری با این ایمیل از قبل وجود دارد')
        response = self.client.post(reverse('register'), self.registration_data(
            username='another', password2='different-password',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='another').exists())

    def test_login_logout_post_and_profile_requires_login(self):
        user = User.objects.create_user(username='login-user', password='SafePass123!')
        response = self.client.post(reverse('login'), {
            'username': user.username, 'password': 'SafePass123!',
        })
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('product_list'))
        protected = self.client.get(reverse('profile'))
        self.assertEqual(protected.status_code, 302)
        self.assertIn(reverse('login'), protected.url)
        self.assertIn('next=', protected.url)

    def test_profile_shows_only_own_recent_orders(self):
        user = User.objects.create_user(username='profile-user', password='SafePass123!')
        other = User.objects.create_user(username='profile-other', password='SafePass123!')
        own = Order.objects.create(
            order_number='OWN-ORDER', user=user, total=100,
            shipping_address='آدرس', billing_address='آدرس', shipping_city='شهر', shipping_state='استان',
        )
        Order.objects.create(
            order_number='OTHER-ORDER', user=other, total=100,
            shipping_address='آدرس', billing_address='آدرس', shipping_city='شهر', shipping_state='استان',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('profile'))
        self.assertContains(response, own.order_number)
        self.assertNotContains(response, 'OTHER-ORDER')

    def test_login_merges_guest_items_and_preserves_existing_user_items(self):
        import uuid

        user = User.objects.create_user(username='merge-user', password='SafePass123!')
        user_cart = ShoppingCart.objects.create(
            id=str(uuid.uuid4()), session_key='previous-user-session', user=user, total=0,
        )
        CartItem.objects.create(
            cart=user_cart, product=self.product, quantity=1,
            unit_price=self.product.price, subtotal=self.product.price,
        )

        # Build a fresh guest cart, then authenticate through the real LoginView.
        self.client.post(reverse('add_to_cart'), {'product_id': self.product.pk, 'quantity': 2})
        guest_cart = ShoppingCart.objects.get(user__isnull=True)
        response = self.client.post(reverse('login'), {
            'username': user.username, 'password': 'SafePass123!',
        })
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(ShoppingCart.objects.filter(user=user).count(), 1)
        cart = ShoppingCart.objects.get(user=user)
        self.assertEqual(cart.items.get().quantity, 3)
        self.assertEqual(CartItem.objects.filter(cart=cart).count(), 1)
        self.assertFalse(ShoppingCart.objects.filter(pk=user_cart.pk).exists())
