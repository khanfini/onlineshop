import json
from decimal import Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

PERSIAN_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


@register.filter
def persian_number(value):
    return str(value).translate(PERSIAN_DIGITS)


@register.filter
def toman(value):
    try:
        number = Decimal(str(value))
        formatted = f'{number:,.0f}' if number == number.to_integral() else f'{number:,.2f}'
        return formatted.translate(PERSIAN_DIGITS)
    except (InvalidOperation, TypeError, ValueError):
        return value


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    return f'?{query.urlencode()}' if query else '?'


@register.filter
def json_value(value):
    return mark_safe(json.dumps(str(value or ''), ensure_ascii=False).replace('<', '\\u003c'))
