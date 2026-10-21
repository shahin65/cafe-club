from django import forms
from django.urls import reverse


class PageHtmlWidget(forms.Textarea):
    def __init__(self, language="fa", *args, **kwargs):
        self.editor_language = language
        attrs = kwargs.setdefault("attrs", {})
        attrs.setdefault("rows", 18)
        attrs.setdefault("class", "vLargeTextField page-html-editor")
        super().__init__(*args, **kwargs)

    class Media:
        js = (
            "https://cdn.jsdelivr.net/npm/tinymce@7.6.1/tinymce.min.js",
            "admin/js/page_html_widget.js",
        )
        css = {"all": ("admin/css/page_html_widget.css",)}

    def render(self, name, value, attrs=None, renderer=None):
        attrs = {} if attrs is None else dict(attrs)
        attrs["data-page-html"] = "1"
        attrs["data-editor-language"] = self.editor_language
        attrs["data-upload-url"] = reverse("scenario_page_image")
        return super().render(name, value, attrs, renderer)
