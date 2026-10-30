from django.contrib import admin
from django.shortcuts import redirect

from assistant.models import AssistantConfig


class AssistantHubAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def changelist_view(self, request, extra_context=None):
        return redirect("assistant_home")


admin.site.register(AssistantConfig, AssistantHubAdmin)
