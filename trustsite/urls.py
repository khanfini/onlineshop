from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from core.health import health_check
from products.views import (
    AboutView,
    AddReviewView,
    BrandListView,
    CategoryListView,
    ContactView,
    HomeView,
    ProductDetailView,
    ProductListView,
)


def media_file(request, path):
    try:
        uploaded_file = default_storage.open(path, 'rb')
    except (FileNotFoundError, SuspiciousFileOperation, ValueError):
        raise Http404('Media file not found')
    return FileResponse(uploaded_file)


urlpatterns = [
    path('', HomeView.as_view(), name='root_home'),
    path('health/', health_check, name='health_check'),
    path('home/', RedirectView.as_view(pattern_name='root_home', permanent=True), name='home'),
    path('admin/', admin.site.urls),
    path('products/', ProductListView.as_view(), name='product_list'),
    path('product/<slug:slug>/', ProductDetailView.as_view(), name='product_detail'),
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('brands/', BrandListView.as_view(), name='brand_list'),
    path('about/', AboutView.as_view(), name='about'),
    path('contact/', ContactView.as_view(), name='contact'),
    path('review/add/', AddReviewView.as_view(), name='add_review'),
    path('robots.txt', lambda request: HttpResponse('User-agent: *\nDisallow: /admin/\nDisallow: /checkout/\n', content_type='text/plain')),
    path('', include('accounts.urls')),
    path('', include('cart.urls')),
    path('', include('orders.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [re_path(r'^media/(?P<path>.+)$', media_file, name='media_file')]
