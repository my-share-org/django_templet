from typing import Dict, List, Optional
from django.apps import apps, AppConfig
from django.conf import settings
from django.db import models


class ModelInspector:
    """
    Django app & model inspection utilities.
    Zero DB hits, safe for production use.
    """

    # -------------------------
    # App-level methods
    # -------------------------
    def get_all_apps(self, app_labels: Optional[List[str]] = None) -> List[AppConfig]:
        """
        Return all installed apps. If app_labels are provided, return only the apps with the given labels.
        """
        if app_labels:
            return [app for app in apps.get_app_configs() if app.label in app_labels]
        return list(apps.get_app_configs())

    # -------------------------
    # Model-level methods
    # -------------------------
    def get_models(
        self,
        app_configs: Optional[List[AppConfig]] = None,
        model_names: Optional[List[str]] = None,
    ) -> List[type[models.Model]]:
        """
        Return all models in the given app configs or installed apps.
        """
        if app_configs:
            if model_names:
                return [model for app in app_configs for model in app.get_models() if model.__name__ in model_names]
            return [model for app in app_configs for model in app.get_models()]
        elif model_names:
            return [model for model in apps.get_models() if model.__name__ in model_names]
        else:
            return list(apps.get_models())

    def get_model_fields(
        self,
        model: type[models.Model] | models.Model,
        field_names: Optional[List[str]] = None,
    ) -> List[models.Field]:
        """
        Return all non-relational fields in the given model.
        """
        if field_names:
            return [field for field in model._meta.get_fields() if not field.is_relation and field.name in field_names]
        return [field for field in model._meta.get_fields() if not field.is_relation]