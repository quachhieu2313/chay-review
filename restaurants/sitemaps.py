from django.contrib.sitemaps import Sitemap

from .models import Restaurant


class RestaurantSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Restaurant.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at
