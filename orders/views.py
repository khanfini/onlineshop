from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from cart.views import (
    COUPON_SESSION_KEYS,
    CartError,
    _recalculate_cart,
    get_current_cart,
    validate_purchasable,
)
from products.models import Order, OrderItem, Product, ProductVariant, ShoppingCart

from .forms import CheckoutForm


GUEST_ORDERS_SESSION_KEY = 'guest_order_ids'


def _initial_checkout_data(user):
    if not user.is_authenticated:
        return {}
    full_name = user.get_full_name().strip() or user.username
    return {'full_name': full_name, 'email': user.email}


def _create_order(request, form):
    cart = get_current_cart(request)
    if cart is None:
        raise CartError('سبد خرید شما خالی است.')

    with transaction.atomic():
        # Lock the cart rows and all purchasable objects before checking stock.
        locked_cart = ShoppingCart.objects.select_for_update().get(pk=cart.pk)
        cart_items = list(
            locked_cart.items.select_for_update()
            .select_related('product', 'variant')
            .order_by('created_at', 'pk')
        )
        if not cart_items:
            raise CartError('سبد خرید شما خالی است.')

        product_ids = {item.product_id for item in cart_items}
        variant_ids = {item.variant_id for item in cart_items if item.variant_id}
        products = {
            product.pk: product
            for product in Product.objects.select_for_update().filter(pk__in=product_ids)
        }
        variants = {
            variant.pk: variant
            for variant in ProductVariant.objects.select_for_update().filter(pk__in=variant_ids)
        }

        # Aggregate duplicate product/variant rows before validating and decrementing.
        aggregated = {}
        for item in cart_items:
            key = (item.product_id, item.variant_id)
            stock_key = ('variant', item.variant_id) if item.variant_id else ('product', item.product_id)
            if stock_key not in aggregated:
                aggregated[stock_key] = {
                    'product': products.get(item.product_id),
                    'variant': variants.get(item.variant_id) if item.variant_id else None,
                    'quantity': 0,
                    'discount': Decimal('0'),
                    'weight': None,
                }
            line = aggregated[stock_key]
            if line['product'].pk != item.product_id:
                raise CartError('اطلاعات سبد خرید هماهنگ نیست. لطفاً سبد را دوباره بررسی کنید.')
            if item.discount < 0:
                raise CartError('تخفیف نامعتبر در سبد خرید وجود دارد.')
            line['quantity'] += item.quantity
            line['discount'] += item.discount

        for line in aggregated.values():
            product = line['product']
            variant = line['variant']
            if product is None:
                raise CartError('یکی از محصولات سبد خرید دیگر وجود ندارد.')
            validate_purchasable(product, variant)
            stock_item = variant or product
            if stock_item.track_inventory and line['quantity'] > stock_item.stock:
                raise CartError(f'موجودی «{product.name}» برای تعداد درخواستی کافی نیست.')
            line['unit_price'] = variant.price if variant else product.price
            line['weight'] = variant.weight if variant else product.weight
            if line['discount'] > line['quantity'] * line['unit_price']:
                raise CartError('تخفیف سبد خرید معتبر نیست. لطفاً سبد را دوباره بررسی کنید.')

        subtotal = sum(
            (
                line['quantity'] * (line['unit_price'] - line['discount'])
                for line in aggregated.values()
            ),
            Decimal('0'),
        )
        tax = max(locked_cart.tax, Decimal('0'))
        shipping = max(locked_cart.shipping, Decimal('0'))
        discount = min(max(locked_cart.discount, Decimal('0')), subtotal)
        total = max(subtotal + tax + shipping - discount, Decimal('0'))
        customer = form.cleaned_data
        guest_info = None
        if not request.user.is_authenticated:
            guest_info = {
                'full_name': customer['full_name'],
                'email': customer['email'],
                'phone': customer['phone'],
            }

        order = Order(
            user=request.user if request.user.is_authenticated else None,
            guest_info=guest_info,
            status='pending',
            payment_status='pending',
            payment_method='cash',
            shipping_address=customer['address'],
            billing_address=customer['address'],
            shipping_city=customer['city'],
            shipping_state=customer['state'],
            subtotal=subtotal,
            tax=tax,
            shipping=shipping,
            discount=discount,
            total=total,
            notes=customer['notes'],
        )
        order.order_number = order.generate_order_number()
        order.save()

        for stock_key, line in aggregated.items():
            product = line['product']
            variant = line['variant']
            order_item = OrderItem(
                order=order,
                product=product,
                variant=variant,
                product_name=product.name,
                product_sku=product.code,
                variant_sku=variant.sku if variant else '',
                quantity=line['quantity'],
                unit_price=line['unit_price'],
                discount=line['discount'],
                subtotal=line['quantity'] * (line['unit_price'] - line['discount']),
                weight=line['weight'],
            )
            # OrderItem.save() snapshots the current product and variant fields.
            order_item.save()
            # Keep immutable checkout values even if model logic later changes.
            if (
                order_item.unit_price != line['unit_price']
                or order_item.subtotal != line['quantity'] * (line['unit_price'] - line['discount'])
            ):
                OrderItem.objects.filter(pk=order_item.pk).update(
                    unit_price=line['unit_price'],
                    subtotal=line['quantity'] * (line['unit_price'] - line['discount']),
                )
                order_item.unit_price = line['unit_price']
                order_item.subtotal = line['quantity'] * (line['unit_price'] - line['discount'])
            stock_item = variant or product
            if stock_item.track_inventory:
                stock_item.stock -= line['quantity']
                stock_item.save(update_fields=['stock', 'updated_at'])

        locked_cart.items.all().delete()
        _recalculate_cart(locked_cart)

    for key in COUPON_SESSION_KEYS:
        request.session.pop(key, None)
    if order.user_id is None:
        guest_order_ids = request.session.get(GUEST_ORDERS_SESSION_KEY, [])
        request.session[GUEST_ORDERS_SESSION_KEY] = [order.pk] + guest_order_ids[:19]
    return order


def checkout(request):
    cart = get_current_cart(request)
    if request.method == 'POST':
        if cart is None or not cart.items.exists():
            messages.error(request, 'سبد خرید شما خالی است.')
            return redirect('cart_view')
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = _create_order(request, form)
            except CartError as exc:
                form.add_error(None, str(exc))
                messages.error(request, str(exc))
            else:
                messages.success(request, 'سفارش ثبت شد؛ پرداخت هنگام تحویل انجام می‌شود.')
                return redirect('order_confirmation', order_number=order.order_number)
    else:
        form = CheckoutForm(initial=_initial_checkout_data(request.user))

    cart_items = (
        cart.items.select_related('product', 'variant').order_by('created_at', 'pk')
        if cart else []
    )
    return render(request, 'orders/checkout.html', {
        'form': form,
        'cart': cart,
        'cart_items': cart_items,
    })


def order_confirmation(request, order_number):
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('items__product', 'items__variant'),
        order_number=order_number,
    )
    if order.user_id is not None:
        if not request.user.is_authenticated or order.user_id != request.user.pk:
            if request.user.is_authenticated:
                return render(request, 'orders/order_detail.html', status=403)
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
    else:
        guest_order_ids = request.session.get(GUEST_ORDERS_SESSION_KEY, [])
        if order.pk not in guest_order_ids:
            return render(request, 'orders/order_detail.html', status=403)
    return render(request, 'orders/order_confirmation.html', {'order': order})


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related('items').order_by('-created_at')
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product', 'items__variant'),
        order_number=order_number,
        user=request.user,
    )
    return render(request, 'orders/order_detail.html', {'order': order})
