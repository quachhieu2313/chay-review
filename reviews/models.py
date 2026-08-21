from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from restaurants.models import Restaurant


class Review(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["restaurant", "user"], name="one_review_per_user_per_restaurant"),
        ]

    def __str__(self):
        return f"{self.user} - {self.restaurant} ({self.rating}★)"


class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="reviews/photos/")

    def __str__(self):
        return f"Ảnh của review #{self.review_id}"
