from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("dang-ky/", views.register, name="register"),
]
