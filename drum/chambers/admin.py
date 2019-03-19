from django.contrib import admin

from mezzanine.core.admin import DisplayableAdmin
from drum.chambers.models import Chamber


class ChamberAdmin(DisplayableAdmin):

    list_display = ("id", "title", "chamber", "status", "publish_date",
                    "user", "comments_count", "rating_sum")
    list_display_links = ("id",)
    list_editable = ("title", "chamber", "status")
    list_filter = ("status", "user__username")
    search_fields = ("title", "chamber", "user__username", "user__email")
    ordering = ("-publish_date",)

    fieldsets = (
        (None, {
            "fields": ("title", "chamber", "status", "publish_date", "user"),
        }),
    )


admin.site.register(Chamber, ChamberAdmin)
