from django.urls import path

from . import views


urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<str:order_number>/', views.order_detail, name='order_detail'),
    path('orders/<str:order_number>/confirmation/', views.order_confirmation, name='order_confirmation'),
]
