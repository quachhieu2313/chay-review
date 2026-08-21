from django.contrib import admin

from .models import Category, MenuItem, Restaurant


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 1


@admin.action(description="Duyệt và hiển thị công khai các quán đã chọn")
def publish_restaurants(modeladmin, request, queryset):
    queryset.update(is_published=True)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "price_range", "is_published", "created_by", "created_at")
    list_filter = ("province", "price_range", "is_published", "categories")
    search_fields = ("name", "address")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MenuItemInline]
    actions = [publish_restaurants]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
