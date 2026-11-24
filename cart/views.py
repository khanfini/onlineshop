import json
import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.db import transaction
from django.db.models import Q
from django.dispatch import receiver
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from products.models import CartItem, Product, ProductVariant, ShoppingCart


COUPON_SESSION_KEYS = (
    'coupon', 'coupon_id', 'coupon_code', 'cart_coupon',
    'cart_coupon_id', 'cart_coupon_code', 'discount', 'discount_amount',
)


class CartError(ValueError):
    """A validation error that can safely be shown to the shopper."""


def _positive_int(value, *, field='quantity', default=None):
    if value in (None, '') and default is not None:
        return default
    if isinstance(value, bool):
        raise CartError('مقدار وارد شده معتبر نیست.')
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        raise CartError('مقدار وارد شده معتبر نیست.') from None
    if parsed < 1:
        raise CartError('تعداد باید حداقل ۱ باشد.' if field == 'quantity' else 'شناسه معتبر نیست.')
    return parsed


def _current_cart_queryset(request, session_key):
    owner_filter = Q(session_key=session_key, user__isnull=True)
    if request.user.is_authenticated:
        owner_filter |= Q(user=request.user)
    return ShoppingCart.objects.filter(owner_filter).order_by('-updated_at', '-created_at')


def _recalculate_cart(cart):
    """Recalculate item totals, including after bulk deletes."""
    cart.recalculate_totals()
    cart.refresh_from_db(fields=['subtotal', 'total'])


def _merge_cart_items(source, destination):
    """Merge without discarding guest items; no stock is reserved by a cart."""
    source_items = list(source.items.select_related('product', 'variant').order_by('created_at', 'pk'))
    for source_item in source_items:
        matching = list(destination.items.filter(
            product=source_item.product,
            variant=source_item.variant,
        ).order_by('created_at', 'pk'))
        if matching:
            target = matching[0]
            target.quantity += source_item.quantity
            target.save()
            for duplicate in matching[1:] + [source_item]:
                duplicate.delete()
        else:
            # Re-save through the existing model logic to capture current prices.
            source_item.cart = destination
            source_item.save()
    _recalculate_cart(destination)


def _consolidate_carts(carts, *, user=None, session_key=None):
    carts = list(carts)
    if not carts:
        return None
    destination = carts[0]
    changed = False
    if user is not None and destination.user_id != user.pk:
        destination.user = user
        changed = True
    if session_key is not None and destination.session_key != session_key:
        destination.session_key = session_key
        changed = True
    if changed:
        destination.save(update_fields=['user', 'session_key', 'updated_at'])
    for duplicate in carts[1:]:
        _merge_cart_items(duplicate, destination)
        duplicate.delete()
    _recalculate_cart(destination)
    return destination


def get_current_cart(request, *, create=False):
    """Return one cart, repairing legacy duplicate carts for this owner."""
    if not request.session.session_key:
        if not create:
            return None
        request.session.create()
    session_key = request.session.session_key

    with transaction.atomic():
        carts = list(_current_cart_queryset(request, session_key).select_for_update())
        if carts:
            return _consolidate_carts(
                carts,
                user=request.user if request.user.is_authenticated else None,
                session_key=session_key,
            )
        if not create:
            return None
        return ShoppingCart.objects.create(
            id=str(uuid.uuid4()),
            session_key=session_key,
            user=request.user if request.user.is_authenticated else None,
            total=0,
        )


def get_owned_cart_item(request, item_id):
    item_id = _positive_int(item_id, field='cart_item_id')
    item = get_object_or_404(
        CartItem.objects.select_related('cart', 'product', 'variant'),
        pk=item_id,
    )
    cart = get_current_cart(request)
    if cart is None or item.cart_id != cart.pk:
        raise CartError('این آیتم در سبد خرید شما وجود ندارد.')
    return item


def cart_item_count(cart):
    if cart is None:
        return 0
    return sum(cart.items.values_list('quantity', flat=True))


def _stock_error(product, stock):
    if stock == 0:
        return CartError(f'«{product.name}» در حال حاضر موجود نیست.')
    return CartError(f'از «{product.name}» فقط {stock} عدد موجود است.')


def validate_purchasable(product, variant=None):
    if not product.is_active or product.status != 'active':
        raise CartError('این محصول در حال حاضر قابل خرید نیست.')
    if variant is not None:
        if variant.product_id != product.pk:
            raise CartError('واریانت انتخاب شده متعلق به این محصول نیست.')
        if variant.status != 'active':
            raise CartError('واریانت انتخاب شده در حال حاضر قابل خرید نیست.')
        if variant.track_inventory and variant.stock < 1:
            raise _stock_error(product, 0)
    elif product.track_inventory and product.stock < 1:
        raise _stock_error(product, 0)


def validate_quantity(cart, product, variant, quantity, *, exclude_item=None):
    """Check the requested row and all rows sharing the same stock pool."""
    validate_purchasable(product, variant)
    stock_item = variant or product
    if not stock_item.track_inventory:
        return

    if variant is not None:
        rows = CartItem.objects.filter(cart=cart, variant=variant)
        stock = variant.stock
    else:
        rows = CartItem.objects.filter(cart=cart, product=product, variant__isnull=True)
        stock = product.stock
    if exclude_item is not None:
        rows = rows.exclude(pk=exclude_item.pk)
    reserved = sum(rows.values_list('quantity', flat=True))
    if reserved + quantity > stock:
        raise _stock_error(product, stock)


def _json_request(request):
    content_type = request.content_type or ''
    return content_type.split(';', 1)[0].strip().lower() == 'application/json'


def _request_data(request):
    if not _json_request(request):
        return request.POST
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CartError('بدنه JSON معتبر نیست.') from None
    if not isinstance(data, dict):
        raise CartError('بدنه JSON باید یک شیء باشد.')
    return data


def _safe_next(request, candidate):
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse('cart_view')


def _cart_json(cart, *, success=True, message=None, status=200, item=None):
    payload = {
        'success': success,
        'cart_count': cart_item_count(cart),
        'count': cart_item_count(cart),
        'cart_items_count': cart_item_count(cart),
        'cart_total': str(cart.total) if cart else '0',
        'cart_subtotal': str(cart.subtotal) if cart else '0',
    }
    if message is not None:
        payload['message' if success else 'error'] = message
    if item is not None:
        payload['item'] = {
            'id': item.pk,
            'product_id': item.product_id,
            'variant_id': item.variant_id,
            'quantity': item.quantity,
            'unit_price': str(item.unit_price),
            'subtotal': str(item.subtotal),
        }
    return JsonResponse(payload, status=status)


@require_GET
def cart_view(request):
    cart = get_current_cart(request)
    items = (
        cart.items.select_related('product', 'variant').order_by('created_at', 'pk')
        if cart else []
    )
    return render(request, 'cart/cart.html', {'cart': cart, 'cart_items': items})


@require_GET
def cart_count(request):
    cart = get_current_cart(request)
    count = cart_item_count(cart)
    return JsonResponse({'success': True, 'count': count, 'cart_count': count, 'cart_items_count': count})


@require_POST
def add_to_cart(request, product_id=None):
    wants_json = _json_request(request)
    try:
        data = _request_data(request)
        raw_product_id = product_id if product_id is not None else data.get('product_id')
        if raw_product_id in (None, ''):
            raise CartError('شناسه محصول الزامی است.')
        product_pk = _positive_int(raw_product_id, field='product_id')
        quantity = _positive_int(data.get('quantity'), default=1)
        raw_variant_id = data.get('variant_id')
        variant_pk = _positive_int(raw_variant_id, field='variant_id') if raw_variant_id not in (None, '') else None

        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=product_pk)
            variant = (
                get_object_or_404(ProductVariant.objects.select_for_update(), pk=variant_pk)
                if variant_pk is not None else None
            )
            validate_purchasable(product, variant)
            if not product.slug:
                raise CartError('این محصول هنوز نشانی معتبر برای خرید ندارد.')
            cart = get_current_cart(request, create=True)
            rows = list(cart.items.select_for_update().filter(
                product=product, variant=variant,
            ).order_by('created_at', 'pk'))
            current_quantity = sum(row.quantity for row in rows)
            validate_quantity(cart, product, variant, current_quantity + quantity)

            if rows:
                item = rows[0]
                item.quantity = current_quantity + quantity
                item.save()
                for duplicate in rows[1:]:
                    duplicate.delete()
                _recalculate_cart(cart)
            else:
                unit_price = variant.price if variant else product.price
                item = CartItem(
                    cart=cart,
                    product=product,
                    variant=variant,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=quantity * unit_price,
                )
                item.save()
    except CartError as exc:
        if wants_json:
            return _cart_json(None, success=False, message=str(exc), status=400)
        messages.error(request, str(exc))
        return redirect(_safe_next(request, request.POST.get('next')))

    message = f'«{product.name}» به سبد خرید اضافه شد.'
    if wants_json:
        return _cart_json(cart, message=message, item=item)
    messages.success(request, message)
    return redirect(_safe_next(request, request.POST.get('next')))


@require_POST
def update_cart_item(request):
    try:
        item = get_owned_cart_item(request, request.POST.get('cart_item_id'))
        quantity = _positive_int(request.POST.get('quantity'), default=1)
        with transaction.atomic():
            item = CartItem.objects.select_for_update().select_related('product', 'variant').get(pk=item.pk)
            validate_quantity(item.cart, item.product, item.variant, quantity, exclude_item=item)
            item.quantity = quantity
            item.save()
    except CartError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'سبد خرید به‌روزرسانی شد.')
    return redirect('cart_view')


@require_POST
def remove_from_cart(request):
    try:
        item = get_owned_cart_item(request, request.POST.get('cart_item_id'))
        cart = item.cart
        item.delete()
        _recalculate_cart(cart)
        messages.success(request, 'آیتم از سبد خرید حذف شد.')
    except CartError as exc:
        messages.error(request, str(exc))
    return redirect('cart_view')


@require_POST
def clear_cart(request):
    cart = get_current_cart(request)
    if cart is not None:
        cart.items.all().delete()
        cart.discount = Decimal('0')
        cart.save(update_fields=['discount', 'updated_at'])
        _recalculate_cart(cart)
    for key in COUPON_SESSION_KEYS:
        request.session.pop(key, None)
    messages.success(request, 'سبد خرید خالی شد.')
    return redirect('cart_view')


def _merge_login_carts(request, user, guest_cart_ids=()):
    """Consolidate the user's carts and a guest cart captured before rotation."""
    if not request.session.session_key:
        return
    session_key = request.session.session_key
    with transaction.atomic():
        carts = list(ShoppingCart.objects.select_for_update().filter(
            Q(pk__in=guest_cart_ids) | Q(session_key=session_key) | Q(user=user)
        ).order_by('-updated_at', '-created_at'))
        if not carts:
            return
        destination = next(
            (cart for cart in carts if str(cart.pk) in {str(pk) for pk in guest_cart_ids}),
            carts[0],
        )
        carts.remove(destination)
        _consolidate_carts(
            [destination] + carts,
            user=user,
            session_key=session_key,
        )


@receiver(user_logged_in, dispatch_uid='cart.merge_guest_cart_on_login')
def merge_guest_cart_on_login(sender, request, user, guest_cart_ids=None, **kwargs):
    """Merge carts when the caller captured the pre-login guest cart IDs."""
    if guest_cart_ids:
        _merge_login_carts(request, user, guest_cart_ids)
