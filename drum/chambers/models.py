from urllib.parse import urlparse
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from mezzanine.core.models import Displayable, Ownable
from mezzanine.core.request import current_request
from mezzanine.generic.fields import RatingField, CommentsField

USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')

AUTOMOD = dict(blank=True,
               max_length=100)

SEVERITY = dict(max_digits=3,
                decimal_places=2,
                default=Decimal('0'))

BALANCE = dict(decimal_places=2,
               default=Decimal('0'),
               max_digits=8)


class Chamber(Displayable, Ownable):

    chamber = models.CharField(max_length=200)
    rating = RatingField()
    comments = CommentsField()
    balance = models.DecimalField(**BALANCE)
    min_thread_balance = models.DecimalField(**BALANCE)
    min_comment_balance = models.DecimalField(**BALANCE)
    automod_can_fine = models.BooleanField(default=False)
    max_fine = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0'))

    # ugly automod stuff...
    automod_a = models.CharField(**AUTOMOD)
    automod_b = models.CharField(**AUTOMOD)
    automod_c = models.CharField(**AUTOMOD)
    automod_d = models.CharField(**AUTOMOD)
    automod_e = models.CharField(**AUTOMOD)
    severity_a = models.DecimalField(**SEVERITY)
    severity_b = models.DecimalField(**SEVERITY)
    severity_c = models.DecimalField(**SEVERITY)
    severity_d = models.DecimalField(**SEVERITY)
    severity_e = models.DecimalField(**SEVERITY)

    def _automod_config(self):
        """
        Helper to get/format automod config for this chamber
        """
        out = dict()
        for char in 'abcde':
            mod = getattr(self, 'automod_{}'.format(char))
            sev = getattr(self, 'severity_{}'.format(char))
            if mod:
                out[mod] = float(sev)
        return out

    def get_absolute_url(self):
        kwa = {"chamber": self.chamber}
        return reverse("chamber_view", kwargs=kwa)

    @property
    def domain(self):
        return urlparse(self.url).netloc

    @property
    def url(self):
        if self.slug:
            return self.slug
        return current_request().build_absolute_uri(self.get_absolute_url())
