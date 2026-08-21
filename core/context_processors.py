from django.conf import settings


def site_settings(request):
    return {
        "GA_MEASUREMENT_ID": settings.GA_MEASUREMENT_ID,
    }
