from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    Product, Category, Brand, Tag, ProductImage,
    ProductAttribute, AttributeValue, ProductVariant,
    ProductReview, ShoppingCart, CartItem, Order, OrderItem, Payment, Coupon,
    CampaignPoster, ProductStoryBook, ProductStoryPage
)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'alt_text', 'sort_order', 'is_feature')
    readonly_fields = ('created_at',)
    show_change_link = True

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('sku', 'price', 'stock', 'is_default', 'status')
    show_change_link = True

class ProductReviewInline(admin.TabularInline):
    model = ProductReview
    extra = 0
    readonly_fields = ('created_at', 'approved_at')
    can_delete = False

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'brand', 'price', 'stock', 'status', 'is_featured', 'created_at')
    list_filter = ('status', 'category', 'brand', 'is_featured', 'is_active', 'tags')
    search_fields = ('code', 'name', 'sku', 'slug', 'descriptions')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVariantInline, ProductReviewInline]
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('status', 'is_featured', 'stock')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['make_active', 'make_archived', 'make_draft']

    def make_active(self, request, queryset):
        queryset.update(status='active')
    make_active.short_description = 'وضعیت محصولات به حالت فعال تغییر یابد'

    def make_archived(self, request, queryset):
        queryset.update(status='archived')
    make_archived.short_description = 'وضعیت محصولات به حالت بایگانی تغییر یابد'

    def make_draft(self, request, queryset):
        queryset.update(status='draft')
    make_draft.short_description = 'وضعیت محصولات به حالت پیش‌نویس تغییر یابد'

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_active', 'sort_order')
    list_filter = ('is_active', 'parent')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('sort_order', 'name')
    search_fields = ('name',)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image_thumbnail', 'sort_order', 'is_feature', 'created_at')
    list_filter = ('is_feature', 'product__category', 'product__brand')
    search_fields = ('product__name', 'alt_text')

    def image_thumbnail(self, obj):
        if obj.image:
            from django.utils.html import format_html
            return format_html('<img src="{}" width="50" />', obj.image.url)
        return '-'
    image_thumbnail.short_description = 'پیش‌نمایش'

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'sku', 'price', 'stock', 'is_default', 'status')
    list_filter = ('status', 'is_default', 'product__category')
    search_fields = ('sku', 'product__name')
    list_editable = ('price', 'stock', 'is_default', 'status')

@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'is_filterable', 'sort_order')
    list_filter = ('type', 'is_filterable')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ('attribute', 'value', 'extra_price', 'sort_order')
    list_filter = ('attribute',)
    search_fields = ('attribute__name', 'value')

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user_name', 'rating', 'is_approved', 'is_verified_purchase', 'created_at')
    list_filter = ('is_approved', 'is_verified_purchase', 'rating', 'product')
    search_fields = ('product__name', 'user_name', 'user_email', 'title', 'content')
    actions = ['approve_reviews', 'reject_reviews']

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
    approve_reviews.short_description = 'نقد و بررسیهای انتخاب شده را تایید کن'

    def reject_reviews(self, request, queryset):
        queryset.update(is_approved=False)
    reject_reviews.short_description = 'نقد و بررسیهای انتخاب شده را رد کن'

@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_key', 'user', 'subtotal', 'tax', 'shipping', 'discount', 'total', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('id', 'session_key')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'variant', 'quantity', 'unit_price', 'subtotal', 'created_at')
    list_filter = ('created_at', 'cart')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'status', 'payment_status', 'total', 'created_at')
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('order_number', 'user__username', 'user__email', 'shipping_city')
    readonly_fields = ('created_at', 'updated_at', 'paid_at', 'shipped_at', 'delivered_at')
    actions = ['mark_as_paid', 'mark_as_shipped', 'mark_as_delivered', 'cancel_order']

    def mark_as_paid(self, request, queryset):
        queryset.update(status='confirmed', payment_status='paid', paid_at=timezone.now())
    mark_as_paid.short_description = 'به عنوان پرداخت شده علامت بزن'

    def mark_as_shipped(self, request, queryset):
        queryset.update(status='shipped', shipped_at=timezone.now())
    mark_as_shipped.short_description = 'به عنوان ارسال شده علامت بزن'

    def mark_as_delivered(self, request, queryset):
        queryset.update(status='delivered', delivered_at=timezone.now())
    mark_as_delivered.short_description = 'به عنوان تحویل داده شده علامت بزن'

    def cancel_order(self, request, queryset):
        queryset.update(status='cancelled')
    cancel_order.short_description = 'سفارش را لغو کن'

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'variant', 'quantity', 'unit_price', 'subtotal', 'created_at')
    list_filter = ('created_at', 'order')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'transaction_id', 'payment_method', 'amount', 'status', 'paid_at', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('transaction_id', 'order__order_number')
    readonly_fields = ('created_at', 'paid_at', 'refunded_at')

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'type', 'value', 'min_order_amount', 'usage_limit', 'used_count', 'is_active', 'valid_from', 'valid_to')
    list_filter = ('is_active', 'type', 'valid_from', 'valid_to')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['activate_coupons', 'deactivate_coupons']

    def activate_coupons(self, request, queryset):
        queryset.update(is_active=True)
    activate_coupons.short_description = 'کوپن‌های انتخاب شده را فعال کن'

    def deactivate_coupons(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_coupons.short_description = 'کوپن‌های انتخاب شده را غیرفعال کن'


@admin.register(CampaignPoster)
class CampaignPosterAdmin(admin.ModelAdmin):
    list_display = ('title', 'badge_text', 'theme', 'discount_code', 'poster_preview', 'is_active', 'start_date', 'end_date', 'sort_order')
    list_filter = ('is_active', 'theme', 'start_date', 'end_date')
    search_fields = ('title', 'subtitle', 'badge_text', 'discount_code')
    list_editable = ('is_active', 'sort_order')
    readonly_fields = ('poster_preview', 'created_at')
    fieldsets = (
        ('اطلاعات مناسبت و پوستر', {
            'fields': ('title', 'subtitle', 'badge_text', 'theme', 'poster_image', 'poster_preview')
        }),
        ('تخفیف و دکمه اقدام (Call to Action)', {
            'fields': ('discount_code', 'discount_percent', 'button_text', 'button_link')
        }),
        ('زمان‌بندی و وضعیت انتشار', {
            'fields': ('is_active', 'sort_order', 'start_date', 'end_date', 'created_at')
        }),
    )

    def poster_preview(self, obj):
        if obj.poster_image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 100px; border-radius: 6px; object-fit: cover;" />', obj.poster_image.url)
        return '—'
    poster_preview.short_description = 'پیش‌نمایش تصویر'


class ProductStoryPageInline(admin.StackedInline):
    model = ProductStoryPage
    extra = 0
    min_num = 1
    autocomplete_fields = ('product',)
    fields = ('product', 'chapter_title', 'hour_label', 'note', 'valley', 'sort_order')
    ordering = ('sort_order', 'id')


@admin.register(ProductStoryBook)
class ProductStoryBookAdmin(admin.ModelAdmin):
    list_display = ('title', 'page_count', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'subtitle', 'pages__product__name')
    inlines = (ProductStoryPageInline,)

    @admin.display(description='تعداد صفحات')
    def page_count(self, obj):
        return obj.pages.count()

