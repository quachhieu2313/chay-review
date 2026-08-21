from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from reviews.forms import ReviewForm
from reviews.models import Review

from .forms import RestaurantSubmitForm
from .models import Category, PROVINCE_CHOICES, Restaurant


def home(request):
    restaurants = (
        Restaurant.objects.filter(is_published=True)
        .annotate(avg_rating=Avg("reviews__rating"), num_reviews=Count("reviews"))
    )

    province = request.GET.get("tinh", "")
    category_slug = request.GET.get("loai", "")
    query = request.GET.get("q", "")

    if province:
        restaurants = restaurants.filter(province=province)
    if category_slug:
        restaurants = restaurants.filter(categories__slug=category_slug)
    if query:
        restaurants = restaurants.filter(Q(name__icontains=query) | Q(address__icontains=query))

    restaurants = restaurants.order_by("-num_reviews", "-created_at")

    paginator = Paginator(restaurants, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "provinces": PROVINCE_CHOICES,
        "categories": Category.objects.all(),
        "selected_province": province,
        "selected_category": category_slug,
        "query": query,
    }
    return render(request, "restaurants/home.html", context)


def detail(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_published=True)
    reviews = restaurant.reviews.select_related("user").prefetch_related("images")

    user_has_reviewed = (
        request.user.is_authenticated
        and Review.objects.filter(restaurant=restaurant, user=request.user).exists()
    )

    context = {
        "restaurant": restaurant,
        "menu_items": restaurant.menu_items.all(),
        "reviews": reviews,
        "review_form": ReviewForm(),
        "user_has_reviewed": user_has_reviewed,
    }
    return render(request, "restaurants/detail.html", context)


@login_required
def submit_restaurant(request):
    if request.method == "POST":
        form = RestaurantSubmitForm(request.POST, request.FILES)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.is_published = False
            restaurant.created_by = request.user
            restaurant.save()
            form.save_m2m()
            messages.success(
                request,
                "Cảm ơn bạn! Quán chay đã được gửi và sẽ hiển thị sau khi được duyệt.",
            )
            return redirect("restaurants:home")
    else:
        form = RestaurantSubmitForm()

    return render(request, "restaurants/submit.html", {"form": form})


def about(request):
    return render(request, "restaurants/about.html")
