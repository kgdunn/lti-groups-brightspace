from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from formation.models import Person

@python_2_unicode_compatible
class Logging(models.Model):
    """General timing statistics about the site usage are summarized here."""
    action_type = (
                    ('create',         'create'),
                    ('login',          'login'),
                    ('join',           'join'),
                    ('leave',          'leave'),
                    ('waitlist-add',   'waitlist-add'),
                    ('waitlist-left',  'waitlist-left'),
                 )
    action = models.CharField(max_length=80, choices=action_type)
    ua_string = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    datetime = models.DateTimeField(auto_now_add=True)
    
    user = models.ForeignKey(Person, blank=True, null=True)
    item_name = models.CharField(max_length=100, blank=True, null=True)
    item_pk = models.PositiveIntegerField(blank=True, null=True, default=0)
    other_info_id = models.PositiveIntegerField(blank=True, null=True,default=0)
    other_info = models.CharField(max_length=5000, blank=True, null=True,
                                  default=None)

    def __str__(self):
        return '%s [%s]' % (self.action, self.user)


