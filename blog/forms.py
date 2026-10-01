from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Post, Comment, Profile


class RegisterForm(UserCreationForm):
    """Sign-up form. Extends Django's built-in user form to also collect an email."""

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class PostForm(forms.ModelForm):
    """Used for both creating a new post and editing an existing one.
    'status' is deliberately not a form field — it's set directly in the
    view based on which button was clicked (Publish vs Save draft), and
    left untouched on edits. Tags are also handled separately — see
    _save_tags() in views.py."""

    class Meta:
        model = Post
        fields = ['title', 'category', 'excerpt', 'body', 'cover_image']


class CommentForm(forms.ModelForm):
    """A single comment on a post. Also reused for editing an existing comment."""

    class Meta:
        model = Comment
        fields = ['body']


class ProfileForm(forms.ModelForm):
    """Lets a reader or author update their own bio and avatar."""

    class Meta:
        model = Profile
        fields = ['bio', 'avatar']