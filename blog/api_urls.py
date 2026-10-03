from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_views import (
    PostViewSet, CommentViewSet, CategoryViewSet, TagViewSet,
    register_api, login_api, logout_api,
)

router = DefaultRouter()
router.register('posts', PostViewSet, basename='api-post')
router.register('comments', CommentViewSet, basename='api-comment')
router.register('categories', CategoryViewSet, basename='api-category')
router.register('tags', TagViewSet, basename='api-tag')

urlpatterns = [
    path('auth/register/', register_api, name='api-register'),
    path('auth/login/', login_api, name='api-login'),
    path('auth/logout/', logout_api, name='api-logout'),
] + router.urls