from __future__ import unicode_literals
from future.builtins import super

from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.messages import info, error

from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now
from django.views.generic import ListView, CreateView, DetailView, TemplateView

from mezzanine.accounts import get_profile_model
from mezzanine.conf import settings
from mezzanine.generic.models import ThreadedComment, Keyword
from mezzanine.utils.views import paginate
from mezzanine.utils.automod import get_automod_scores, score_below_threshold

from drum.links.forms import LinkForm
from drum.links.models import Link, Profile
from drum.links.utils import order_by_score
from drum.chambers.models import Chamber


# Returns the name to be used for reverse profile lookups from the user
# object. That's "profile" for the ``drum.links.Profile``, but otherwise
# depends on the model specified in ``AUTH_PROFILE_MODULE``.
USER_PROFILE_RELATED_NAME = get_profile_model().user.field.related_query_name()


class UserFilterView(ListView):
    """
    List view that puts a ``profile_user`` variable into the context,
    which is optionally retrieved by a ``username`` urlpattern var.
    If a user is loaded, ``object_list`` is filtered by the loaded
    user. Used for showing lists of links and comments.
    """

    def get_context_data(self, **kwargs):
        context = super(UserFilterView, self).get_context_data(**kwargs)
        try:
            username = self.kwargs["username"]
        except KeyError:
            profile_user = None
        else:
            users = User.objects.select_related(USER_PROFILE_RELATED_NAME)
            lookup = {"username__iexact": username, "is_active": True}
            profile_user = get_object_or_404(users, **lookup)
            qs = context["object_list"].filter(user=profile_user)
            context["object_list"] = qs
            # Update context_object_name variable
            context_object_name = self.get_context_object_name(context["object_list"])
            context[context_object_name] = context["object_list"]

        context["profile_user"] = profile_user
        context["no_data"] = "No posts to display (yet)."
        return context


class ScoreOrderingView(UserFilterView):
    """
    List view that optionally orders ``object_list`` by calculated
    score. Subclasses must defined a ``date_field`` attribute for the
    related model, that's used to determine time-scaled scoring.
    Ordering by score is the default behaviour, but can be
    overridden by passing ``False`` to the ``by_score`` arg in
    urlpatterns, in which case ``object_list`` is sorted by most
    recent, using the ``date_field`` attribute. Used for showing lists
    of links and comments.
    """

    def get_context_data(self, **kwargs):
        context = super(ScoreOrderingView, self).get_context_data(**kwargs)
        qs = context["object_list"]
        context["by_score"] = self.kwargs.get("by_score", True)
        if context["by_score"]:
            qs = order_by_score(qs, self.score_fields, self.date_field)
        else:
            qs = qs.order_by("-" + self.date_field)
        page = self.request.GET.get("page", 1)
        items = settings.ITEMS_PER_PAGE
        max_page = settings.MAX_PAGING_LINKS
        context["object_list"] = paginate(qs, page, items, max_page)
        # Update context_object_name variable
        context_object_name = self.get_context_object_name(context["object_list"])
        context[context_object_name] = context["object_list"]
        context["title"] = self.get_title(context)
        return context


class LinkView(object):
    """
    List and detail view mixin for links - just defines the correct
    queryset.
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['chamber'] = self.kwargs.get("chamber", "")
        return context

    def get_queryset(self, chamber=None):
        user_rel = "user__%s" % USER_PROFILE_RELATED_NAME
        links = Link.objects.published().select_related("user", user_rel)
        return links if not chamber else links.filter(chamber=chamber)


class LinkList(LinkView, ScoreOrderingView):
    """
    List view for links, which can be for all users (homepage) or
    a single user (links from user's profile page). Links can be
    order by score (homepage, profile links) or by most recently
    created ("newest" main nav item).
    """

    date_field = "publish_date"
    score_fields = ["rating_sum", "comments_count"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chamber = self.kwargs.get("chamber", "")
        context['chamber'] = chamber
        return context

    def get_queryset(self):
        chamber = self.kwargs.get("chamber")
        chamber = dict(chamber=chamber) if chamber else dict()
        queryset = super(LinkList, self).get_queryset(**chamber)
        tag = self.kwargs.get("tag")
        if tag:
            queryset = queryset.filter(keywords__keyword__slug=tag)
        return queryset.prefetch_related("keywords__keyword")

    def get_title(self, context):
        tag = self.kwargs.get("tag")
        if tag:
            return get_object_or_404(Keyword, slug=tag).title
        if context["by_score"]:
            return ""  # Homepage
        if context["profile_user"]:
            return "Links by %s" % getattr(
                context["profile_user"],
                USER_PROFILE_RELATED_NAME
            )
        else:
            return "Newest"


class LinkCreate(CreateView):
    """
    Link creation view - assigns the user to the new link, as well
    as setting Mezzanine's ``gen_description`` attribute to ``False``,
    so that we can provide our own descriptions.
    """
    def __init__(self):
        super().__init__()

    form_class = LinkForm
    model = Link

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['chamber'] = self.kwargs.get("chamber", "")
        context['chamber_or_thread'] = "thread"
        return context

        return context

    def get_initial(self):
        # initial = super().get_initial()
        chamber = self.kwargs.get("chamber")
        return {'chamber': chamber}

    def form_valid(self, form):
        hours = getattr(settings, "ALLOWED_DUPLICATE_LINK_HOURS", None)
        chamber = form.instance.chamber
        text = form.instance.description
        profile = Profile.objects.get(user=self.request.user)
        chamber_min = Chamber.objects.get(chamber=chamber).min_thread_balance
        # automod
        scores, automods = get_automod_scores(self.request, chamber, text)
        fail_info = score_below_threshold(scores, automods)
        if fail_info:
            msg = "Failed automoderation:<br><br>{}".format(fail_info)
            error(self.request, msg)
            # todo: fix this url
            return redirect('chamber_view', chamber=chamber)
        user_balance = profile.balance
        if user_balance < chamber_min:
            msg = "Balance ({}) too low to create a thread in '{}'. Minimum: {}"
            formed = msg.format(user_balance, chamber, chamber_min)
            error(self.request, formed)
            # todo: fix this url
            return redirect('chamber_view', chamber=chamber)

        if hours and form.instance.link:
            lookup = dict(link=form.instance.link,
                          chamber=chamber,
                          publish_date__gt=now()-timedelta(hours=hours))
            try:
                link = Link.objects.get(**lookup)
            except Link.DoesNotExist:
                pass
            else:
                error(self.request, "Link exists")
                return redirect(link)
        form.instance.user = self.request.user
        form.instance.gen_description = False
        info(self.request, "Link created")
        return super(LinkCreate, self).form_valid(form)


class LinkDetail(LinkView, DetailView):
    """
    Link detail view - threaded comments and rating are implemented
    in its template.
    """
    pass


class CommentList(ScoreOrderingView):
    """
    List view for comments, which can be for all users ("comments" and
    "best" main nav items) or a single user (comments from user's
    profile page). Comments can be order by score ("best" main nav item)
    or by most recently created ("comments" main nav item, profile
    comments).
    """

    date_field = "submit_date"
    score_fields = ["rating_sum"]

    def get_queryset(self):
        qs = ThreadedComment.objects.filter(is_removed=False, is_public=True)
        select = ["user", "user__%s" % (USER_PROFILE_RELATED_NAME)]
        prefetch = ["content_object"]
        return qs.select_related(*select).prefetch_related(*prefetch)

    def get_title(self, context):
        if context["profile_user"]:
            return "Comments by %s" % getattr(
                context["profile_user"],
                USER_PROFILE_RELATED_NAME
            )
        elif context["by_score"]:
            return "Best comments"
        else:
            return "Latest comments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['chamber'] = self.kwargs.get("chamber", "")
        return context


class TagList(TemplateView):
    template_name = "links/tag_list.html"
