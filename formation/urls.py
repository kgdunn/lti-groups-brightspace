from django.conf.urls import url

from . import views

urlpatterns = [
    
    # Base page for instructors and students
    url(r'^$',  views.index,  name='index'),
    
    # Action to take based on XHR POST event:
    url(r'^action/(?P<user_ID>.+)/$', 
        views.process_action,  
        name='process_action'),

]