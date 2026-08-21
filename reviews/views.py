from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.validators import validate_image_size
from restaurants.models import Restaurant

from .forms import ReviewForm
from .models import Review, ReviewImage


@login_required
@require_POST
def add_review(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_published=True)

    if Review.objects.filter(restaurant=restaurant, user=request.user).exists():
        messages.error(request, "Bạn đã đánh giá quán này rồi.")
        return redirect(restaurant.get_absolute_url())

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.restaurant = restaurant
        review.user = request.user
        review.save()

        skipped = 0
        for image in request.FILES.getlist("images")[:5]:
            try:
                validate_image_size(image)
            except ValidationError:
                skipped += 1
                continue
            ReviewImage.objects.create(review=review, image=image)

        if skipped:
            messages.warning(request, f"{skipped} ảnh quá dung lượng (>5MB) đã bị bỏ qua.")
        messages.success(request, "Cảm ơn bạn đã đánh giá!")
    else:
        messages.error(request, "Đánh giá chưa hợp lệ, vui lòng kiểm tra lại.")

    return redirect(restaurant.get_absolute_url())
