from django.contrib.auth.models import User
from django.contrib.messages import info, error

from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, CreateView, DetailView, TemplateView

from mezzanine.accounts import get_profile_model
from mezzanine.conf import settings
from mezzanine.generic.models import ThreadedComment
from mezzanine.utils.views import paginate

from drum.chambers.forms import ChamberForm
from drum.chambers.models import Chamber
from drum.links.utils import order_by_score
from drum.links.models import Profile


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
        context["object_list"] = paginate(qs, self.request.GET.get("page", 1),
            settings.ITEMS_PER_PAGE, settings.MAX_PAGING_LINKS)
        # Update context_object_name variable
        context_object_name = self.get_context_object_name(context["object_list"])
        context[context_object_name] = context["object_list"]
        context["title"] = self.get_title(context)
        return context


class ChamberView(object):
    """
    List and detail view mixin for links - just defines the correct
    queryset.
    """
    template_name = "links/tag_list.html"

    def get_queryset(self):
        return Chamber.objects.published().select_related(
            "user",
            "user__%s" % USER_PROFILE_RELATED_NAME
        )

    def get_object(self):
        name = self.request.resolver_match.kwargs["chamber"]
        return name


class ChamberList(ChamberView, ScoreOrderingView):
    """
    List view for links, which can be for all users (homepage) or
    a single user (links from user's profile page). Links can be
    order by score (homepage, profile links) or by most recently
    created ("newest" main nav item).
    """

    date_field = "publish_date"
    score_fields = ["rating_sum", "comments_count"]
    template_name = "links/chamber_list.html"
    queryset = Chamber.objects.all()

    def get_title(self, context):
        return "Chambers"  # ?


class ChamberCreate(CreateView):
    """
    Link creation view - assigns the user to the new link, as well
    as setting Mezzanine's ``gen_description`` attribute to ``False``,
    so that we can provide our own descriptions.
    """
    template_name = 'links/link_form.html'
    form_class = ChamberForm
    model = Chamber

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['chamber_or_thread'] = "chamber"
        return context

    def form_valid(self, form):
        cham = form.instance.chamber
        lookup = dict(chamber=cham)
        try:
            chamber = Chamber.objects.get(**lookup)
        except Chamber.DoesNotExist:
            pass
        else:
            error(self.request, "Chamber exists")
            return redirect(chamber)
        profile = Profile.objects.get(user=self.request.user)
        user_balance = profile.balance
        if user_balance < settings.MIN_CHAMBER_BALANCE:
            msg = "Balance ({}) too low to create a chamber. Minimum: {}"
            form = msg.format(user_balance, cham, settings.MIN_CHAMBER_BALANCE)
            error(self.request, form)
            return redirect('/')
        form.instance.user = self.request.user
        form.instance.gen_description = False
        info(self.request, "Chamber created")
        return super(ChamberCreate, self).form_valid(form)


class ChamberDetail(ChamberView, DetailView):
    """
    Link detail view - threaded comments and rating are implemented
    in its template.
    """
    template_name = 'links/link_detail.html'


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


class TagList(TemplateView):
    template_name = "links/tag_list.html"
