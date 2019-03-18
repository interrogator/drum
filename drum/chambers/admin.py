from django.contrib import admin

from mezzanine.core.admin import DisplayableAdmin
from drum.chambers.models import Chamber


class ChamberAdmin(DisplayableAdmin):

    list_display = ("id", "title", "display_name", "status", "publish_date",
                    "user", "comments_count", "rating_sum")
    list_display_links = ("id",)
    list_editable = ("title", "display_name", "status")
    list_filter = ("status", "user__username")
    search_fields = ("title", "display_name", "user__username", "user__email")
    ordering = ("-publish_date",)

    fieldsets = (
        (None, {
            "fields": ("title", "display_name", "status", "publish_date", "user"),
        }),
    )


admin.site.register(Chamber, ChamberAdmin)
