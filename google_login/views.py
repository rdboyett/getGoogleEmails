import os
ROOT_PATH = os.path.dirname(__file__)

import json
import logging
import httplib2
from datetime import datetime, timedelta

from django.shortcuts import render_to_response, redirect
from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.core.context_processors import csrf
from django.core.mail import send_mail
from django.utils import timezone

from google_login.models import CredentialsModel, GoogleUserInfo, ForgottenPassword
from google_login import settings
from forms import ContactForm
#from userInfo_profile.models import UserInfo
#from classrooms.models import ClassUser

from apiclient.discovery import build
from oauth2client import xsrfutil
from oauth2client.client import flow_from_clientsecrets #, SignedJwtAssertionCredentials
from oauth2client.django_orm import Storage

from oauth2client.client import OAuth2WebServerFlow

from apiclient import errors


# CLIENT_SECRETS, name of a file containing the OAuth 2.0 information for this
# application, including client_id and client_secret, which are found
# on the API Access tab on the Google APIs
# Console <http://code.google.com/apis/console>
CLIENT_SECRETS = settings.CLIENT_SECRETS

SCOPES = settings.SCOPES

FLOW = flow_from_clientsecrets(
    CLIENT_SECRETS,
    scope= ' '.join(SCOPES),
    redirect_uri= settings.redirect_uri)



def index(request):
    if 'user_id' in request.session:
        user_id = request.session['user_id']
        if User.objects.filter(id=user_id):
            user = User.objects.get(id=user_id)
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            return HttpResponseRedirect(settings.LOGIN_SUCCESS)
        
        else:
            user_id = False
    else:
        user_id = False
    
    if not user_id:
        args = {}
        args.update(csrf(request))
        #redirect to user login page
        return render_to_response('google_login/login.html', args)

    
def auth(request, Boyett=0):
    credential = None
        
    if credential is None or credential.invalid == True:
        FLOW.params['access_type'] = 'offline'
	
	# in oder to force a persistant credential that will refresh itself user "/google/auth/1".  However other users will not need to worry about it.
	if Boyett:
	    FLOW.params['approval_prompt'] = 'force'
	    
	    
        FLOW.params['state'] = xsrfutil.generate_token(settings.SECRET_KEY,
                                                        request.user)
        authorize_url = FLOW.step1_get_authorize_url()
        return HttpResponseRedirect(authorize_url)


def auth_return(request):
    if not xsrfutil.validate_token(settings.SECRET_KEY, request.REQUEST['state'],
                                   request.user):
      return  HttpResponseBadRequest('oops')
    credential = FLOW.step2_exchange(request.REQUEST)


    user_info = get_user_info(credential)
    google_email = user_info.get('email')
    firstName = user_info.get('given_name')
    lastName = user_info.get('family_name')
    google_id = user_info.get('id')
    googlePlus = user_info.get('link')
    language = user_info.get('locale')
    googleAvatar = user_info.get('picture')
    gender = user_info.get('gender')
        
    emailEnding = google_email.split("@")[1]
    userName = "@"+google_email.split("@")[0]
    
    if User.objects.filter(username=userName):
        # Make sure that the e-mail is unique.
        user = User.objects.get(username=userName)
        #userInfo = UserInfo.objects.get(user=user)
    elif User.objects.filter(email=google_email):
        user = User.objects.get(email=google_email)
    else:
        if 'alvaradoisd.net' in emailEnding:
            if 'student' in emailEnding:
                bTeacher = False
            else:
                bTeacher = True
            
            user = User.objects.create(
                username = userName,
                first_name = firstName,
                last_name = lastName,
                email = google_email,
                password = 'password',
            )
            
	    
        else:
            return HttpResponse('Please sign in with your Alvarado ISD account.')
	
    #Update the User model with changes in google
    if not user.first_name:
	user.first_name = firstName
	user.last_name = lastName
	user.save()

    #Check to see if a google account has been setup yet
    if not GoogleUserInfo.objects.filter(google_id=google_id):
        newGoogleUser = GoogleUserInfo.objects.create(
            user = user,
            google_id = google_id,
            googlePlus = googlePlus,
            language = language,
            googleAvatar = googleAvatar,
            gender = gender,
        )
            
    
    #check to see if user is logged in
    if user:
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        
    request.session['user_id'] = user.id
    request.session.set_expiry(604800)
    storage = Storage(CredentialsModel, 'id', user, 'credential')
    storage.put(credential)
    
    
    '''
    orgUnit = getUsersOrgUnit(user_info.get('email'))
    if orgUnit:
	pass
	#put this into students userInfo
    '''
    
    #return HttpResponseRedirect(settings.LOGIN_SUCCESS)
    #return HttpResponse('<script>window.close();</script>')
    return HttpResponse('here')



def get_user_info(credentials):
  """Send a request to the UserInfo API to retrieve the user's information.

  Args:
    credentials: oauth2client.client.OAuth2Credentials instance to authorize the
                 request.
  Returns:
    User information as a dict.
  """
  user_info_service = build(
      serviceName='oauth2', version='v2',
      http=credentials.authorize(httplib2.Http()))
  user_info = None
  try:
    user_info = user_info_service.userinfo().get().execute()
  except errors.HttpError, e:
    logging.error('An error occurred: %s', e)
  if user_info and user_info.get('id'):
    return user_info
  else:
    raise NoUserIdException()



@login_required
def success(request):
    return HttpResponse("You've logged in with success!")




def error(request):
    return HttpResponse("There was an error during login!")



def test(request):
    return HttpResponse("Hello, You're in!")


def forgotPassword(request, forgotID=False):
    if forgotID:
        #check that it has been less than 5 minutes since forgotID was created.
        if ForgottenPassword.objects.filter(id=forgotID):
            forgot = ForgottenPassword.objects.get(id=forgotID)

            now = timezone.now()
            tdelta = now - forgot.dateTime
            seconds = tdelta.total_seconds()

            if not seconds:# > 300 or forgot.used:
                return HttpResponse('You reached this link in error.'+str(seconds))
            else:
                forgot.used = True
                forgot.save()

                args = {}
                args.update(csrf(request))
                args['passwordForm'] = ContactForm()
                return render_to_response('google_login/change_password.html', args)
        else:
            return HttpResponse('You reached this link in error.')

        #Set the dateTime to 0 so that this link will only work once.
    else:
        return HttpResponse('You reached this link in error.')


def passwordReset(request):
    return HttpResponse('You reached this link.')



@login_required
def studentGradYears(request):
    
    
    args = {}
    args.update(csrf(request))
	
    return render_to_response('update_students.html', args)














































#-------------------------- Ajax calls -------------------------------------------

def ajaxAuth(request):
    if request.method == 'POST':
        username = request.POST['username'].strip()
        password = request.POST['password'].strip()
        user = authenticate(username=username, password=password)

        if user is None and User.objects.filter(email=username):
            userEmail = User.objects.get(email=username)
            user = authenticate(username=userEmail.username, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                request.session['user_id'] = user.id
                request.session.set_expiry(604800)
                data = {'success':'success'}
            else:
                data = {'error':'<div class="google-login-error">incorrect username or password</div>'}
        else:
			data = {'error':'<div class="google-login-error">incorrect username or password</div>'}
    
    return HttpResponse(json.dumps(data))
    
    
    


def checkUsername(request):
    if request.method == 'POST':
        username = request.POST['username']
        if User.objects.filter(username=username):
            data = {'exists':'true'}
        else:
            data = {'exists':'false'}
    else:
        data = {'error':'Did not post correctly'}
    return HttpResponse(json.dumps(data))




def submitRegistration(request):
    if request.method == 'POST':
        username = request.POST['username'].strip()
        email = request.POST['email'].strip()
        password = request.POST['password'].strip()

        if User.objects.filter(username=username):
            data = {'error':'This username is already taken.'}
        elif User.objects.filter(email=email):
            data = {'error':'This email is already used with another account.'}
        else:
            user = User.objects.create_user(username, email, password)
            
            #check to see if user is logged in
            if user:
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                
            request.session['user_id'] = user.id
            request.session.set_expiry(604800)
            data = {'success':'success'}

    else:
        data = {'error':'Did not post correctly'}
    return HttpResponse(json.dumps(data))



def doesEmailExist(request):
    if request.method == 'POST':
        email = request.POST['email']
        if User.objects.filter(email=email):
            data = {'exists':'true'}
        else:
            data = {'exists':'false'}
    else:
        data = {'error':'Did not post correctly'}
    return HttpResponse(json.dumps(data))




def submitPasswordForgot(request):
    if request.method == 'POST':
        email = request.POST['email']
        if User.objects.filter(email=email):
            user = User.objects.get(email=email)
            forgotLink = ForgottenPassword.objects.create()
            try:
                send_mail(
                    'Alert from '+ settings.WEBSITENAME,
                    'To reset your password please follow this link:\n\n'+
                    settings.ROOT_WEBSITE_LINK+'/google/forgot/'+ str(forgotLink.id) + '\n\n'+
                    'If you feel this message reached you in error, please disregard or you can email '+ settings.WEBMASTER_EMAIL +' for any questions.',
                    settings.WEBMASTER_EMAIL,
                    [email],
                    fail_silently=False
                )
                data = {'exists':'true'}
            except:
                data = {'error':'Your server email settings have not been set.  Please read the requirements text.'}
        else:
            data = {'exists':'false'}
    else:
        data = {'error':'Did not post correctly'}
    return HttpResponse(json.dumps(data))



@login_required
def syncGoogleAccount(request):
    if request.method == 'POST':
        oldUserID = request.POST['oldUserID']
        newUserID = request.POST['newUserID']

	if User.objects.filter(id=oldUserID):
	    resetThisUser = User.objects.get(id=oldUserID)
	else:
	    return HttpResponse(json.dumps({'error':'Sorry, we are having an issue linking your google account.'}))
	    	
	if User.objects.filter(id=newUserID):
	    deleteThisUser = User.objects.get(id=newUserID)
	else:
	    return HttpResponse(json.dumps({'error':'Sorry, we are having an issue linking your google account.'}))
	    
	    
	#reset google account to oldUserID and delete newUserID
	if GoogleUserInfo.objects.filter(user=deleteThisUser):
	    googleAccount = GoogleUserInfo.objects.get(user=deleteThisUser)
	    
	    #get the storage from deleteUser
	    oldStorage = Storage(CredentialsModel, 'id', deleteThisUser, 'credential')
	    credential = oldStorage.get()
	    
	    #create a new storage for resetUser
	    newStorage = Storage(CredentialsModel, 'id', resetThisUser, 'credential')
	    newStorage.put(credential)
	    
	    #delete old credential for deleteUser
	    oldStorage.delete()
	    
	    #reset email from deleteUser to resetUser to make them the same
	    resetThisUser.email = deleteThisUser.email
	    resetThisUser.save()
	    
	    
	    #log in resetUser
	    resetThisUser.backend = 'django.contrib.auth.backends.ModelBackend'
	    login(request, resetThisUser)
		
	    #set new userID for session
	    request.session['user_id'] = resetThisUser.id
	    request.session.set_expiry(604800)
	    
	    
	    #set to old account
	    googleAccount.user = resetThisUser
	    googleAccount.save()
	    
	    #delete deleteUser
	    deleteThisUser.delete()
	    data = {'success':'success'}
	else:
	    return HttpResponse(json.dumps({'error':'Sorry, we are having an issue linking your google account.'}))
    else:
        data = {'error':'Did not post correctly'}
    return HttpResponse(json.dumps(data))



@login_required
def ajaxResetPassword(request):
    if request.method == 'POST':
        password1 = request.POST['password1']
        password2 = request.POST['password2']
	
	if password1 == password2:
	    user = request.user
	    user.set_password(password1)
	    user.save()
	    data = {'success':'success'}
	else:
	    return HttpResponse(json.dumps({'error':"Sorry, these passwords don't match."}))
    else:
        data = {'error':'Did not post correctly'}
    return HttpResponse(json.dumps(data))



@login_required
def changeUsername(request):
    if request.method == 'POST':
        username = request.POST['userName'].strip()
	
	currentUser = request.user
	
	#check if username exists
        if User.objects.filter(username=username):
	    #Check if they are the same user as logged in
	    if currentUser == User.objects.get(username=username):
		return HttpResponse(json.dumps({'error':'you already have that username.'}))
	    else:
		return HttpResponse(json.dumps({'error':'username already exists.'}))
        else:
	    currentUser.username = username
	    currentUser.save()
            data = {'username':username}
    else:
        data = {'error':'Did not post correctly'}
    return HttpResponse(json.dumps(data))




def getUsersOrgUnit(userEmail, user):
    #adminUser = User.objects.get(email='rboyett@alvaradoisd.net')
    
    
    storage = Storage(CredentialsModel, 'id', user, 'credential')
    credential = storage.get()
    
    if credential is None or credential.invalid == True:
                #return HttpResponseRedirect("/login/")
        return False
    else:
        http = httplib2.Http()
        http = credential.authorize(http)
	directory_service = build("admin", "directory_v1", http=http)
	userGoogleInfo = directory_service.users().get(userKey=userEmail, projection=None, customFieldMask=None, viewType=None, fields='name,id,orgUnitPath').execute()
	return userGoogleInfo
    
    
    
def getAllFaculty(user):
    #adminUser = User.objects.get(email='rboyett@alvaradoisd.net')
    
    
    storage = Storage(CredentialsModel, 'id', user, 'credential')
    credential = storage.get()
    
    if credential is None or credential.invalid == True:
                #return HttpResponseRedirect("/login/")
        return False
    else:
        http = httplib2.Http()
        http = credential.authorize(http)
	directory_service = build("admin", "directory_v1", http=http)
	    
	all_users = []
	page_token = None
	params = {'domain': 'alvaradoisd.net', 'fields':'nextPageToken,users(name,id,orgUnitPath,primaryEmail)'}
	
	while True:
	  try:
	    if page_token:
	      params['pageToken'] = page_token
	      
	    current_page = directory_service.users().list(**params).execute()
	    
	    all_users.extend(current_page['users'])
	    page_token = current_page.get('nextPageToken')
	    if not page_token:
	      break
	  except errors.HttpError as error:
	    return 'An error occurred: %s' % error
	    break
	
	return all_users
	    
    
    
    
@login_required
def getAllEmails(request):
    faculty = getAllFaculty(request.user)
    
    for user in faculty:
	google_email = user['primaryEmail']
	firstName = user['name']['givenName']
	lastName = user['name']['familyName']
	google_id = user['id']
	
	userName = "@"+google_email.split("@")[0]
	
	if User.objects.filter(email=google_email):
	    user = User.objects.get(email=google_email)
	    user.username = userName
	    user.first_name = firstName
	    user.last_name = lastName
	    user.email = google_email
	    user.save()
	    
	    
	else:
	    user = User.objects.create(
		    username = userName,
		    first_name = firstName,
		    last_name = lastName,
		    email = google_email,
		    password = 'password',
	    )
	
    
    return HttpResponse("it worked!")
    
    
    
    '''
    if request.method == 'POST':
        numberStudents = request.POST['numberStudents'].strip()
        studentEmail = request.POST['studentEmail'].strip()
	
	if not numberStudents == 'all':
	    student = getUsersOrgUnit(studentEmail, request.user)
	    
	    if not student:
		return HttpResponse(json.dumps({'error':'/google/auth/1'}))
	    else:
		gradYear = student['orgUnitPath'].split('/')[-1]
		    
		if gradYear.isdigit():
		    google_email = student['primaryEmail']
		    firstName = student['name']['givenName']
		    lastName = student['name']['familyName']
		    google_id = student['id']
			
		    emailEnding = google_email.split("@")[1]
		    userName = "@"+google_email.split("@")[0]
		    
		    if 'student' in emailEnding:
			bTeacher = False
		    else:
			bTeacher = True
            
		    if User.objects.filter(email=google_email):
			user = User.objects.get(email=google_email)
		    else:
			user = User.objects.create(
				username = userName,
				first_name = firstName,
				last_name = lastName,
				email = google_email,
				password = 'password',
			)
			    
		    if not UserInfo.objects.filter(user=user):
			userInfo = UserInfo.objects.create(
				user = user,
				teacher = bTeacher,
			    )
	    
		    if not GoogleUserInfo.objects.filter(google_id=google_id):
			newGoogleUser = GoogleUserInfo.objects.create(
				user = user,
				google_id = google_id,
				gradYear = gradYear,
			    )
			
		    data = {'success':student}
		    
		else:
		    data = {'error':'not a student'}
	    
	    
	    
	else:
	    allStudents = getAllStudentsOrgUnit(request.user)
	    if not allStudents:
		return HttpResponse(json.dumps({'error':'/google/auth/1'}))
	    else:
		for student in allStudents:
		    #get the last part of the students orgUnit 
		    gradYear = student['orgUnitPath'].split('/')[-1]
    
		    if gradYear.isdigit():
			google_email = student['primaryEmail']
			firstName = student['name']['givenName']
			lastName = student['name']['familyName']
			google_id = student['id']
			
			emailEnding = google_email.split("@")[1]
			userName = "@"+google_email.split("@")[0]
		    
			if User.objects.filter(email=google_email):
			    user = User.objects.get(email=google_email)
			else:
			    user = User.objects.create(
				username = userName,
				first_name = firstName,
				last_name = lastName,
				email = google_email,
				password = 'password',
			    )
			    
			if not UserInfo.objects.filter(user=user):
			    userInfo = UserInfo.objects.create(
				user = user,
			    )
	    
			if not GoogleUserInfo.objects.filter(google_id=google_id):
			    newGoogleUser = GoogleUserInfo.objects.create(
				user = user,
				google_id = google_id,
				gradYear = gradYear,
			    )
			    
			    
		data = {'success':'true'}
	    
	    
    else:
        data = {'error':'Did not post correctly'}
    return HttpResponse(json.dumps(data))

'''





























