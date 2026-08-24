from django import forms


class DashboardFilterForm(forms.Form):
    geographic_level = forms.ChoiceField(label="Niveau géographique")
    geographic_code = forms.ChoiceField(label="Territoire")
    reference_period = forms.ChoiceField(label="Période")
    model_version = forms.ChoiceField(label="Version du modèle")
    comparison_period = forms.ChoiceField(
        label="Période de comparaison",
        required=False,
    )
    comparison_model_version = forms.ChoiceField(
        label="Modèle de comparaison",
        required=False,
    )

    def __init__(self, *args, scores=None, models=None, **kwargs):
        super().__init__(*args, **kwargs)
        scores = scores or []
        models = models or []
        self.scores = scores

        self.fields["geographic_level"].choices = _choices(
            (
                score["geographic_level"],
                _level_label(score["geographic_level"]),
            )
            for score in scores
        )
        self.fields["geographic_code"].choices = [
            (
                level,
                _choices(
                    (
                        score["geographic_code"],
                        score.get("geographic_name") or score["geographic_code"],
                    )
                    for score in scores
                    if score["geographic_level"] == level
                ),
            )
            for level, _label in self.fields["geographic_level"].choices
        ]
        periods = _choices(
            (score["reference_period"], score["reference_period"])
            for score in scores
        )
        self.fields["reference_period"].choices = periods
        self.fields["comparison_period"].choices = [("", "—")] + periods

        versions = _choices(
            (model["version"], f"{model['name']} — {model['version']}")
            for model in models
        )
        self.fields["model_version"].choices = versions
        self.fields["comparison_model_version"].choices = [("", "—")] + versions

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        level = cleaned["geographic_level"]
        code = cleaned["geographic_code"]
        valid_pair = any(
            score["geographic_level"] == level
            and score["geographic_code"] == code
            for score in self.scores
        )
        if self.scores and not valid_pair:
            raise forms.ValidationError(
                "Le territoire ne correspond pas au niveau géographique."
            )
        return cleaned


def dashboard_defaults(scores: list[dict], models: list[dict]) -> dict:
    first_score = scores[0] if scores else {}
    active_model = next(
        (model for model in models if model.get("is_active")),
        models[0] if models else {},
    )
    return {
        "geographic_level": first_score.get("geographic_level", ""),
        "geographic_code": first_score.get("geographic_code", ""),
        "reference_period": first_score.get("reference_period", ""),
        "model_version": active_model.get("version", ""),
        "comparison_period": "",
        "comparison_model_version": "",
    }


def _choices(items) -> list[tuple[str, str]]:
    values = {}
    for value, label in items:
        if value not in (None, ""):
            values[str(value)] = str(label)
    return sorted(values.items(), key=lambda item: item[1])


def _level_label(value: str) -> str:
    return {
        "department": "Département",
        "region": "Région",
    }.get(value, value)
