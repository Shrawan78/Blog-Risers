from rest_framework import serializers
from .models import Post, Comment, Category, Tag


class CategorySerializer(serializers.ModelSerializer):
    """Turns a Category into JSON: id, name, slug, description."""

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description']


class TagSerializer(serializers.ModelSerializer):
    """Turns a Tag into JSON: id, name, slug."""

    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class CommentSerializer(serializers.ModelSerializer):
    """A single comment. 'author' is shown as a username but can't be set
    by the client directly — the view fills it in from the logged-in user."""

    author = serializers.ReadOnlyField(source='author.username')

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'parent', 'body', 'is_visible', 'created_at', 'updated_at']
        read_only_fields = ['author']


class PostSerializer(serializers.ModelSerializer):
    """A blog post. Category and tags are shown as readable objects on the
    way out, but category_id is what you send on the way in. read_time and
    comment_count are the same calculated fields your templates use."""

    author = serializers.ReadOnlyField(source='author.username')
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False
    )
    tags = TagSerializer(many=True, read_only=True)
    read_time = serializers.ReadOnlyField()
    comment_count = serializers.ReadOnlyField()

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'author', 'category', 'category_id', 'tags',
            'excerpt', 'body', 'cover_image', 'status', 'is_featured', 'views',
            'read_time', 'comment_count', 'created_at', 'updated_at', 'published_at',
        ]
        read_only_fields = ['slug', 'author', 'views', 'created_at', 'updated_at', 'published_at']