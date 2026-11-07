"""Compatibility fixes for the bundled Summernote Lite assets."""
from django_summernote.apps import DjangoSummernoteConfig


class CatalogSummernoteConfig(DjangoSummernoteConfig):
    def update_config(self):
        super().update_config()
        # 0.8.20 ships only the minified Lite CSS and overwrites settings-level
        # default_css overrides during initialization.
        if self.theme == "lite":
            self.config["default_css"] = (
                "summernote/summernote-lite.min.css",
                "summernote/django_summernote.css",
            )
