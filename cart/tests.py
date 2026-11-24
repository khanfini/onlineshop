import json
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.views.generic import TemplateView

from products.models import CartItem, Product, ProductVariant, ShoppingCart


urlpatterns = [
    path('', TemplateView.as_view(template_name='base.html'), name='root_home'),
    path('products/', TemplateView.as_view(template_name='base.html'), name='product_list'),
    path('product/<slug:slug>/', TemplateView.as_view(template_name='base.html'), name='product_detail'),
    path('categories/', TemplateView.as_view(template_name='base.html'), name='category_list'),
    path('brands/', TemplateView.as_view(template_name='base.html'), name='brand_list'),
    path('about/', TemplateView.as_view(template_name='base.html'), name='about'),
    path('contact/', TemplateView.as_view(template_name='base.html'), name='contact'),
    path('cart/', include('cart.urls')),
    path('api/cart/add/', __import__('cart.views', fromlist=['add_to_cart']).add_to_cart),
    path('api/cart/add/<int:product_id>/', __import__('cart.views', fromlist=['add_to_cart']).add_to_cart),
    path('api/cart/count/', __import__('cart.views', fromlist=['cart_count']).cart_count),
    path('', include('accounts.urls')),
    path('', include('orders.urls')),
]


@override_settings(ROOT_URLCONF='cart.tests')
class CartTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            code='CART-1', name='محصول سبد', slug='cart-product',
            price=Decimal('12500.00'), stock=10, status='active', is_active=True,
        )
        cls.user = User.objects.create_user(username='cart-user', password='SafePass123!')

    def add_product(self, quantity=1, next_url=None):
        data = {'product_id': self.product.pk, 'quantity': quantity}
        if next_url:
            data['next'] = next_url
        return self.client.post(reverse('add_to_cart'), data)

    def test_guest_form_add_creates_valid_session_cart_and_redirects(self):
        response = self.add_product(2, next_url=reverse('cart_view'))
        self.assertRedirects(response, reverse('cart_view'))
        cart = ShoppingCart.objects.get()
        uuid.UUID(cart.id)
        self.assertEqual(cart.session_key, self.client.session.session_key)
        self.assertIsNone(cart.user)
        self.assertEqual(str(cart.total), '25000.00')
        self.assertEqual(cart.items.get().quantity, 2)

    def test_json_add_by_url_and_body_aggregates_quantity(self):
        first = self.client.post(
            f'/api/cart/add/{self.product.pk}/',
            data=json.dumps({'quantity': 2}), content_type='application/json',
        )
        second = self.client.post(
            '/api/cart/add/',
            data=json.dumps({'product_id': self.product.pk, 'quantity': 3}),
            content_type='application/json',
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['success'])
        self.assertEqual(second.json()['cart_count'], 5)
        self.assertEqual(CartItem.objects.get().quantity, 5)

    def test_json_rejects_bad_input_and_inactive_product(self):
        malformed = self.client.post('/api/cart/add/', data='{', content_type='application/json')
        self.assertEqual(malformed.status_code, 400)
        self.assertFalse(malformed.json()['success'])
        invalid = self.client.post(
            '/api/cart/add/', data=json.dumps({'product_id': 'bad', 'quantity': 1}),
            content_type='application/json',
        )
        self.assertEqual(invalid.status_code, 400)
        self.product.status = 'draft'
        self.product.save(update_fields=['status'])
        inactive = self.client.post(
            '/api/cart/add/', data=json.dumps({'product_id': self.product.pk, 'quantity': 1}),
            content_type='application/json',
        )
        self.assertEqual(inactive.status_code, 400)
        self.assertEqual(ShoppingCart.objects.count(), 0)

    def test_add_checks_aggregate_stock_and_variant_belongs_to_product(self):
        other = Product.objects.create(
            code='CART-2', name='محصول دیگر', slug='cart-other',
            price=1000, stock=5, status='active', is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=other, sku='OTHER-VAR', price=1500, stock=4, status='active',
        )
        mismatch = self.client.post(reverse('add_to_cart'), {
            'product_id': self.product.pk, 'variant_id': variant.pk, 'quantity': 1,
        })
        self.assertEqual(mismatch.status_code, 302)
        self.assertFalse(CartItem.objects.exists())
        self.add_product(8)
        response = self.add_product(3)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CartItem.objects.get().quantity, 8)

    def test_variant_uses_current_variant_price_in_total(self):
        variant = ProductVariant.objects.create(
            product=self.product, sku='CART-VAR', price=Decimal('18000.00'), stock=5, status='active',
        )
        self.client.post(reverse('add_to_cart'), {
            'product_id': self.product.pk, 'variant_id': variant.pk, 'quantity': 2,
        })
        cart = ShoppingCart.objects.get()
        item = cart.items.get()
        self.assertEqual(str(item.unit_price), '18000.00')
        self.assertEqual(str(cart.total), '36000.00')

    def test_update_remove_clear_recalculate_totals_and_use_post(self):
        self.add_product(2)
        item = CartItem.objects.get()
        response = self.client.post(reverse('update_cart_item'), {
            'cart_item_id': item.pk, 'quantity': 4,
        })
        self.assertRedirects(response, reverse('cart_view'))
        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)
        self.assertEqual(str(item.cart.total), '50000.00')

        self.client.post(reverse('remove_from_cart'), {'cart_item_id': item.pk})
        item.cart.refresh_from_db()
        self.assertEqual(item.cart.total, 0)
        self.assertEqual(self.client.get(reverse('update_cart_item')).status_code, 405)

        self.add_product(2)
        self.client.post(reverse('clear_cart'))
        cart = ShoppingCart.objects.get()
        self.assertFalse(cart.items.exists())
        self.assertEqual(cart.total, 0)

    def test_cannot_update_or_remove_another_users_item(self):
        self.client.force_login(self.user)
        self.add_product(1)
        item = CartItem.objects.get()
        other = User.objects.create_user(username='other-cart-user', password='SafePass123!')
        self.client.force_login(other)
        self.client.post(reverse('update_cart_item'), {'cart_item_id': item.pk, 'quantity': 9})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)
        self.client.post(reverse('remove_from_cart'), {'cart_item_id': item.pk})
        self.assertTrue(CartItem.objects.filter(pk=item.pk).exists())

    def test_empty_cart_page_is_honest(self):
        response = self.client.get(reverse('cart_view'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'سبد خرید شما خالی است')
        self.assertEqual(ShoppingCart.objects.count(), 0)

    def test_existing_duplicate_user_carts_are_safely_consolidated(self):
        self.client.force_login(self.user)
        session_key = self.client.session.session_key
        first = ShoppingCart.objects.create(id=str(uuid.uuid4()), session_key=session_key, user=self.user, total=0)
        second = ShoppingCart.objects.create(id=str(uuid.uuid4()), session_key=session_key, user=self.user, total=0)
        CartItem.objects.create(cart=first, product=self.product, quantity=1, unit_price=Decimal('1'), subtotal=Decimal('1'))
        CartItem.objects.create(cart=second, product=self.product, quantity=2, unit_price=Decimal('1'), subtotal=Decimal('1'))
        response = self.client.get(reverse('cart_view'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ShoppingCart.objects.filter(user=self.user).count(), 1)
        cart = ShoppingCart.objects.get(user=self.user)
        self.assertEqual(cart.items.get().quantity, 3)
