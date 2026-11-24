from django.http import JsonResponse


def health_check(request):
    """Return a cheap liveness response; migrations run before deployment."""
    return JsonResponse({'status': 'ok'})
