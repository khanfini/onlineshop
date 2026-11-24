from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Order, OrderItem, Product, ProductVariant, ShoppingCart


@override_settings(ROOT_URLCONF='cart.tests')
class CheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            code='ORDER-1', name='محصول سفارش', slug='order-product',
            price=Decimal('10000.00'), stock=5, status='active', is_active=True,
        )

    def checkout_data(self, **overrides):
        data = {
            'full_name': 'خریدار آزمایشی',
            'email': 'buyer@example.com',
            'phone': '09121234567',
            'address': 'خیابان آزمایش، پلاک ۱',
            'city': 'تهران',
            'state': 'تهران',
            'notes': 'تحویل در ساعت کاری',
            'payment_method': 'cash',
        }
        data.update(overrides)
        return data

    def add_product(self, quantity=1, variant=None):
        data = {'product_id': self.product.pk, 'quantity': quantity}
        if variant:
            data['variant_id'] = variant.pk
        return self.client.post(reverse('add_to_cart'), data)

    def test_checkout_empty_cart_is_honest_and_cannot_create_order(self):
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'سبد خرید شما خالی است')
        response = self.client.post(reverse('checkout'), self.checkout_data())
        self.assertRedirects(response, reverse('cart_view'))
        self.assertFalse(Order.objects.exists())

    def test_guest_checkout_creates_pending_cash_order_and_decrements_stock(self):
        self.add_product(2)
        session = self.client.session
        session['coupon_code'] = 'temporary-coupon'
        session.save()
        response = self.client.post(reverse('checkout'), self.checkout_data())
        order = Order.objects.get()
        self.assertRedirects(response, reverse('order_confirmation', args=[order.order_number]))
        self.assertTrue(order.order_number.startswith('ORD-'))
        self.assertIsNone(order.user)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.payment_status, 'pending')
        self.assertEqual(order.payment_method, 'cash')
        self.assertIsNone(order.paid_at)
        self.assertEqual(order.guest_info['full_name'], 'خریدار آزمایشی')
        self.assertEqual(order.guest_info['phone'], '09121234567')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(str(order.total), '20000.00')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(ShoppingCart.objects.get().total, 0)
        self.assertFalse(ShoppingCart.objects.get().items.exists())
        self.assertNotIn('coupon_code', self.client.session)
        confirmation = self.client.get(response.url)
        self.assertContains(confirmation, 'پرداخت هنگام تحویل انجام می‌شود')
        self.assertContains(confirmation, 'پرداخت آنلاین انجام نشده است')

    def test_authenticated_checkout_uses_current_variant_price_and_snapshots_item(self):
        user = User.objects.create_user(username='order-user', email='user@example.com', password='SafePass123!')
        variant = ProductVariant.objects.create(
            product=self.product, sku='ORDER-VAR', price=Decimal('14000.00'), stock=4, status='active',
        )
        self.client.force_login(user)
        self.add_product(2, variant=variant)
        response = self.client.post(reverse('checkout'), self.checkout_data())
        order = Order.objects.get(user=user)
        self.assertEqual(response.status_code, 302)
        item = order.items.get()
        self.assertEqual(str(item.unit_price), '14000.00')
        self.assertEqual(str(item.subtotal), '28000.00')
        self.assertEqual(item.product_name, 'محصول سفارش')
        self.assertEqual(item.product_sku, 'ORDER-1')
        self.assertEqual(item.variant_sku, 'ORDER-VAR')
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 2)
        variant.price = 99999
        variant.save(update_fields=['price'])
        item.refresh_from_db()
        self.assertEqual(str(item.unit_price), '14000.00')
        self.assertEqual(str(order.total), '28000.00')

    def test_stock_failure_rolls_back_order_and_cart(self):
        self.add_product(2)
        self.product.stock = 1
        self.product.save(update_fields=['stock'])
        response = self.client.post(reverse('checkout'), self.checkout_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'موجودی')
        self.assertFalse(Order.objects.exists())
        self.assertEqual(ShoppingCart.objects.get().items.get().quantity, 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    def test_checkout_rejects_online_payment_and_invalid_fields(self):
        self.add_product()
        response = self.client.post(reverse('checkout'), self.checkout_data(payment_method='online'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        response = self.client.post(reverse('checkout'), self.checkout_data(email='bad', phone='بدون عدد'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'شماره تماس معتبر نیست')
        self.assertFalse(Order.objects.exists())

    def test_duplicate_variant_rows_cannot_oversell_stock(self):
        variant = ProductVariant.objects.create(
            product=self.product, sku='STOCK-POOL', price=Decimal('12000'), stock=5, status='active',
        )
        self.add_product(4, variant=variant)
        self.client.post(reverse('add_to_cart'), {'product_id': self.product.pk, 'quantity': 4, 'variant_id': variant.pk})
        cart = ShoppingCart.objects.get()
        item = cart.items.get()
        item.pk = None
        item.save()
        response = self.client.post(reverse('checkout'), self.checkout_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'موجودی')
        self.assertFalse(Order.objects.exists())
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 5)

    def test_checkout_never_creates_negative_totals(self):
        self.add_product()
        cart = ShoppingCart.objects.get()
        cart.discount = Decimal('50000')
        cart.save(update_fields=['discount'])
        self.client.post(reverse('checkout'), self.checkout_data())
        order = Order.objects.get()
        self.assertEqual(order.discount, Decimal('10000'))
        self.assertEqual(order.total, Decimal('0'))
        self.assertEqual(order.items.get().subtotal, Decimal('10000'))

    def test_order_list_detail_and_ownership(self):
        user = User.objects.create_user(username='owner', password='SafePass123!')
        other = User.objects.create_user(username='intruder', password='SafePass123!')
        order = Order.objects.create(
            order_number='PRIVATE-ORDER', user=user, total=100,
            shipping_address='آدرس', billing_address='آدرس', shipping_city='شهر', shipping_state='استان',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('order_list'))
        self.assertContains(response, order.order_number)
        response = self.client.get(reverse('order_detail', args=[order.order_number]))
        self.assertEqual(response.status_code, 200)
        self.client.force_login(other)
        response = self.client.get(reverse('order_detail', args=[order.order_number]))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse('order_list'))
        self.assertNotContains(response, order.order_number)

    def test_guest_order_confirmation_is_not_publicly_enumerable(self):
        order = Order.objects.create(
            order_number='GUEST-PRIVATE', guest_info={'email': 'private@example.com'}, total=100,
            shipping_address='آدرس', billing_address='آدرس', shipping_city='شهر', shipping_state='استان',
        )
        response = self.client.get(reverse('order_confirmation', args=[order.order_number]))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, 'private@example.com', status_code=403)
