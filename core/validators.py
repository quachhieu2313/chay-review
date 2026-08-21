from django.core.exceptions import ValidationError

MAX_IMAGE_SIZE_MB = 5


def validate_image_size(image):
    limit = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if image.size > limit:
        raise ValidationError(f"Ảnh không được vượt quá {MAX_IMAGE_SIZE_MB}MB.")
