from __future__ import unicode_literals

from django.conf.urls import url
from django.contrib.auth.decorators import login_required

from drum.chambers.views import ChamberCreate
from drum.links.views import LinkList


urlpatterns = [
    # url("^$",
    #     ChamberList.as_view(),
    #    name="home"),
    url("^chamber/create/$",
        login_required(ChamberCreate.as_view()),
        name="chamber_create"),
    url("^c(hamber)?/(?P<display_name>.*)/?$",
        LinkList.as_view(),
        name="chamber_view"),
]
