from django import forms

from .models import Review

RATING_CHOICES = [(i, f"{i} sao") for i in range(5, 0, -1)]


class ReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(choices=RATING_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={"rows": 4, "class": "form-control", "placeholder": "Món ăn thế nào, không gian ra sao..."}
            ),
        }
