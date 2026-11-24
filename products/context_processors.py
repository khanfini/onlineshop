from django.db.models import Sum

from .models import ShoppingCart


def storefront(request):
    """Expose only the current visitor's cart quantity to the shared shell."""
    if not hasattr(request, 'session'):
        return {'cart_items_count': 0}
    filters = {'user': request.user} if request.user.is_authenticated else {
        'session_key': request.session.session_key, 'user__isnull': True,
    }
    if not request.user.is_authenticated and not request.session.session_key:
        return {'cart_items_count': 0}
    count = ShoppingCart.objects.filter(**filters).aggregate(
        count=Sum('items__quantity')
    )['count'] or 0
    return {'cart_items_count': count}
