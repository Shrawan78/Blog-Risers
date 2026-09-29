from django.urls import path
from . import views

urlpatterns = [
    path('', views.home,name='home'),
    path('posts/', views.post_list, name='post_list'),
    path('posts/<slug:slug>/', views.post_detail, name='post_detail'),
    path('categories/', views.category_list, name='category_list'),
    path('write/', views.post_create, name='post_create'),
    path('profile/', views.profile, name='profile'),
    path('register/', views.register, name='register'),
]
