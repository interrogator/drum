from urllib.parse import urlparse

from django.conf import settings
from django.db import models
from django.urls import reverse

from mezzanine.core.models import Displayable, Ownable
from mezzanine.core.request import current_request
from mezzanine.generic.fields import RatingField, CommentsField


USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class Chamber(Displayable, Ownable):

    display_name = models.CharField(max_length=200)
    rating = RatingField()
    comments = CommentsField()
    automod = models.CharField(max_length=100)  # dummy for now

    def get_absolute_url(self):
        kwa = {"display_name": self.display_name}
        return reverse("chamber_detail", kwargs=kwa)

    @property
    def domain(self):
        return urlparse(self.url).netloc

    @property
    def url(self):
        if self.slug:
            return self.slug
        return current_request().build_absolute_uri(self.get_absolute_url())
