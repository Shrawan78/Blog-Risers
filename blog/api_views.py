from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    PostSerializer, CommentSerializer, CategorySerializer,
    TagSerializer, RegisterSerializer,
)

from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import Post, Comment, Category, Tag
from .serializers import PostSerializer, CommentSerializer, CategorySerializer, TagSerializer


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Anyone can view (GET, safe methods). Only the object's own author
    is allowed to update or delete it."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class PostViewSet(viewsets.ModelViewSet):
    """Full CRUD for posts: GET /api/posts/, POST /api/posts/,
    GET/PUT/PATCH/DELETE /api/posts/<id>/.
    Supports ?search=, ?category__slug=, ?status=, and ?ordering=."""

    queryset = Post.objects.all().order_by('-published_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category__slug', 'status']
    search_fields = ['title', 'author__username', 'category__name']
    ordering_fields = ['published_at', 'views']

    def perform_create(self, serializer):
        """The logged-in user becomes the post's author automatically —
        the client never sends this field."""
        serializer.save(author=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    """Full CRUD for comments. Supports ?post=<id> to see one post's comments."""

    queryset = Comment.objects.all().order_by('created_at')
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['post']

    def perform_create(self, serializer):
        """The logged-in user becomes the comment's author automatically."""
        serializer.save(author=self.request.user)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only: categories are managed in the admin site, not through the API."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list of every tag currently in use."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    """POST {username, email, password} -> creates a user and returns a
    token, the same way the website's register view logs you in immediately
    after signup."""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'username': user.username}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    """POST {username, password} -> returns a token on success. The client
    is expected to send this token as 'Authorization: Token <key>' on every
    request after this."""
    user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
    if user is None:
        return Response({'detail': 'Invalid username or password.'}, status=400)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'username': user.username})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_api(request):
    """Deletes the caller's token, so it can no longer be used to authenticate."""
    request.user.auth_token.delete()
    return Response(status=204)