from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

# The built-in User model already handles username, email, password and login.
# We point at it with settings.AUTH_USER_MODEL instead of importing it directly.
User = settings.AUTH_USER_MODEL


class Profile(models.Model):
    """Extra information about a user, plus their role (author or reader)."""

    ROLE_CHOICES = [
        ('reader', 'Reader'),
        ('author', 'Author'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='reader')
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_author(self):
        """Return True if this user is allowed to write and manage posts."""
        return self.role == 'author'

    def __str__(self):
        return f"{self.user} ({self.role})"


class Category(models.Model):
    """A subject a post belongs to, like Culture or Technology. One per post."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        """Build the slug from the name automatically if it was left empty."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    """A small keyword label. A post can have many tags, and a tag many posts."""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        """Build the slug from the name automatically if it was left empty."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Post(models.Model):
    """A blog article written by one author."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    cover_image = models.ImageField(upload_to='covers/', blank=True, null=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', '-published_at']),
        ]

    def save(self, *args, **kwargs):
        """Create a unique slug from the title, and stamp the publish date
        the first time the post is published."""
        if not self.slug:
            base = slugify(self.title)
            slug = base
            count = 2
            # If another post already uses this slug, add -2, -3 ... until unique.
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{count}"
                count += 1
            self.slug = slug
        if self.status == 'published' and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def read_time(self):
        """Estimate minutes to read, assuming about 200 words per minute."""
        return max(1, round(len(self.body.split()) / 200))

    @property
    def comment_count(self):
        """How many comments this post has, replies included."""
        return self.comments.count()

    def __str__(self):
        return self.title


class Comment(models.Model):
    """A comment on a post. If `parent` is set, it is a reply to another comment,
    which is what makes threaded conversations possible."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    body = models.TextField()
    is_visible = models.BooleanField(default=True)  # lets an admin hide a comment
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.post}"


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Whenever a new user signs up, automatically create their Profile."""
    if created:
        Profile.objects.create(user=instance)