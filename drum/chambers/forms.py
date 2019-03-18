from django.forms.models import modelform_factory
from django.forms import ValidationError

from drum.chambers.models import Chamber


fields = ["display_name", "description", "automod"]
BaseChamberForm = modelform_factory(Chamber, fields=fields)


class ChamberForm(BaseChamberForm):

    def clean(self):
        link = self.cleaned_data.get("link")
        description = self.cleaned_data.get("description")
        if not link and not description:
            raise ValidationError("Either a link or description is required")
        return self.cleaned_data
