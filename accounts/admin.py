from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "user",
        "display_name",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "display_name",
    )
    list_filter = ("created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("user",)


from django.contrib.auth.models import Group, User

for model in (User, Group):
    admin.site.get_model_admin(model).ordering = ("-id",)
