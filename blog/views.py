from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def home(request):
    return render(request, "home.html")

def post_list(request):
    return render(request, 'post_list.html')  # build this later

def post_detail(request, slug):
    return render(request, 'post_detail.html')  # build this later

def category_list(request):
    return render(request, 'category_list.html')  # build this later

def post_create(request):
    return render(request, 'post_create.html')  # build this later

def profile(request):
    return render(request, 'profile.html')  # build this later

def register(request):
    return render(request, 'register.html') # build this later
