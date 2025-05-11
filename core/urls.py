from django.contrib import admin
from django.urls import path,include
from django.urls import re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from schema_graph.views import Schema
from django.conf import settings
from django.conf.urls.static import static

schema_view = get_schema_view(
   openapi.Info(
      title="Destiny Builder API",
      default_version='v1',
      description="Test description",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@snippets.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    # djoser urls
    path('auth-api/', include('djoser.urls')),
    path('', include('djoser.urls.jwt')),

    #  api endpoints docs
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path("schema/", Schema.as_view()),

    # db sync

    path('api/v1/accounts/', include("mainapps.accounts.api.urls")),
    path('project_api/', include("mainapps.project.api.urls",)),
    path('task_api/', include("mainapps.project_task.api.urls",)),
    path('common_api/', include("mainapps.common.api.urls")),
    path('profile_api/', include("mainapps.user_profile.api.urls")),
]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)