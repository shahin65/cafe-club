from django.apps import AppConfig


class AssistantAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "assistant"
    verbose_name = "دستیار هوش مصنوعی"

    def ready(self):
        from assistant.realtime import connect_signals

        connect_signals()
