from django.contrib import admin
from .models import Logging
class LoggingAdmin(admin.ModelAdmin):
    list_display =('datetime', 'user', 'action', 'item_pk',
                   'item_name', 'other_info',)
    list_per_page = 5000


admin.site.register(Logging, LoggingAdmin)

