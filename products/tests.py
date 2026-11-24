from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Brand, Category, Product, ProductReview, ProductStoryBook, ProductStoryPage, ProductVariant


class StorefrontTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='اکسسوری', slug='accessories')
        cls.brand = Brand.objects.create(name='برند نمونه', slug='sample')
        cls.product = Product.objects.create(
            code='P-001', name='کیف دستی نمونه', slug='sample-bag',
            category=cls.category, brand=cls.brand, price=Decimal('1250000'),
            compare_at_price=Decimal('1500000'), stock=8, status='active',
            is_active=True, is_featured=True, descriptions='توضیحات محصول نمونه',
        )

    def test_home_and_aliases_render_catalog(self):
        response = self.client.get(reverse('root_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, 'محبوب‌ترین‌های دنیای زیبایی')
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, reverse('root_home'), status_code=301)

    def test_product_without_slug_is_safely_excluded(self):
        Product.objects.create(code='NO-SLUG', name='محصول فارسی', slug='', price=100, stock=1)
        self.assertEqual(self.client.get(reverse('root_home')).status_code, 200)
        self.assertEqual(self.client.get(reverse('product_list')).status_code, 200)
        self.product.slug = ''
        self.product.name = 'محصول با نام فارسی'
        self.product.save()
        self.assertTrue(self.product.slug)

    def test_search_filters_and_sorting(self):
        hidden = Product.objects.create(
            code='P-002', name='محصول دیگر', slug='other', price=Decimal('100'),
            stock=1, status='draft', category=self.category,
        )
        response = self.client.get(reverse('product_list'), {'search': 'کیف', 'category': self.category.slug, 'sort': 'price_low'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertNotContains(response, hidden.name)
        self.assertEqual(list(response.context['products']), [self.product])

    def test_pagination_keeps_filters(self):
        response = self.client.get(reverse('product_list'), {'category': self.category.slug, 'search': 'کیف'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="search"')

    def test_product_detail_and_variant(self):
        variant = ProductVariant.objects.create(
            product=self.product, sku='P-001-BLUE', price=Decimal('1300000'),
            stock=4, status='active', is_default=True,
        )
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, variant.sku)
        self.assertNotContains(response, 'cost_price')
        self.assertEqual(response.context['default_variant'], variant)

    def test_only_approved_reviews_and_no_email(self):
        ProductReview.objects.create(
            product=self.product, user_name='کاربر', user_email='private@example.com',
            rating=5, title='بررسی نمونه', content='متن بررسی', is_approved=True,
        )
        ProductReview.objects.create(
            product=self.product, user_name='نهان', user_email='hidden@example.com',
            rating=1, title='تأیید نشده', content='نمایش نده', is_approved=False,
        )
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, 'بررسی نمونه')
        self.assertNotContains(response, 'private@example.com')
        self.assertNotContains(response, 'تأیید نشده')

    def test_review_requires_login_and_valid_data(self):
        response = self.client.post(reverse('add_review'), {'product_id': self.product.id, 'rating': 5, 'title': 'خوب', 'content': 'خوب بود'})
        self.assertRedirects(response, reverse('login'))
        self.assertEqual(ProductReview.objects.count(), 0)
        get_user_model().objects.create_user('reviewer', 'reviewer@example.com', 'Strong-test-pass-912')
        self.client.login(username='reviewer', password='Strong-test-pass-912')
        response = self.client.post(reverse('add_review'), {'product_id': self.product.id, 'rating': 5, 'title': 'خوب', 'content': 'خوب بود'})
        self.assertRedirects(response, self.product.get_absolute_url())
        review = ProductReview.objects.get()
        self.assertFalse(review.is_approved)
        self.assertFalse(review.is_verified_purchase)

    @override_settings(MEDIA_ROOT='C:/Users/JKHANF~1.SAB/AppData/Local/Temp/kilo/test-media')
    def test_story_book_uses_real_products_and_admin_content(self):
        book = ProductStoryBook.objects.create(title='دفترچه‌ی مراقبت')
        ProductStoryPage.objects.create(book=book, product=self.product, chapter_title='یک صبح آرام', valley='dawn')
        response = self.client.get(reverse('root_home'))
        self.assertContains(response, 'data-story-book')
        self.assertContains(response, 'data-book-open')
        self.assertContains(response, 'یک صبح آرام')
        self.assertContains(response, 'data-valley="dawn"')
        self.assertContains(response, self.product.get_absolute_url())
        self.assertNotContains(response, 'data-hillock-pin')
        book.is_active = False
        book.save()
        self.assertNotContains(self.client.get(reverse('root_home')), 'data-story-book')

    def test_supporting_routes(self):
        for route in ('category_list', 'brand_list', 'about', 'contact'):
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        response = self.client.post(reverse('contact'), {'name': '', 'email': 'bad', 'subject': '', 'message': ''})
        self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse('contact'), {'name': 'کاربر', 'email': 'test@example.com', 'subject': 'پرسش', 'message': 'پیام نمونه'})
        self.assertRedirects(response, reverse('contact'))
