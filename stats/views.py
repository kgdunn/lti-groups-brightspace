# Our models
from .models import Logging

def get_IP_address(request):
    """
    Returns the visitor's IP address as a string given the Django ``request``.
    """
    # Catchs the case when the user is on a proxy
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if ip == '' or ip.lower() in ('unkown', ):
        ip = request.META.get('REMOTE_ADDR', '')   # User is not on a proxy
    if ip == '' or ip.lower() in ('unkown', ):
        ip = request.META.get('HTTP_X_REAL_IP')
    return ip


def create_hit(request, item=None, action='', user=None, 
               other_info=None, other_info_id=0):
    """
    Given a Django ``request`` object, create an entry in the DB for the hit.

    """
    ip_address = get_IP_address(request)
    ua_string = ''
    if action=='login':
        ua_string = request.META.get('HTTP_USER_AGENT', '')

    try:
        page_hit = Logging(ip_address=ip_address,
                           ua_string=ua_string[0:255],
                           item_name=item._meta.model_name[0:100],
                           item_pk=item.pk,
                           other_info=other_info[0:5000],
                           other_info_id=other_info_id,
                           user=user,                           
                           action=action)

        page_hit.save()
    except Exception:
        pass