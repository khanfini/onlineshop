from django.http import HttpResponse


class HealthCheckMiddleware:
    """Respond to Railway's internal health probe before host validation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == '/health/':
            return HttpResponse('OK', content_type='text/plain')
        return self.get_response(request)


def health_check(request):
    """Answer the platform health probe before Django host validation."""
    return HttpResponse('OK', content_type='text/plain')
