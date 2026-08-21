from django.urls import path

from reviews.views import add_review

from . import views

app_name = "restaurants"

urlpatterns = [
    path("", views.home, name="home"),
    path("de-xuat-quan/", views.submit_restaurant, name="submit"),
    path("gioi-thieu/", views.about, name="about"),
    path("quan/<slug:slug>/", views.detail, name="detail"),
    path("quan/<slug:slug>/danh-gia/", add_review, name="add_review"),
]
