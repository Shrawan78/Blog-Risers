from rest_framework.routers import DefaultRouter
from .api_views import PostViewSet, CommentViewSet, CategoryViewSet, TagViewSet

router = DefaultRouter()
router.register('posts', PostViewSet, basename='api-post')
router.register('comments', CommentViewSet, basename='api-comment')
router.register('categories', CategoryViewSet, basename='api-category')
router.register('tags', TagViewSet, basename='api-tag')

urlpatterns = router.urls