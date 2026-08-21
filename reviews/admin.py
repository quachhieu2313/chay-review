from django.contrib import admin

from .models import Review, ReviewImage


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "user", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("restaurant__name", "user__username", "comment")
    inlines = [ReviewImageInline]
