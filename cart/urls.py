from django.urls import path

from . import views


urlpatterns = [
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/count/', views.cart_count, name='cart_count'),
    path('api/cart/add/', views.add_to_cart, name='api_add_to_cart'),
    path('api/cart/add/<int:product_id>/', views.add_to_cart, name='api_add_product_to_cart'),
]
