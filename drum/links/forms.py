from django.forms.models import modelform_factory
from django.forms import ValidationError

from drum.links.models import Link

fields = ["title", "chamber", "link", "description"]
BaseLinkForm = modelform_factory(Link, fields=fields)


class LinkForm(BaseLinkForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['chamber'].widget.attrs['disabled'] = True

    def clean(self):
        link = self.cleaned_data.get("link")
        description = self.cleaned_data.get("description")
        chamber = self.cleaned_data.get("chamber")
        if not chamber:
            raise ValidationError("Chamber required.")
        if not link and not description:
            raise ValidationError("Either a link or description is required")
        return self.cleaned_data
