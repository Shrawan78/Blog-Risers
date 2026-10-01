from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('posts/', views.post_list, name='post_list'),
    path('posts/<slug:slug>/', views.post_detail, name='post_detail'),
    path('posts/<slug:slug>/edit/', views.post_update, name='post_update'),
    path('posts/<slug:slug>/delete/', views.post_delete, name='post_delete'),
    path('comments/<int:comment_id>/edit/', views.comment_edit, name='comment_edit'),
    path('comments/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
    path('categories/', views.category_list, name='category_list'),
    path('write/', views.post_create, name='post_create'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('register/', views.register, name='register'),
]