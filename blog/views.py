from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404

from .forms import RegisterForm, PostForm, CommentForm, ProfileForm
from .models import Post, Category, Tag, Comment


def _save_tags(post, raw_tags):
    """Turn the comma-separated tag box into real Tag rows — creating any
    that don't already exist — and attach them to this post."""
    names = [name.strip() for name in raw_tags.split(',') if name.strip()]
    tags = []
    for name in names:
        tag, _ = Tag.objects.get_or_create(name=name)
        tags.append(tag)
    post.tags.set(tags)


def home(request):
    """Show one featured post, a few more reads, the category list, and the
    latest posts underneath. Every section is skipped in the template if
    there is nothing real to put in it — no placeholder posts."""
    published = Post.objects.filter(status='published')

    featured_post = published.filter(is_featured=True).first() or published.first()

    secondary_posts = []
    if featured_post:
        secondary_posts = list(published.exclude(pk=featured_post.pk)[:3])

    categories = Category.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    )

    exclude_ids = [p.pk for p in secondary_posts]
    if featured_post:
        exclude_ids.append(featured_post.pk)
    posts = published.exclude(pk__in=exclude_ids)

    paginator = Paginator(posts, 5)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'home.html', {
        'featured_post': featured_post,
        'secondary_posts': secondary_posts,
        'categories': categories,
        'posts': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
    })


def post_list(request):
    """The Explore page: every published post, with search, category
    filtering, tag filtering, a publish-date range, and sorting — all
    driven by the URL's query string so a filtered view is a shareable link."""
    posts = Post.objects.filter(status='published')

    query = request.GET.get('q')
    if query:
        posts = posts.filter(
            Q(title__icontains=query) |
            Q(author__username__icontains=query) |
            Q(category__name__icontains=query)
        )

    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)

    tag_slug = request.GET.get('tag')
    if tag_slug:
        posts = posts.filter(tags__slug=tag_slug)

    date_from = request.GET.get('date_from')
    if date_from:
        posts = posts.filter(published_at__date__gte=date_from)

    date_to = request.GET.get('date_to')
    if date_to:
        posts = posts.filter(published_at__date__lte=date_to)

    # Filtering by tag can match the same post more than once if a search
    # joins the tags table, so make sure every post only appears once.
    posts = posts.distinct()

    sort = request.GET.get('sort')
    if sort == 'oldest':
        posts = posts.order_by('published_at')
    elif sort == 'popular':
        posts = posts.order_by('-views')
    # "newest" needs no extra ordering — that's already the model's default.

    paginator = Paginator(posts, 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'post_list.html', {
        'posts': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'categories': Category.objects.all(),
        'tags': Tag.objects.all(),
    })


def post_detail(request, slug):
    """A single post: its full body, a paginated list of its comments, and a
    form to add a new one. Also counts a view each time the page is opened."""
    post = get_object_or_404(Post, slug=slug)

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            return redirect('post_detail', slug=post.slug)
    else:
        form = CommentForm()

    Post.objects.filter(pk=post.pk).update(views=post.views + 1)

    all_comments = post.comments.filter(is_visible=True)
    comment_paginator = Paginator(all_comments, 5)
    comments_page = comment_paginator.get_page(request.GET.get('comment_page'))

    return render(request, 'post_detail.html', {
        'post': post,
        'comments': comments_page,
        'comments_page_obj': comments_page,
        'comments_is_paginated': comments_page.has_other_pages(),
        'form': form,
    })


@login_required
def post_create(request):
    """Publish a new post. Only reachable if logged in."""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.status = 'draft' if 'save_draft' in request.POST else 'published'
            post.save()
            _save_tags(post, request.POST.get('tags', ''))
            return redirect('post_detail', slug=post.slug)
    else:
        form = PostForm()

    return render(request, 'post_create.html', {'form': form, 'is_edit': False, 'existing_tags': ''})


@login_required
def post_update(request, slug):
    """Edit an existing post. Only the post's own author can do this."""
    post = get_object_or_404(Post, slug=slug)
    if post.author != request.user:
        messages.error(request, "You can only edit your own posts.")
        return redirect('post_detail', slug=post.slug)

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            _save_tags(post, request.POST.get('tags', ''))
            return redirect('post_detail', slug=post.slug)
    else:
        form = PostForm(instance=post)

    existing_tags = ', '.join(post.tags.values_list('name', flat=True))

    return render(request, 'post_create.html', {
        'form': form, 'is_edit': True, 'post': post, 'existing_tags': existing_tags,
    })


@login_required
def post_delete(request, slug):
    """Delete a post, after a confirmation step. Only the author can do this."""
    post = get_object_or_404(Post, slug=slug)
    if post.author != request.user:
        messages.error(request, "You can only delete your own posts.")
        return redirect('post_detail', slug=post.slug)

    if request.method == 'POST':
        post.delete()
        return redirect('post_list')

    return render(request, 'post_confirm_delete.html', {'post': post})


@login_required
def comment_edit(request, comment_id):
    """Edit a comment. Only the comment's own author can do this."""
    comment = get_object_or_404(Comment, pk=comment_id)
    if comment.author != request.user:
        messages.error(request, "You can only edit your own comments.")
        return redirect('post_detail', slug=comment.post.slug)

    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect('post_detail', slug=comment.post.slug)
    else:
        form = CommentForm(instance=comment)

    return render(request, 'comment_edit.html', {'form': form, 'comment': comment})


@login_required
def comment_delete(request, comment_id):
    """Delete a comment, after a confirmation step. Only the author can do this."""
    comment = get_object_or_404(Comment, pk=comment_id)
    if comment.author != request.user:
        messages.error(request, "You can only delete your own comments.")
        return redirect('post_detail', slug=comment.post.slug)

    if request.method == 'POST':
        slug = comment.post.slug
        comment.delete()
        return redirect('post_detail', slug=slug)

    return render(request, 'comment_confirm_delete.html', {'comment': comment})


def category_list(request):
    """Every category that exists, with a real count of published posts in each one."""
    categories = Category.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    )
    return render(request, 'category_list.html', {'categories': categories})


@login_required
def profile(request):
    """The logged-in user's own profile page and their own posts."""
    posts = Post.objects.filter(author=request.user)
    return render(request, 'profile.html', {'posts': posts})


@login_required
def profile_edit(request):
    """Let the logged-in user update their own bio and avatar."""
    user_profile = request.user.profile
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect('profile')
    else:
        form = ProfileForm(instance=user_profile)

    return render(request, 'profile_edit.html', {'form': form})


def register(request):
    """Create a new account, then log the person straight in."""
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})