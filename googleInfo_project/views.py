from django.shortcuts import render_to_response, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.core.context_processors import csrf
from django.core.mail import send_mail

#from userInfo_profile.models import UserInfo, MyAnswer, MyGrade
from google_login.models import GoogleUserInfo



def index(request):
    if 'user_id' in request.session:
        user_id = request.session['user_id']
        if User.objects.filter(id=user_id):
            user = User.objects.get(id=user_id)
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            return HttpResponseRedirect("/dashboard/")
        
        else:
            user_id = False
    else:
        return redirect('/google/auth/')



@login_required
def dashboard(request, classID=False):
    return HttpResponse("<a href='/google/getAllEmails'>get all emails</a>")
    