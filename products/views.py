import os
from decimal import Decimal, InvalidOperation

from django.conf import settings

from django.contrib import messages
from django.core.mail import mail_managers
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import ContactForm, ReviewForm
from .models import Brand, Category, Product, ProductReview, Tag, CampaignPoster, ProductStoryBook
from django.utils import timezone


def with_card_data(queryset):
    """Annotate what the product card needs to decide between quick-add and choosing an option."""
    return queryset.annotate(
        variant_count=Count('variants', filter=Q(variants__status='active'), distinct=True)
    )


def purchasable_products():
    return Product.objects.filter(status='active', is_active=True).exclude(slug__isnull=True).exclude(slug='')


SHOWCASE_SIZE = 6
SHOWCASE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def hero_showcase():
    """Slides for the hero's 3D product box: real products first, then gallery photos from media/products."""
    products = list(
        purchasable_products().exclude(image='').exclude(image__isnull=True)
        .select_related('category', 'brand').order_by('-is_featured', '-created_at')[:SHOWCASE_SIZE]
    )
    slides = [{'product': product, 'image': product.image.url} for product in products]
    used = {str(product.image) for product in products}
    folder = os.path.join(settings.MEDIA_ROOT, 'products')
    try:
        names = sorted(name for name in os.listdir(folder) if name.lower().endswith(SHOWCASE_EXTENSIONS))
    except OSError:
        names = []
    for name in names:
        if len(slides) >= SHOWCASE_SIZE:
            break
        if f'products/{name}' not in used:
            slides.append({'product': None, 'image': f'{settings.MEDIA_URL}products/{name}'})
    return slides


class ProductListView(ListView):
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.filter(
            status='active', is_active=True
        ).exclude(slug__isnull=True).exclude(slug='').select_related('category', 'brand').prefetch_related('images')

        filters = {
            'category__slug': self.request.GET.get('category'),
            'brand__slug': self.request.GET.get('brand'),
            'tags__slug': self.request.GET.get('tag'),
        }
        for lookup, value in filters.items():
            if value:
                queryset = queryset.filter(**{lookup: value})

        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(descriptions__icontains=search_query)
                | Q(sku__icontains=search_query)
            )

        for lookup, parameter in [('price__gte', 'min_price'), ('price__lte', 'max_price')]:
            value = self.request.GET.get(parameter)
            if value:
                try:
                    amount = Decimal(value)
                    if amount >= 0:
                        queryset = queryset.filter(**{lookup: amount})
                except InvalidOperation:
                    pass

        if self.request.GET.get('discount'):
            queryset = queryset.filter(compare_at_price__gt=F('price'))

        sort_options = {
            'price_low': 'price',
            'price_high': '-price',
            'name': 'name',
            'newest': '-created_at',
        }
        sort_by = self.request.GET.get('sort', 'newest')
        if sort_by == 'featured':
            queryset = queryset.filter(is_featured=True)
        return with_card_data(queryset.order_by(sort_options.get(sort_by, '-created_at')).distinct())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
        context['brands'] = Brand.objects.filter(is_active=True).order_by('name')
        context['tags'] = Tag.objects.filter(
            products__status='active', products__is_active=True
        ).distinct().order_by('name')
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Product.objects.filter(
            status='active', is_active=True
        ).select_related('category', 'brand').prefetch_related('images', 'tags')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        context['product_images'] = product.images.all()
        variants = list(product.variants.filter(status='active').order_by('-is_default', 'id'))
        context['variants'] = variants
        context['default_variant'] = next((item for item in variants if item.is_default), variants[0] if variants else None)
        context['reviews'] = product.reviews.filter(is_approved=True)
        context['related_products'] = with_card_data(
            purchasable_products().filter(category=product.category).exclude(pk=product.pk).select_related('category', 'brand')
        )[:4] if product.category_id else []
        context['is_low_stock'] = product.track_inventory and 0 < product.stock <= product.low_stock_threshold
        return context


class AddReviewView(View):
    http_method_names = ['post']

    def post(self, request):
        if not request.user.is_authenticated:
            messages.info(request, 'برای ثبت دیدگاه ابتدا وارد حساب خود شوید.')
            return redirect('login')
        product = get_object_or_404(Product, pk=request.POST.get('product_id'), status='active', is_active=True)
        if not product.slug:
            messages.error(request, 'امکان ثبت دیدگاه برای این محصول وجود ندارد.')
            return redirect('product_list')
        form = ReviewForm(request.POST)
        if form.is_valid():
            ProductReview.objects.create(
                product=product,
                user_name=request.user.get_full_name() or request.user.username,
                user_email=request.user.email,
                rating=form.cleaned_data['rating'],
                title=form.cleaned_data['title'],
                content=form.cleaned_data['content'],
                is_approved=False,
                is_verified_purchase=product.order_items.filter(order__user=request.user, order__payment_status='paid').exists(),
            )
            messages.success(request, 'دیدگاه شما ثبت شد و پس از بررسی نمایش داده می‌شود.')
        else:
            messages.error(request, 'لطفاً امتیاز، عنوان و متن دیدگاه را کامل وارد کنید.')
        return redirect('product_detail', slug=product.slug)


class HomeView(ListView):
    model = Product
    template_name = 'home.html'
    context_object_name = 'products'

    def get_queryset(self):
        return with_card_data(purchasable_products().select_related('category', 'brand').order_by('-created_at'))[:8]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        active_campaigns = list(CampaignPoster.objects.filter(
            is_active=True
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now)
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        ).order_by('sort_order', '-created_at'))

        context['active_campaign'] = active_campaigns[0] if active_campaigns else None
        context['all_campaigns'] = active_campaigns

        context['story_book'] = ProductStoryBook.objects.filter(
            is_active=True, pages__isnull=False
        ).prefetch_related('pages__product__category', 'pages__product__brand').distinct().first()

        featured = list(with_card_data(
            purchasable_products().filter(is_featured=True).select_related('category', 'brand').order_by('-created_at')
        )[:8])
        context['featured_products'] = featured
        context['sale_products'] = list(with_card_data(
            purchasable_products().filter(compare_at_price__gt=F('price')).select_related('category', 'brand').order_by('-created_at')
        )[:4])

        live = purchasable_products().filter(category=OuterRef('pk'))
        context['categories'] = Category.objects.filter(is_active=True).annotate(
            live_count=Count('products', filter=Q(
                products__status='active', products__is_active=True, products__slug__isnull=False,
            ) & ~Q(products__slug=''), distinct=True),
            cover=Subquery(live.exclude(image='').exclude(image__isnull=True).order_by('-is_featured', '-created_at').values('image')[:1]),
        ).filter(live_count__gt=0).order_by('sort_order', 'name')[:8]
        context['hero_showcase'] = hero_showcase()
        context['hero_product'] = next((product for product in featured if product.image), next((product for product in self.object_list if product.image), None))
        return context


class CategoryListView(ListView):
    model = Category
    template_name = 'products/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by('sort_order', 'name')


class BrandListView(ListView):
    model = Brand
    template_name = 'products/brand_list.html'
    context_object_name = 'brands'

    def get_queryset(self):
        return Brand.objects.filter(is_active=True).order_by('name')


class StaticPageView(View):
    template_name = None
    form_class = None

    def get(self, request):
        return render(request, self.template_name, {'form': self.form_class() if self.form_class else None})

    def post(self, request):
        if not self.form_class:
            return self.get(request)
        form = self.form_class(request.POST)
        if form.is_valid():
            try:
                mail_managers(
                    f"پیام فروشگاه: {form.cleaned_data['subject']}",
                    f"فرستنده: {form.cleaned_data['name']}\nایمیل: {form.cleaned_data['email']}\n\n{form.cleaned_data['message']}",
                )
            except Exception:
                messages.error(request, 'ارسال پیام انجام نشد. اتصال ایمیل فروشگاه را بررسی کنید و دوباره تلاش کنید.')
                return render(request, self.template_name, {'form': form}, status=503)
            messages.success(request, 'پیام شما ارسال شد.')
            return redirect('contact')
        return render(request, self.template_name, {'form': form}, status=400)


class AboutView(StaticPageView):
    template_name = 'products/about.html'


class ContactView(StaticPageView):
    template_name = 'products/contact.html'
    form_class = ContactForm


class PolicyView(StaticPageView):
    def get(self, request):
        policy = request.resolver_match.url_name
        return render(request, 'products/policy.html', {'policy': policy})
