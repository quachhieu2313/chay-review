from django import forms

from .models import Restaurant


class RestaurantSubmitForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = [
            "name", "province", "address", "description", "phone",
            "opening_hours", "price_range", "cover_image", "categories",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "province": forms.Select(attrs={"class": "form-select"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "opening_hours": forms.TextInput(attrs={"class": "form-control"}),
            "price_range": forms.Select(attrs={"class": "form-select"}),
            "cover_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "categories": forms.CheckboxSelectMultiple(),
        }
