from django.conf.urls import url, include
from django.contrib import admin
from django.conf import settings
urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'', include('formation.urls')),
]
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


