from django import __version__
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.clickjacking import xframe_options_exempt
from django.conf import settings

# Our imports
from .models import Person, Course, Group_Formation_Process
from .models import Group, Enrolled, Allowed, Tracking
from stats.views import create_hit, get_IP_address

# Python imports
from collections import namedtuple, defaultdict
import datetime
import json
import csv


# Logging
import logging
logger = logging.getLogger(__name__)
logger.debug('Django version ' + __version__)

development = settings.DEBUG

 
def track_log(request, action, gfp, group, person):
    """Tracks in the logs the person and their actions for a given group.
    """
    ip_address = get_IP_address(request)
    try:
        tracked = Tracking(ip_address=ip_address,
                           action=action,
                           gfp=gfp,
                           group=group,
                           person=person,                          
                        )
        tracked.save()
    except Exception:
        pass
    
    
@csrf_exempt
@xframe_options_exempt # Required for integration into Brightspace
def process_action(request, user_ID):
    """
    Ensures the learner is actually in the group_formation_process: how?
    > Since the learner has visited the group page in Brightspace, it implies
    > they are registered in the course. 
    > Additional precaution: csrf cookie checking
    
    Basic principle: even though this is protected with CSRF, we will not spare
    any precaution, since spoofing this URL can lead to confusion. Perform
    extra checks before modifying the database.
    """
    # Collect all information we can from the user and browser:
    if request.GET:
        return HttpResponse('Invalid')
    action = request.POST.get('action', '').strip()
    group_id = request.POST.get('group_id', '0').strip()
    gfp = request.POST.get('gfp', '0').strip()

    # Now hit the database:
    learner = Person.objects.filter(user_ID=user_ID)
    if not(learner):
        return HttpResponse('Invalid')
    else:
        learner = learner[0]
    

    gfp = Group_Formation_Process.objects.filter(id=gfp)
    if not(gfp):
        return HttpResponse('Invalid') 
    else:
        gfp = gfp[0]
        
        
    # Now we can split off for students vs. instructors, to keep this function
    # overzichtelijk
    if learner.role == 'Admin':
        return admin_action_process(request, action, gfp)
            
            
    group = Group.objects.filter(id=group_id)
    if not(group):
        return HttpResponse('Invalid')
    else:
        group = group[0]
    
    
    if group.gfp.id != gfp.id:
        return HttpResponse('Invalid') 
    
    allowed = Allowed.objects.filter(person=learner, 
                                     course=group.gfp.course).count()
    if not(allowed):
        return HttpResponse('Invalid') 
    
    # OK, so we have determined with several checks that the student is
    # allowed to take an action now.
    
    if action == 'group-enrol':
        success_message = "Successfully enrolled"
        
        if Enrolled.objects.filter(group=group, is_enrolled=True).count() >= \
                                                             group.capacity:
            # We cannot enrol beyond the group capacity 
            # The link is not shown, but this precaution is here also.
            return HttpResponse('The group has reached the maximum capacity')     
                
        if not(gfp.allow_multi_enrol):
            # First remove the user from all other enrollments:
            all_enrols = Enrolled.objects.filter(person=learner, group__gfp=gfp)
            for enrolled in all_enrols:
                if enrolled.is_enrolled:
                    track_log(request, action='leave', gfp=gfp, 
                              group=enrolled.group, person=learner)
                    
            all_enrols.update(is_enrolled=False)

                        
        enrolled, _ = Enrolled.objects.get_or_create(person=learner, 
                                                     group=group)            
        enrolled.is_enrolled = True
        enrolled.save()
        track_log(request, action='join', gfp=gfp, group=group,
                  person=learner)        
                
        return HttpResponse(success_message) 
    
    if action == 'group-unenrol':
        success_message = 'Successfully un-enrolled'
        enrolled, _ = Enrolled.objects.get_or_create(person=learner, 
                                                     group=group)
        enrolled.is_enrolled = False
        enrolled.save()
        track_log(request, action='leave', gfp=gfp, group=group,
                  person=learner)         

        return HttpResponse(success_message)  
    
    if action == 'group-add-waitlist':
        track_log(request, action='waitlist-add', gfp=gfp, group=group,
                person=learner)         
                
        return HttpResponse('This is not supported yet.')
        
def admin_action_process(request, action, gfp):
    """
    The administrator can click in the user-interface to take certain 
    ``action``s for a given ``gfp``.
    
    Must return an HttpResponse object here.
    """
    if action =='group-enrollment-log':
        # Gets a log history for display in the browser. Returns a JSON object.
        
        log = []
        log_items = Tracking.objects.filter(gfp=gfp).order_by('-datetime')
        for item in log_items:
            log.append([item.datetime.strftime('%d/%B/%Y %H:%M:%S.%f'), 
                        item.person.email, item.action, item.group.name])
            
        return HttpResponse(json.dumps(log))
    
    elif action =='group-CSV-download':
        response = HttpResponse(content_type='text/csv')
        filename = '{0}--{1}.csv'.format(gfp.LTI_id,
                                         datetime.datetime.now().\
                                               strftime('%d-%B-%Y-%H-%M-%S'))
        response['Content-Disposition'] = 'attachment; filename="{0}"'.format(
                                                                       filename)
        writer = csv.writer(response)
        writer.writerow(['Student email', 'Group name', 'Last action taken'])
        return response
    

    elif action == 'group-push-enrollment':
        return HttpResponse('GROUP PUSH TODO')
    return HttpResponse('This is not supported yet.')

  

def get_create_student(request, course, gfp):
    """
    Gets or creates the learner from the POST request.
    """
    newbie = False
    
    email = request.POST.get('lis_person_contact_email_primary', '')
    display_name = request.POST.get('lis_person_name_full', '')
    user_ID = request.POST.get('user_id', '')
    POST_role = request.POST.get('roles', '')
    
    # You can also use: request.POST['ext_d2l_role'] in Brightspace
    role = 'Student'
    if 'Instructor' in POST_role:
        role = 'Admin'
    
    learner, newbie = Person.objects.get_or_create(email=email,
                                                   user_ID=user_ID,
                                                   role=role)

    if newbie:
        create_hit(request, item=course, action='create', 
                       user=learner, other_info='gfp.id={0}'.format(gfp.id),
                       other_info_id=gfp.id)               
        learner.display_name = display_name
        learner.save()
        logger.info('New learner: {0} [{1}]'.format(learner.display_name,
                                                    learner.email))

    if learner:
        # Augments the learner with extra fields that might not be there
        if learner.user_ID == '':
            learner.user_ID = user_ID
            learner.save()
            
    # Register that this person is allowed into this course.
    Allowed.objects.get_or_create(person=learner, course=course, allowed=True)

    return learner

def starting_point(request):
    """
    Bootstrap code to run on every request.

    Returns a ``Person`` instance, the ``Course`` instant, and ``Group Formation
    Process`` (GFP) instance.
    """
    course_ID = request.POST.get('context_id', None) or (settings.DEBUG and \
                             request.GET.get('context_id', None))

    gfp_ID = request.POST.get('resource_link_id', None) or (settings.DEBUG and \
                             request.GET.get('resource_link_id', None))


    if (gfp_ID is None) or (course_ID is None):
        return (HttpResponse(("You are not registered in this course. NCNPR")),
                None, None)

    
    try:
        course = Course.objects.get(label=course_ID)
    except Course.DoesNotExist:
        # The Course does not exist in our database; create it
        name = request.POST.get('context_title')
        if isinstance(name, list):
            name = name[0]
        else:
            name = str(name)
        course = Course.objects.create(name=name, label=course_ID)
        
        logger.info('Created course: {0}[code={1}]'.format(name, course_ID)) 
        
    # Now we have a ``Course`` instance. Next: get the GFP within this course.
    try:
        gfp = Group_Formation_Process.objects.get(course=course,
                                                  LTI_id=gfp_ID)
    except Group_Formation_Process.DoesNotExist:
        # The GFP does not exist in our database; create it.
        gfp = Group_Formation_Process.objects.create(LTI_id=gfp_ID,
                                                     course=course)
        
        logger.info('Created GFP: {0}[LTI_id={1}]'.format(course, gfp_ID)) 
        

    person = get_create_student(request, course, gfp)
 
    if person:
            
        return person, course, gfp
    else:
        return (HttpResponse(("You are not registered in this course.")), None,
                None)
    
    
def add_enrollment_summary(groups, learner=None):
    """
    Adds the group enrollment summary for the QuerySet of ``groups``. Modifies
    the instances by adding new field(s):
        * n_enrolled     : number of students from course enrolled in this group
        * n_free         : this is what students want: number of free spots
        * is_enrolled    : True or False, indicating if the learner is enrolled
        
    The instances in the QuerySet are never saved to the database, but will
    have added information that can be rendered in the templates.
    
    Returns ``is_enrolled_already``, if ``learner`` is enroled in 1 or more 
    groups.
    """
    is_enrolled_already = False
    for group in groups:
        enrolleds = Enrolled.objects.filter(group=group, is_enrolled=True)
        group.n_enrolled = enrolleds.count()
        # You must threshold at zero, incase a manual override is done, and
        # then we don't want to show "-2 spaces free", for example.
        group.n_free = max(0, group.capacity - group.n_enrolled)
        group.is_enrolled = 0
        if learner and group.n_enrolled:
            group.is_enrolled = enrolleds.filter(person=learner).count()
            if group.is_enrolled:
                is_enrolled_already = True         
            
    return is_enrolled_already 
                

def add_enrol_unenrol_links(groups, learner=None, is_enrolled_already=False):
    """
    Adds the links to enrol and unenrol to the QuerySet of ``groups``. This 
    is only called if the student is accessing the page.
    
    Modifies the instances by adding new field(s):
        * y1=enrol_link     : click this link and the student will be enrolled
        * y2=unenrol_link   : click this link and the student will be unenrolled
        * y3=waitlist_link  : click this link and the student is waitlisted 
        
    Table of assignments, depending on 3 conditions:
        A = Already enrolled in this group?
        B = Multi-group evaluation allowed (gfp.allow_multi_enrol=True)
        C = Capacity of group reached?
    
          |y1  y2  y3 |  A   B   C
          |===========|===========
        1.|T   F   F  |  F   F   F
        2.|F   T   F  |  T   F   F
        3.|T   F   F  |  F   T   F
        4.|F   T   F  |  T   T   F
          |-----------|-----------
        5.|F   F   T  |  F   F   T
        6.|F   T   F  |  T   F   T
        7.|F   F   T  |  F   T   T
        8.|F   T   F  |  T   T   T
        
    The instances in the QuerySet are never saved to the database, but will
    have added information that can be rendered in the templates.    
    
    Also, returns a dictionary of columns to hide in the student view.
    """
    # Assume we will hide all these columns, unless otherwise specified
    hide_description = True
    hide_join_waitlist = True
    hide_leave_group = True
    
    for group in groups:
        if group.description:
            hide_description = False
        group.enrol_link = False
        group.unenrol_link = True
        if group.is_enrolled:         # learner already enrolled (rows 2 and 4)
            hide_leave_group = False  # then the defaults suffice
        else:
            group.enrol_link = True   # rows 1 and 3
            group.unenrol_link = False
             
          
        # Rows 5, 6, 7 and 8 in the above table trump all conditions:
        if Enrolled.objects.filter(group=group, is_enrolled=True).count()\
                                                             >= group.capacity:
            group.enrol_link = False
            group.waitlist_link = True
            if group.is_enrolled:
                group.waitlist_link = False
                group.unenrol_link = True
                hide_leave_group = False
        else:
            # Rows 5, 6, 7 and 8 for column C and y3
            group.waitlist_link = False
            
    return {'description': hide_description,
            'join_waitlist': hide_join_waitlist,
            'leave_group': hide_leave_group}
            
        
            
@csrf_exempt           # The entry page is exempt, the others are not.
@xframe_options_exempt # Required for integration into Brightspace
@ensure_csrf_cookie    # But set the CSRF cookie for later use
def index(request):
    """
    The main entry point
    """
    logger.debug(str(request.POST))
    if development:
        # Creates a fake ``request`` that is used during development/debugging
        original_request = request
        request = namedtuple('Request', ['method', 'POST', 'META'])   
        request.method = "POST"
                         # course code in Brightspace
        request.POST = {'context_id': '8228',
                        'context_title': [u'IO3075 TCPD (2016/17 Q3)'],
                        
                         # When a new item is created in Brightspace, a code
                         # ID is provided. The course and this code provide
                         # a unique way to identify the course.
                        'resource_link_id': '24426106',
                        #'roles': (u'urn:lti:instrole:ims/lis/Instructor,Admin,'
                        #           'urn:lti:instrole:ims/lis/Admin,Admin'),
                        'roles': u'Instructor',
                        #'roles': u'Student',
                        'lis_person_contact_email_primary': 'kgdunn@gmail.com2',
                        'lis_person_name_full': 'Kevin Dunn',
                        'user_id': '01a7b8a9-f1c9-430d-b7d9-eca804cbde10_702',
                        }
        
        request.META = {'REMOTE_ADDR': '127.0.0.1'}
    else:
        original_request = request
        
            
    if request.method != 'POST' and (len(request.GET.keys())==0):
        return HttpResponse("This is the Brightspace Groups LTI component.")

    person_or_error, course, gfp = starting_point(request)

    if not(isinstance(person_or_error, Person)):
        return person_or_error      # Error path if student does not exist

    learner = person_or_error
    logger.debug('Learner entering: {0}'.format(learner))

   
    # Do the work here; Return the HTTP Response
    if learner.role == 'Student':
        # Get them alphabetically, and then within the fixed order specified
        groups = Group.objects.filter(gfp=gfp).order_by('name').order_by('order')
        is_enrolled_already = add_enrollment_summary(groups, learner)
        hide_columns = add_enrol_unenrol_links(groups, learner, 
                                               is_enrolled_already)
        
        ctx = {'groups': groups,
               'learner': learner,
               'gfp': gfp,
               'is_enrolled_already': is_enrolled_already,
               'hide_columns': hide_columns,
               }

        return render(original_request, 
                      'formation/student_summary_view.html', ctx)        
    
    elif learner.role == 'Admin':
        groups = Group.objects.filter(gfp=gfp).order_by('name').order_by('order')
        _ = add_enrollment_summary(groups, learner)
        ctx = {'groups': groups,
               'learner': learner,
               'gfp': gfp,
                   }
        return render(original_request, 
                      'formation/instructor_summary_view.html', ctx)          
    