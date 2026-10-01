"""
Automated tests for Blog Risers.

Covers:
  - Model behaviour (slug generation, auto-profile creation, calculated fields)
  - CRUD views for posts (create, read, update, delete)
  - Permission rules (only an author can edit/delete their own post or comment)
  - Search, category/tag filtering, and pagination
  - The REST API (list, create, and permission checks via DRF's test client)

Run with:
    python manage.py test blog
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Post, Category, Tag, Comment, Profile


class ProfileModelTests(TestCase):
    """Checks the automatic Profile creation that happens on signup."""

    def test_profile_is_created_automatically_for_new_user(self):
        """Creating a User should create exactly one linked Profile, with
        the default 'reader' role, via the post_save signal."""
        user = User.objects.create_user(username='alice', password='testpass123')
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.role, 'reader')


class PostModelTests(TestCase):
    """Checks the custom logic inside Post.save() and its calculated properties."""

    def setUp(self):
        self.author = User.objects.create_user(username='writer', password='testpass123')
        self.category = Category.objects.create(name='Culture')

    def test_slug_is_generated_from_title(self):
        post = Post.objects.create(
            author=self.author, category=self.category,
            title='My First Post', body='Some content here.',
        )
        self.assertEqual(post.slug, 'my-first-post')

    def test_duplicate_titles_get_unique_slugs(self):
        """Two posts with the same title shouldn't collide — the second
        one should get a -2 suffix instead of failing to save."""
        Post.objects.create(author=self.author, title='Same Title', body='First.')
        second = Post.objects.create(author=self.author, title='Same Title', body='Second.')
        self.assertEqual(second.slug, 'same-title-2')

    def test_published_at_is_set_when_status_becomes_published(self):
        post = Post.objects.create(author=self.author, title='Draft Post', body='...', status='draft')
        self.assertIsNone(post.published_at)

        post.status = 'published'
        post.save()
        self.assertIsNotNone(post.published_at)

    def test_published_at_does_not_change_on_later_edits(self):
        """Editing an already-published post again shouldn't reset its
        publish date — only the first publish should set it."""
        post = Post.objects.create(author=self.author, title='Post', body='...', status='published')
        first_published_at = post.published_at

        post.title = 'Post (edited)'
        post.save()
        self.assertEqual(post.published_at, first_published_at)

    def test_read_time_is_calculated_from_word_count(self):
        body = ' '.join(['word'] * 400)  # 400 words at ~200 wpm = 2 minutes
        post = Post.objects.create(author=self.author, title='Long Post', body=body)
        self.assertEqual(post.read_time, 2)

    def test_comment_count_reflects_real_comments(self):
        post = Post.objects.create(author=self.author, title='Post', body='...', status='published')
        self.assertEqual(post.comment_count, 0)

        Comment.objects.create(post=post, author=self.author, body='Nice post!')
        self.assertEqual(post.comment_count, 1)


class PostViewTests(TestCase):
    """CRUD operations and permission rules, exercised through the real URLs."""

    def setUp(self):
        self.author = User.objects.create_user(username='author1', password='testpass123')
        self.other_user = User.objects.create_user(username='other1', password='testpass123')
        self.category = Category.objects.create(name='Technology')
        self.post = Post.objects.create(
            author=self.author, category=self.category,
            title='Existing Post', body='Original content.', status='published',
        )

    # --- Read ---

    def test_home_page_loads(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_post_detail_increments_view_count(self):
        self.assertEqual(self.post.views, 0)
        self.client.get(reverse('post_detail', args=[self.post.slug]))
        self.post.refresh_from_db()
        self.assertEqual(self.post.views, 1)

    def test_draft_post_still_reachable_by_direct_link(self):
        """A draft isn't hidden by a 404 — it's just excluded from public
        listings. The author (or anyone with the link) can still open it."""
        draft = Post.objects.create(author=self.author, title='Draft', body='...', status='draft')
        response = self.client.get(reverse('post_detail', args=[draft.slug]))
        self.assertEqual(response.status_code, 200)

    # --- Create ---

    def test_post_create_requires_login(self):
        """An anonymous visitor hitting the write page should be redirected
        to the login page, not allowed to see the form."""
        response = self.client.get(reverse('post_create'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_logged_in_user_can_create_post(self):
        self.client.login(username='author1', password='testpass123')
        response = self.client.post(reverse('post_create'), {
            'title': 'Brand New Post',
            'category': self.category.id,
            'excerpt': '',
            'body': 'Some new content.',
            'status': 'published',
            'tags': 'django, testing',
        })
        self.assertEqual(response.status_code, 302)
        new_post = Post.objects.get(title='Brand New Post')
        self.assertEqual(new_post.author, self.author)
        self.assertEqual(set(new_post.tags.values_list('name', flat=True)), {'django', 'testing'})

    # --- Update ---

    def test_author_can_edit_their_own_post(self):
        self.client.login(username='author1', password='testpass123')
        response = self.client.post(reverse('post_update', args=[self.post.slug]), {
            'title': 'Updated Title',
            'category': self.category.id,
            'excerpt': '',
            'body': 'Updated content.',
            'status': 'published',
            'tags': '',
        })
        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Updated Title')

    def test_other_user_cannot_edit_someone_elses_post(self):
        """This is the core role-based access rule: being logged in isn't
        enough, you must also be the post's author."""
        self.client.login(username='other1', password='testpass123')
        response = self.client.post(reverse('post_update', args=[self.post.slug]), {
            'title': 'Hijacked Title',
            'body': 'Hijacked content.',
            'status': 'published',
            'tags': '',
        })
        self.post.refresh_from_db()
        self.assertNotEqual(self.post.title, 'Hijacked Title')
        self.assertEqual(response.status_code, 302)  # redirected away, not allowed through

    # --- Delete ---

    def test_delete_requires_post_method(self):
        """Visiting the delete link with GET should only show a confirmation
        page — it must not delete anything until POST is sent."""
        self.client.login(username='author1', password='testpass123')
        self.client.get(reverse('post_delete', args=[self.post.slug]))
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_author_can_delete_their_own_post(self):
        self.client.login(username='author1', password='testpass123')
        self.client.post(reverse('post_delete', args=[self.post.slug]))
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_other_user_cannot_delete_someone_elses_post(self):
        self.client.login(username='other1', password='testpass123')
        self.client.post(reverse('post_delete', args=[self.post.slug]))
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())


class SearchFilterPaginationTests(TestCase):
    """Explore page: search, category/tag filtering, and pagination."""

    def setUp(self):
        self.author = User.objects.create_user(username='writer2', password='testpass123')
        self.culture = Category.objects.create(name='Culture')
        self.tech = Category.objects.create(name='Technology')
        self.tag_django = Tag.objects.create(name='django')

        self.post_a = Post.objects.create(
            author=self.author, category=self.culture,
            title='A Culture Post', body='...', status='published',
        )
        self.post_a.tags.add(self.tag_django)

        self.post_b = Post.objects.create(
            author=self.author, category=self.tech,
            title='A Technology Post', body='...', status='published',
        )

    def test_search_matches_title(self):
        response = self.client.get(reverse('post_list'), {'q': 'Culture'})
        titles = [p.title for p in response.context['posts']]
        self.assertIn('A Culture Post', titles)
        self.assertNotIn('A Technology Post', titles)

    def test_filter_by_category(self):
        response = self.client.get(reverse('post_list'), {'category': self.tech.slug})
        titles = [p.title for p in response.context['posts']]
        self.assertEqual(titles, ['A Technology Post'])

    def test_filter_by_tag(self):
        response = self.client.get(reverse('post_list'), {'tag': self.tag_django.slug})
        titles = [p.title for p in response.context['posts']]
        self.assertEqual(titles, ['A Culture Post'])

    def test_pagination_splits_results_across_pages(self):
        """6 posts per page — create enough posts to force a second page."""
        for i in range(10):
            Post.objects.create(author=self.author, title=f'Filler Post {i}', body='...', status='published')

        response = self.client.get(reverse('post_list'))
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['posts']), 6)


class CommentViewTests(TestCase):
    """Create, edit, delete, and pagination for comments."""

    def setUp(self):
        self.author = User.objects.create_user(username='poster', password='testpass123')
        self.commenter = User.objects.create_user(username='commenter', password='testpass123')
        self.other_user = User.objects.create_user(username='rando', password='testpass123')
        self.post = Post.objects.create(author=self.author, title='Post', body='...', status='published')

    def test_anonymous_user_cannot_comment(self):
        response = self.client.post(reverse('post_detail', args=[self.post.slug]), {'body': 'Nice!'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.post.comments.count(), 0)

    def test_logged_in_user_can_comment(self):
        self.client.login(username='commenter', password='testpass123')
        self.client.post(reverse('post_detail', args=[self.post.slug]), {'body': 'Nice post!'})
        self.assertEqual(self.post.comments.count(), 1)
        self.assertEqual(self.post.comments.first().author, self.commenter)

    def test_only_comment_author_can_edit_it(self):
        comment = Comment.objects.create(post=self.post, author=self.commenter, body='Original.')

        self.client.login(username='rando', password='testpass123')
        self.client.post(reverse('comment_edit', args=[comment.id]), {'body': 'Hijacked.'})
        comment.refresh_from_db()
        self.assertEqual(comment.body, 'Original.')

        self.client.login(username='commenter', password='testpass123')
        self.client.post(reverse('comment_edit', args=[comment.id]), {'body': 'Edited by owner.'})
        comment.refresh_from_db()
        self.assertEqual(comment.body, 'Edited by owner.')

    def test_only_comment_author_can_delete_it(self):
        comment = Comment.objects.create(post=self.post, author=self.commenter, body='Delete me.')

        self.client.login(username='rando', password='testpass123')
        self.client.post(reverse('comment_delete', args=[comment.id]))
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

        self.client.login(username='commenter', password='testpass123')
        self.client.post(reverse('comment_delete', args=[comment.id]))
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_comments_are_paginated(self):
        """5 comments per page — create enough to force a second page."""
        for i in range(7):
            Comment.objects.create(post=self.post, author=self.commenter, body=f'Comment {i}')

        response = self.client.get(reverse('post_detail', args=[self.post.slug]))
        self.assertTrue(response.context['comments_is_paginated'])
        self.assertEqual(len(response.context['comments']), 5)


class ProfileEditTests(TestCase):
    """Readers managing their own profile."""

    def test_profile_edit_requires_login(self):
        response = self.client.get(reverse('profile_edit'))
        self.assertEqual(response.status_code, 302)

    def test_logged_in_user_can_update_their_bio(self):
        user = User.objects.create_user(username='reader1', password='testpass123')
        self.client.login(username='reader1', password='testpass123')
        self.client.post(reverse('profile_edit'), {'bio': 'I love reading about culture.'})
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.bio, 'I love reading about culture.')


class RegistrationTests(TestCase):
    """Sign-up flow."""

    def test_register_creates_user_and_logs_them_in(self):
        response = self.client.post(reverse('register'), {
            'username': 'newperson',
            'email': 'new@example.com',
            'password1': 'SuperStrongPass123',
            'password2': 'SuperStrongPass123',
        })
        self.assertTrue(User.objects.filter(username='newperson').exists())
        # A redirect to home (rather than back to the form) means login succeeded.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))


class PostAPITests(APITestCase):
    """The REST API: listing, creating, and the same ownership rules as the website."""

    def setUp(self):
        self.author = User.objects.create_user(username='apiauthor', password='testpass123')
        self.other_user = User.objects.create_user(username='apiother', password='testpass123')
        self.category = Category.objects.create(name='Science')
        self.post = Post.objects.create(
            author=self.author, category=self.category,
            title='API Post', body='Content.', status='published',
        )

    def test_list_posts_does_not_require_login(self):
        response = self.client.get('/api/posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_post_requires_login(self):
        response = self.client.post('/api/posts/', {'title': 'No Auth Post', 'body': 'Should fail.'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logged_in_user_can_create_post_via_api(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post('/api/posts/', {
            'title': 'Created via API', 'body': 'Content here.', 'status': 'published',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Post.objects.get(title='Created via API')
        self.assertEqual(created.author, self.author)  # set by the view, not the client

    def test_other_user_cannot_update_post_via_api(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(f'/api/posts/{self.post.id}/', {'title': 'Hijacked via API'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.post.refresh_from_db()
        self.assertNotEqual(self.post.title, 'Hijacked via API')

    def test_author_can_update_own_post_via_api(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(f'/api/posts/{self.post.id}/', {'title': 'Updated via API'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Updated via API')