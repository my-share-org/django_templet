from django.db.models import Q

def is_exists(model, **kwargs):
    return model.objects.filter(**kwargs).exists()