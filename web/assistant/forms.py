from django import forms


class QuestionForm(forms.Form):
    question = forms.CharField(
        label="Votre question métier",
        min_length=3,
        max_length=2_000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Ex. Comment interpréter l’évolution récente du "
                    "surendettement en France ?"
                ),
            }
        ),
    )
