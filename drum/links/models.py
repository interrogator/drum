from operator import ior
from functools import reduce
from decimal import Decimal

from urllib.parse import urlparse

from django.conf import settings
from django.urls import reverse
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible

from mezzanine.accounts import get_profile_model
from mezzanine.core.models import Displayable, Ownable
from mezzanine.core.request import current_request
from mezzanine.generic.models import Rating, Keyword, AssignedKeyword
from mezzanine.generic.fields import RatingField, CommentsField
from mezzanine.utils.importing import import_dotted_path


USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class Link(Displayable, Ownable):

    link = models.URLField(null=True, blank=(not getattr(settings, "LINK_REQUIRED", False)))
    rating = RatingField()
    comments = CommentsField()
    chamber = models.CharField(max_length=200, null=False)

    def get_absolute_url(self):
        kwa = {"slug": self.slug, "chamber": self.chamber}
        return reverse("link_detail", kwargs=kwa)

    @property
    def domain(self):
        return urlparse(self.url).netloc

    @property
    def url(self):
        if self.link:
            return self.link
        return current_request().build_absolute_uri(self.get_absolute_url())

    def save(self, *args, **kwargs):
        keywords = []
        if not self.keywords_string and getattr(settings, "AUTO_TAG", False):
            func_name = getattr(settings, "AUTO_TAG_FUNCTION",
                                "drum.links.utils.auto_tag")
            keywords = import_dotted_path(func_name)(self)
        super(Link, self).save(*args, **kwargs)
        if keywords:
            lookup = reduce(ior, [Q(title__iexact=k) for k in keywords])
            for keyword in Keyword.objects.filter(lookup):
                self.keywords.add(AssignedKeyword(keyword=keyword), bulk=False)


@python_2_unicode_compatible
class Profile(models.Model):

    user = models.OneToOneField(USER_MODEL, on_delete=models.CASCADE)
    website = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    motto = models.TextField(blank=True)
    gender = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    karma = models.IntegerField(default=0, editable=False)
    balance = models.DecimalField(decimal_places=2, default=Decimal('5.00'), max_digits=8)
    total_uo_given = models.IntegerField(default=0, editable=False)
    total_down_given = models.IntegerField(default=0, editable=False)
    total_users_paid = models.IntegerField(default=0, editable=False)

    def __str__(self):
        return "%s (%s)" % (self.user, self.karma)

    def _get_trust(self):
        """
        Each user has a trust rating, based on potentially all kinds of factors

        Return: Decimal between 0 (breivik) and 1 (marx)
        """
        return Decimal('0.5')

    def _normalise_vote(self, amount):
        """
        Normalise an up/downvote based on user history

        DISCUSS: should trust/being a mod influence vote amount
        """
        if amount > 0:
            return amount / (self.total_uo_given / self.total_down_given)
        return amount / (self.total_down_given / self.total_uo_given)


@receiver(post_save, sender=Rating)
@receiver(pre_delete, sender=Rating)
def karma(sender, **kwargs):
    """
    Each time a rating is saved, check its value and modify the
    profile karma for the related object's user accordingly.
    Since ratings are either +1/-1, if a rating is being edited,
    we can assume that the existing rating is in the other direction,
    so we multiply the karma modifier by 2. We also run this when
    a rating is deleted (undone), in which case we just negate the
    rating value from the karma.
    """
    rating = kwargs["instance"]
    value = int(rating.value)
    if "created" not in kwargs:
        value *= -1  #  Rating deleted
    elif not kwargs["created"]:
        value *= 2  #  Rating changed
    content_object = rating.content_object
    if rating.user != content_object.user:
        queryset = get_profile_model().objects.filter(user=content_object.user)
        queryset.update(karma=models.F("karma") + value)
