from rest_framework import serializers
from .models import EmailLog

class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = '__all__'
        read_only_fields = ('id', 'scheduled_at')