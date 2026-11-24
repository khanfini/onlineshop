from django.db import models
from django.db.models import CASCADE, PROTECT, SET_NULL, PositiveIntegerField
from django.utils.text import slugify
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import reverse
from decimal import Decimal


# Basic Models - These are referenced by other models
class Category(models.Model):
    name = models.CharField('نام', max_length=100, unique=True)
    slug = models.SlugField('اسلاگ', unique=True)
    parent = models.ForeignKey(
        'self', on_delete=CASCADE, null=True, blank=True,
        related_name='children', verbose_name='دسته والد'
    )
    is_active = models.BooleanField('فعال', default=True)
    sort_order = models.PositiveIntegerField('ترتیب', default=0)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'دسته‌بندی'
        verbose_name_plural = 'دسته‌بندی‌ها'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField('نام', max_length=100, unique=True)
    slug = models.SlugField('اسلاگ', unique=True)
    logo = models.ImageField('لوگو', upload_to='brands/', blank=True, null=True)
    is_active = models.BooleanField('فعال', default=True)

    class Meta:
        verbose_name = 'برند'
        verbose_name_plural = 'برندها'
        ordering = ['name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField('نام', max_length=50, unique=True)
    slug = models.SlugField('اسلاگ', unique=True)

    class Meta:
        verbose_name = 'تگ'
        verbose_name_plural = 'تگ‌ها'

    def __str__(self):
        return self.name


class ProductAttribute(models.Model):
    name = models.CharField('نام ویژگی', max_length=50, unique=True)
    slug = models.SlugField('اسلاگ', unique=True)
    type = models.CharField('نوع', max_length=20, choices=[
        ('text', 'متن'),
        ('number', 'عدد'),
        ('boolean', 'بولی'),
        ('select', 'انتخابی'),
        ('color', 'رنگ'),
    ])
    unit = models.CharField('واحد', max_length=20, blank=True, help_text='مثل: عدد، لیتر، کیلوگرم')
    is_filterable = models.BooleanField('قابل فیلتر شدن', default=True)
    sort_order = models.PositiveIntegerField('ترتیب', default=0)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'ویژگی محصول'
        verbose_name_plural = 'ویژگی‌های محصول'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    attribute = models.ForeignKey(
        ProductAttribute, on_delete=CASCADE, related_name='values',
        verbose_name='ویژگی'
    )
    value = models.CharField('مقدار', max_length=100)
    color_code = models.CharField('کد رنگ', max_length=20, blank=True, null=True, help_text='مقداری شبیه #FF0000 برای رنگ‌ها')
    extra_price = models.DecimalField('قیمت اضافی', decimal_places=2, max_digits=10, default=0, help_text='قیمت اضافی برای این مقدار خاص')
    sort_order = models.PositiveIntegerField('ترتیب', default=0)

    class Meta:
        verbose_name = 'مقدار ویژگی'
        verbose_name_plural = 'مقادیر ویژگی'
        unique_together = ['attribute', 'value']
        ordering = ['sort_order', 'value']

    def __str__(self):
        if self.color_code:
            return f"{self.attribute.name} - {self.value} ({self.color_code})"
        return f"{self.attribute.name} - {self.value}"


# Main Product Model - Referenced by all other models
class Product(models.Model):
    STATUS_CHOICES = [
        ('draft', 'پیش‌نویس'),
        ('active', 'فعال'),
        ('archived', 'بایگانی'),
    ]

    code = models.CharField('کد محصول', max_length=50, unique=True)
    name = models.CharField('نام محصول', max_length=100)
    slug = models.SlugField('URL دوستانه', unique=True, blank=True, null=True)

    image = models.ImageField('تصویر اصلی', upload_to='products/', blank=True, null=True)
    descriptions = models.TextField('توضیحات', blank=True)

    sku = models.CharField('کد انبارداری (SKU)', max_length=50, unique=True, blank=True, null=True)

    category = models.ForeignKey(
        Category, on_delete=PROTECT, related_name='products', verbose_name='دسته‌بندی',
        blank=True, null=True
    )
    brand = models.ForeignKey(
        Brand, on_delete=SET_NULL, null=True, blank=True,
        related_name='products', verbose_name='برند'
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='products', verbose_name='تگ‌ها')

    price = models.DecimalField('قیمت', decimal_places=2, max_digits=12)
    compare_at_price = models.DecimalField('قیمت قبل از تخفیف', decimal_places=2, max_digits=12, null=True, blank=True)
    cost_price = models.DecimalField('بهای تمام شده', decimal_places=2, max_digits=12, null=True, blank=True)

    stock = models.PositiveIntegerField('موجودی', default=0)
    track_inventory = models.BooleanField('پیگیری موجودی', default=True)
    low_stock_threshold = models.PositiveIntegerField('آستانه کم‌بود', default=5)

    status = models.CharField('وضعیت', max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField('محصول ویژه', default=False)
    is_active = models.BooleanField('فعال', default=True)

    meta_title = models.CharField('متا تایتل', max_length=60, blank=True)
    meta_description = models.TextField('متا توضیحات', max_length=160, blank=True)
    meta_keywords = models.CharField('متا کلیدواژه‌ها', max_length=255, blank=True)

    weight = models.DecimalField('وزن (گرم)', max_digits=8, decimal_places=2, null=True, blank=True)
    length = models.DecimalField('طول (سم)', max_digits=6, decimal_places=2, null=True, blank=True)
    width = models.DecimalField('عرض (سم)', max_digits=6, decimal_places=2, null=True, blank=True)
    height = models.DecimalField('ارتفاع (سم)', max_digits=6, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField('تاریخ ثبت', default=timezone.now)
    updated_at = models.DateTimeField('تاریخ بروزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'محصول'
        verbose_name_plural = 'محصولات'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or f'product-{self.code.lower()}'
            unique_slug = base_slug
            counter = 1
            while Product.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.compare_at_price and self.compare_at_price <= self.price:
            raise ValidationError({'compare_at_price': 'قیمت قبل از تخفیف باید بزرگتر از قیمت فعلی باشد'})

    @property
    def is_in_stock(self):
        return self.stock > 0 if self.track_inventory else True

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return int(((self.compare_at_price - self.price) / self.compare_at_price) * 100)
        return 0
class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=CASCADE, related_name='images', verbose_name='محصول'
    )
    image = models.ImageField('تصویر گالری', upload_to='products/gallery/')
    alt_text = models.CharField('متن جایگزین (ALT)', max_length=125, blank=True)
    sort_order = models.PositiveIntegerField('ترتیب', default=0)
    is_feature = models.BooleanField('تصویر اصلی', default=False)
    created_at = models.DateTimeField('تاریخ آپلود', auto_now_add=True)

    class Meta:
        verbose_name = 'تصویر محصول'
        verbose_name_plural = 'تصاویر محصول'
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f"{self.product.name} - تصویر {self.sort_order}"

    def save(self, *args, **kwargs):
        if self.is_feature:
            ProductImage.objects.filter(product=self.product, is_feature=True).exclude(pk=self.pk).update(is_feature=False)
        super().save(*args, **kwargs)
class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=CASCADE, related_name='variants', verbose_name='محصول اصلی'
    )
    sku = models.CharField('کد محصول (SKU)', max_length=50, unique=True)
    isbn = models.CharField('شماره کتاب (ISBN)', max_length=20, blank=True, help_text='اختیاری برای محصولات کتاب')

    price = models.DecimalField('قیمت', decimal_places=2, max_digits=12)
    compare_at_price = models.DecimalField('قیمت قبل از تخفیف', decimal_places=2, max_digits=12, null=True, blank=True)
    cost_price = models.DecimalField('بهای تمام شده', decimal_places=2, max_digits=12, null=True, blank=True)
    stock = models.PositiveIntegerField('موجودی', default=0)
    track_inventory = models.BooleanField('پیگیری موجودی', default=True)
    weight = models.DecimalField('وزن (گرم)', max_digits=8, decimal_places=2, null=True, blank=True)
    length = models.DecimalField('طول (سم)', max_digits=6, decimal_places=2, null=True, blank=True)
    width = models.DecimalField('عرض (سم)', max_digits=6, decimal_places=2, null=True, blank=True)
    height = models.DecimalField('ارتفاع (سم)', max_digits=6, decimal_places=2, null=True, blank=True)

    is_default = models.BooleanField('پیش‌فرض', default=False)
    image = models.ImageField('تصویر واریانت', upload_to='products/variants/', blank=True, null=True)
    status = models.CharField('وضعیت', max_length=20, choices=[
        ('draft', 'پیش‌نویس'),
        ('active', 'فعال'),
        ('archived', 'بایگانی'),
        ('out_of_stock', 'ناموجود'),
    ], default='active')

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('تاریخ بروزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'واریانت محصول'
        verbose_name_plural = 'واریانت‌های محصول'
        ordering = ['product__name', 'sku']

    def __str__(self):
        return f"{self.product.name} - {self.sku}"

    def save(self, *args, **kwargs):
        if not self.sku and self.product:
            if self.product.sku:
                self.sku = f"{self.product.code}-{self.id or 'new'}"
            else:
                self.sku = f"VAR-{self.product.id or 'new'}"
        super().save(*args, **kwargs)

    @property
    def is_in_stock(self):
        return self.stock > 0 if self.track_inventory else True

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return int(((self.compare_at_price - self.price) / self.compare_at_price) * 100)
        return 0
class ProductReview(models.Model):
    product = models.ForeignKey(
        Product, on_delete=CASCADE, related_name='reviews', verbose_name='محصول'
    )
    user_name = models.CharField('نام کاربر', max_length=100)
    user_email = models.EmailField('ایمیل کاربر')
    rating = models.PositiveSmallIntegerField('امتیاز', choices=[(i, i) for i in range(1, 6)])
    title = models.CharField('عنوان', max_length=200)
    content = models.TextField('متن نقد و بررسی')
    is_approved = models.BooleanField('تایید شده', default=False)
    is_verified_purchase = models.BooleanField('خرید تایید شده', default=False)
    helpful_votes = models.PositiveIntegerField('رای مفید', default=0)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('تاریخ بروزرسانی', auto_now=True)
    approved_at = models.DateTimeField('تاریخ تایید', null=True, blank=True)

    class Meta:
        verbose_name = 'نقد و بررسی محصول'
        verbose_name_plural = 'نقد و بررسی‌های محصول'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.rating} ستاره"

    def clean(self):
        super().clean()
        if self.rating < 1 or self.rating > 5:
            raise ValidationError({'rating': 'امتیاز باید بین ۱ تا ۵ باشد'})
class ShoppingCart(models.Model):
    id = models.CharField('شناسه سبد خرید', max_length=100, primary_key=True)
    session_key = models.CharField('کلید جلسه', max_length=100, db_index=True)
    user = models.ForeignKey(
        'auth.User', on_delete=CASCADE, null=True, blank=True,
        related_name='carts', verbose_name='کاربر'
    )

    subtotal = models.DecimalField('جمع جزئی', decimal_places=2, max_digits=12, default=0)
    tax = models.DecimalField('مالیات', decimal_places=2, max_digits=10, default=0)
    shipping = models.DecimalField('هزینه ارسال', decimal_places=2, max_digits=10, default=0)
    discount = models.DecimalField('تخفیف', decimal_places=2, max_digits=10, default=0)
    total = models.DecimalField('مجموع', decimal_places=2, max_digits=12)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('تاریخ بروزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'سبد خرید'
        verbose_name_plural = 'سبد خرید‌ها'
        ordering = ['-updated_at']

    def __str__(self):
        user_display = f"کاربر {self.user.username}" if self.user else f"جلسه {self.session_key}"
        return f"سبد خرید {user_display} - {self.total} تومان"

    def recalculate_totals(self):
        self.subtotal = sum(item.subtotal for item in self.items.all())
        self.total = self.subtotal + self.tax + self.shipping - self.discount
        self.save(update_fields=['subtotal', 'total', 'updated_at'])
class CartItem(models.Model):
    cart = models.ForeignKey(
        ShoppingCart, on_delete=CASCADE, related_name='items', verbose_name='سبد خرید'
    )
    product = models.ForeignKey(
        Product, on_delete=CASCADE, related_name='cart_items', verbose_name='محصول'
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=SET_NULL, null=True, blank=True,
        related_name='cart_items', verbose_name='واریانت'
    )

    quantity = models.PositiveIntegerField('تعداد', default=1)
    unit_price = models.DecimalField('قیمت واحد', decimal_places=2, max_digits=12)
    discount = models.DecimalField('تخفیف واحد', decimal_places=2, max_digits=10, default=0)
    subtotal = models.DecimalField('جمع جزئی', decimal_places=2, max_digits=12)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('تاریخ بروزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'آیتم سبد خرید'
        verbose_name_plural = 'آیتم‌های سبد خرید'

    def __str__(self):
        variant_display = f" - {self.variant.sku}" if self.variant else ""
        return f"{self.product.name} ({self.quantity}){variant_display}"

    def clean(self):
        super().clean()
        if self.variant and self.variant.product != self.product:
            raise ValidationError({'variant': 'واریانت باید متعلق به محصول انتخاب شده باشد'})

        if self.variant:
            if not self.variant.is_in_stock and self.variant.track_inventory:
                raise ValidationError({'variant': 'این محصول در حال حاضر موجود نیست'})

        if self.quantity < 1:
            raise ValidationError({'quantity': 'تعداد باید حداقل ۱ باشد'})

    def save(self, *args, **kwargs):
        self.clean()

        self.unit_price = self.variant.price if self.variant else self.product.price
        self.subtotal = self.quantity * (self.unit_price - self.discount)

        super().save(*args, **kwargs)

        self.cart.recalculate_totals()

    def delete(self, *args, **kwargs):
        cart = self.cart
        result = super().delete(*args, **kwargs)
        cart.recalculate_totals()
        return result


class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('confirmed', 'تایید شده'),
        ('shipped', 'ارسال شده'),
        ('delivered', 'تحویل داده شده'),
        ('cancelled', 'لغو شده'),
        ('refunded', 'مرجوعی'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('paid', 'پرداخت شده'),
        ('failed', 'ناموفق'),
        ('refunded', 'مرجوعی'),
        ('partially_refunded', 'مرجوعی جزئی'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'پرداخت نقدی'),
        ('online', 'پرداخت آنلاین'),
        ('paypal', 'پی‌پال'),
        ('card', 'کارت اعتباری'),
        ('bank_transfer', 'حواله بانکی'),
    ]

    order_number = models.CharField('شماره سفارش', max_length=50, unique=True)
    user = models.ForeignKey(
        'auth.User', on_delete=CASCADE, related_name='orders', verbose_name='کاربر',
        null=True, blank=True
    )
    guest_info = models.JSONField('اطلاعات مهمان', blank=True, null=True)

    status = models.CharField('وضعیت سفارش', max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    payment_status = models.CharField('وضعیت پرداخت', max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField('روش پرداخت', max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')

    shipping_address = models.TextField('آدرس ارسال')
    billing_address = models.TextField('آدرس صورتحساب')
    shipping_city = models.CharField('شهر ارسال', max_length=100)
    shipping_state = models.CharField('استان ارسال', max_length=100)

    subtotal = models.DecimalField('جمع جزئی', decimal_places=2, max_digits=12, default=0)
    tax = models.DecimalField('مالیات', decimal_places=2, max_digits=10, default=0)
    shipping = models.DecimalField('هزینه ارسال', decimal_places=2, max_digits=10, default=0)
    discount = models.DecimalField('تخفیف', decimal_places=2, max_digits=10, default=0)
    total = models.DecimalField('مجموع', decimal_places=2, max_digits=12)

    notes = models.TextField('یادداشت‌ها', blank=True)
    admin_notes = models.TextField('یادداشت‌های ادمین', blank=True)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('تاریخ بروزرسانی', auto_now=True)
    paid_at = models.DateTimeField('تاریخ پرداخت', null=True, blank=True)
    shipped_at = models.DateTimeField('تاریخ ارسال', null=True, blank=True)
    delivered_at = models.DateTimeField('تاریخ تحویل', null=True, blank=True)

    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['status', 'payment_status']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"سفارش #{self.order_number} - {self.total} تومان"

    def generate_order_number(self):
        import random
        import string

        while True:
            random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            order_number = f"ORD-{random_part}"
            if not Order.objects.filter(order_number=order_number).exists():
                return order_number

    def recalculate_totals(self):
        self.subtotal = sum(item.subtotal for item in self.items.all())
        self.total = self.subtotal + self.tax + self.shipping - self.discount
        self.save(update_fields=['subtotal', 'total', 'updated_at'])

    def can_cancel(self):
        return self.status in ['pending', 'confirmed']

    def can_ship(self):
        return self.status == 'confirmed' and self.payment_status == 'paid'

    def can_deliver(self):
        return self.status == 'shipped' and self.payment_status == 'paid'
class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=CASCADE, related_name='items', verbose_name='سفارش'
    )
    product = models.ForeignKey(
        Product, on_delete=PROTECT, related_name='order_items', verbose_name='محصول'
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=SET_NULL, null=True, blank=True,
        related_name='order_items', verbose_name='واریانت'
    )

    product_name = models.CharField('نام محصول', max_length=200)
    product_sku = models.CharField('کد محصول', max_length=50)
    variant_sku = models.CharField('کد واریانت', max_length=50, blank=True)

    quantity = models.PositiveIntegerField('تعداد')
    unit_price = models.DecimalField('قیمت واحد', decimal_places=2, max_digits=12)
    discount = models.DecimalField('تخفیف واحد', decimal_places=2, max_digits=10, default=0)
    subtotal = models.DecimalField('جمع جزئی', decimal_places=2, max_digits=12)

    weight = models.DecimalField('وزن واحد (گرم)', max_digits=8, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'آیتم سفارش'
        verbose_name_plural = 'آیتم‌های سفارش'

    def __str__(self):
        variant_display = f" - {self.variant_sku}" if self.variant_sku else ""
        return f"{self.product_name} ({self.quantity}){variant_display}"

    def save(self, *args, **kwargs):
        self.product_name = self.product.name
        self.product_sku = self.product.code
        if self.variant:
            self.variant_sku = self.variant.sku

        self.unit_price = self.variant.price if self.variant else self.product.price
        self.subtotal = self.quantity * (self.unit_price - self.discount)

        super().save(*args, **kwargs)

        self.order.recalculate_totals()
class Payment(models.Model):
    order = models.ForeignKey(
        Order, on_delete=CASCADE, related_name='payments', verbose_name='سفارش'
    )

    transaction_id = models.CharField('شناسه تراکنش', max_length=100, unique=True)
    payment_method = models.CharField('روش پرداخت', max_length=20, choices=[
        ('cash', 'پرداخت نقدی'),
        ('online', 'پرداخت آنلاین'),
        ('paypal', 'پی‌پال'),
        ('card', 'کارت اعتباری'),
        ('bank_transfer', 'حواله بانکی'),
    ])

    amount = models.DecimalField('مبلغ', decimal_places=2, max_digits=12)
    fee = models.DecimalField('کارمزد', decimal_places=2, max_digits=10, default=0)
    net_amount = models.DecimalField('مبلغ خالص', decimal_places=2, max_digits=12)

    status = models.CharField('وضعیت', max_length=20, choices=[
        ('pending', 'در انتظار پرداخت'),
        ('paid', 'پرداخت شده'),
        ('failed', 'ناموفق'),
        ('refunded', 'مرجوعی'),
        ('partially_refunded', 'مرجوعی جزئی'),
    ], default='pending')

    gateway_response = models.JSONField('پاسخ درگاه', blank=True, null=True)
    failure_reason = models.TextField('دلیل شکست', blank=True)

    paid_at = models.DateTimeField('تاریخ پرداخت', null=True, blank=True)
    refunded_at = models.DateTimeField('تاریخ مرجوعی', null=True, blank=True)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'پرداخت'
        verbose_name_plural = 'پرداخت‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f"پرداخت {self.amount} تومان برای سفارش #{self.order.order_number}"

    def refund(self, amount=None, reason=''):
        if self.status in ['refunded', 'partially_refunded']:
            raise ValidationError('این پرداخت قبلاً مرجوع شده است')

        refund_amount = amount or self.net_amount

        if refund_amount > self.net_amount:
            raise ValidationError('مبلغ مرجوعی نمی‌تواند بیشتر از مبلغ پرداختی باشد')

        self.status = 'refunded' if refund_amount == self.net_amount else 'partially_refunded'
        self.refunded_at = timezone.now()
        self.failure_reason = f"مرجوعی: {reason}" if reason else "مرجوعی"
        self.save()

        self.order.status = 'refunded' if refund_amount == self.order.total else 'partially_refunded'
        self.order.save()
class Coupon(models.Model):
    code = models.CharField('کد تخفیف', max_length=50, unique=True)
    name = models.CharField('نام', max_length=100)

    description = models.TextField('توضیحات', blank=True)

    type = models.CharField('نوع', max_length=20, choices=[
        ('percentage', 'درصدی'),
        ('fixed_amount', 'مبلغ ثابت'),
        ('buy_x_get_y', 'خرید x دریافت y'),
        ('free_shipping', 'ارسال رایگان'),
    ])

    value = models.DecimalField('مقدار تخفیف', decimal_places=2, max_digits=10)
    min_order_amount = models.DecimalField('حداقل مبلغ سفارش', decimal_places=2, max_digits=12, default=0)
    max_discount_amount = models.DecimalField('حداکثر مبلغ تخفیف', decimal_places=2, max_digits=12, null=True, blank=True)

    usage_limit = models.PositiveIntegerField('حد استفاده', null=True, blank=True, help_text='حد کل استفاده از کوپن')
    used_count = models.PositiveIntegerField('تعداد استفاده شده', default=0)

    valid_from = models.DateTimeField('از تاریخ اعتبار')
    valid_to = models.DateTimeField('تا تاریخ اعتبار')

    is_active = models.BooleanField('فعال', default=True)
    is_public = models.BooleanField('همه دسترسی دارند', default=True)

    free_shipping_min = models.DecimalField('حداقل مبلغ برای ارسال رایگان', decimal_places=2, max_digits=12, null=True, blank=True)

    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('تاریخ بروزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'کوپن'
        verbose_name_plural = 'کوپن‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False, "این کوپن غیرفعال است"

        if now < self.valid_from:
            return False, "این کوپن هنوز فعال نشده است"

        if now > self.valid_to:
            return False, "این کوپن منقضی شده است"

        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "محدودیت استفاده از این کوپن به پایان رسیده است"

        return True, "کوپن معتبر است"

    def clean(self):
        super().clean()

        if self.valid_from >= self.valid_to:
            raise ValidationError('تاریخ اعتبار باید بعد از تاریخ شروع باشد')

        if self.type == 'fixed_amount' and self.value <= 0:
            raise ValidationError('مبلغ تخفیف ثابت باید بیشتر از ۰ باشد')

        if self.type == 'percentage' and (self.value <= 0 or self.value > 100):
            raise ValidationError('درصد تخفیف باید بین ۰ تا ۱۰۰ باشد')

    def apply_to_order(self, order):
        if not self.is_valid()[0]:
            raise ValidationError('این کوپن معتبر نیست')

        if order.subtotal < self.min_order_amount:
            raise ValidationError(f"مبلغ سفارش باید حداقل {self.min_order_amount} تومان باشد")

        self.used_count += 1
        self.save()

        return {
            'discount_amount': self.calculate_discount(order.total),
            'message': f"کد تخفیف {self.code} اعمال شد"
        }

    def calculate_discount(self, order_total):
        if self.type == 'percentage':
            discount = (order_total * self.value) / 100
        elif self.type == 'fixed_amount':
            discount = min(self.value, order_total)
        elif self.type == 'free_shipping':
            discount = self.free_shipping_min if self.free_shipping_min else order_total
        elif self.type == 'buy_x_get_y':
            discount = 0

        if self.max_discount_amount and discount > self.max_discount_amount:
            discount = self.max_discount_amount

        return discount


class CampaignPoster(models.Model):
    """پوسترها و بنرهای مناسبتی (یلدا، نوروز، جمعه سیاه، تخفیف‌های فصلی و اعیاد)"""
    THEME_CHOICES = [
        ('rose', 'اناری / یلدایی (#e11d48)'),
        ('emerald', 'بهاری / سبز زمردی (#059669)'),
        ('amber', 'پاییزی / طلایی (#d97706)'),
        ('indigo', 'کلاسیک / نیلی (#4f46e5)'),
        ('purple', 'لوکس / بنفش رویال (#7c3aed)'),
        ('dark', 'جمعه سیاه / دارک (#0f172a)'),
    ]

    title = models.CharField('عنوان مناسبت', max_length=150, help_text='مثال: جشنواره شگفت‌انگیز شب یلدا')
    subtitle = models.CharField('شعار یا توضیح کوتاه', max_length=250, blank=True, help_text='مثال: تا ۵۰٪ تخفیف ویژه روی تمامی محصولات چرمی دست‌دوز')
    badge_text = models.CharField('برچسب مناسبت', max_length=50, default='پیشنهاد ویژه مناسبتی', help_text='مثال: ویژه شب یلدا، سال نو مبارک')
    theme = models.CharField('تم رنگی پوستر', max_length=30, choices=THEME_CHOICES, default='rose')
    poster_image = models.ImageField('تصویر پوستر', upload_to='campaigns/posters/', blank=True, null=True, help_text='تصویر باکیفیت پوستر طراحی‌شده برای مناسبت')
    discount_code = models.CharField('کد تخفیف اختصاصی مناسبت', max_length=50, blank=True, help_text='مثال: YALDA1403')
    discount_percent = models.PositiveIntegerField('درصد تخفیف', blank=True, null=True, help_text='در صورت وجود تخفیف درصدی مشخص (مثلاً ۳۰)')
    button_text = models.CharField('متن دکمه خرید', max_length=60, default='مشاهده محصولات جشنواره')
    button_link = models.CharField('لینک مقصد دکمه', max_length=255, default='/products/?discount=1')
    start_date = models.DateTimeField('زمان شروع نمایش', default=timezone.now)
    end_date = models.DateTimeField('زمان پایان جشنواره (برای روزشمار معکوس)', blank=True, null=True)
    is_active = models.BooleanField('فعال برای نمایش در سایت', default=True)
    sort_order = models.PositiveIntegerField('ترتیب نمایش', default=0)
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'پوستر مناسبتی'
        verbose_name_plural = 'پوسترهای مناسبتی'
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.badge_text})"

    @property
    def is_currently_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


class ProductStoryBook(models.Model):
    """A tactile, draggable three-dimensional product book on sunlit linen."""
    title = models.CharField('عنوان کتاب', max_length=150, default='دفترچه‌ی لحظه‌های مراقبت')
    subtitle = models.CharField('زیرعنوان', max_length=250, default='هر صفحه، یک لحظه از روز و یک انتخاب برای مراقبت از خود.')
    is_active = models.BooleanField('فعال در صفحه اصلی', default=True)
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'کتاب سه‌بعدی نمایش محصولات'
        verbose_name_plural = 'کتاب‌های سه‌بعدی نمایش محصولات'

    def __str__(self):
        return self.title


class ProductStoryPage(models.Model):
    VALLEY_CHOICES = [('dawn', 'سپیده‌دم'), ('morning', 'صبح'), ('golden', 'غروب طلایی'), ('night', 'شب')]
    book = models.ForeignKey(ProductStoryBook, on_delete=models.CASCADE, related_name='pages', verbose_name='کتاب')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='story_pages', verbose_name='محصول این صفحه')
    chapter_title = models.CharField('عنوان لحظه', max_length=120, default='لحظه‌ای برای خودت')
    hour_label = models.CharField('ساعت روایت', max_length=40, default='۷:۳۰ صبح')
    note = models.CharField('یادداشت روی صفحه', max_length=200, blank=True)
    valley = models.CharField('حال‌وهوای دره', max_length=20, choices=VALLEY_CHOICES, default='morning')
    sort_order = models.PositiveIntegerField('ترتیب صفحه', default=0)

    class Meta:
        verbose_name = 'صفحه کتاب محصول'
        verbose_name_plural = 'صفحات کتاب محصولات'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.chapter_title} — {self.product.name}'

