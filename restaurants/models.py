from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from core.validators import validate_image_size


PROVINCE_CHOICES = [
    ("hcm", "TP. Hồ Chí Minh"),
    ("hanoi", "Hà Nội"),
    ("danang", "Đà Nẵng"),
    ("cantho", "Cần Thơ"),
    ("hue", "Huế"),
    ("khac", "Tỉnh/thành khác"),
]

PRICE_RANGE_CHOICES = [
    ("binh_dan", "Bình dân (dưới 50.000đ)"),
    ("trung_binh", "Trung bình (50.000đ - 150.000đ)"),
    ("cao_cap", "Cao cấp (trên 150.000đ)"),
]


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Restaurant(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    province = models.CharField(max_length=20, choices=PROVINCE_CHOICES, default="hcm")
    address = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    opening_hours = models.CharField(max_length=200, blank=True, help_text="Ví dụ: 06:00 - 21:00 hằng ngày")
    price_range = models.CharField(max_length=20, choices=PRICE_RANGE_CHOICES, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    cover_image = models.ImageField(
        upload_to="restaurants/covers/", blank=True, null=True, validators=[validate_image_size]
    )
    categories = models.ManyToManyField(Category, blank=True, related_name="restaurants")
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="restaurants_added"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Restaurant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("restaurants:detail", kwargs={"slug": self.slug})

    @property
    def average_rating(self):
        agg = self.reviews.aggregate(models.Avg("rating"))
        return agg["rating__avg"] or 0

    @property
    def review_count(self):
        return self.reviews.count()


class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="menu_items")
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, help_text="VNĐ")
    description = models.CharField(max_length=300, blank=True)
    image = models.ImageField(
        upload_to="restaurants/menu_items/", blank=True, null=True, validators=[validate_image_size]
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.restaurant.name}"
