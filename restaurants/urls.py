from django.urls import path

from reviews.views import add_review

from . import views

app_name = "restaurants"

urlpatterns = [
    path("", views.home, name="home"),
    path("quan/<slug:slug>/", views.detail, name="detail"),
    path("quan/<slug:slug>/danh-gia/", add_review, name="add_review"),
]
