from django import __version__
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.clickjacking import xframe_options_exempt
from django.conf import settings
from django.utils import timezone

# Our imports
from .models import Person, Course, Group_Formation_Process
from .models import Group, Enrolled, Allowed, Tracking
from stats.views import create_hit, get_IP_address

# Python imports
from collections import namedtuple, defaultdict
import datetime
import json
import time
import csv
import magic

# Logging
import logging
logger = logging.getLogger(__name__)

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
        return HttpResponse('Invalid (GET)')
    action = request.POST.get('action', '').strip()
    group_id = request.POST.get('group_id', '0').strip()
    gfp = request.POST.get('gfp', '0').strip()
    logger.debug(str(request.POST))
    logger.debug('Action [{0}]: {1} for group: {2} [gfp={3}]'.format(user_ID,
                                                                     action,
                                                                     group_id,
                                                                     gfp))

    # Now hit the database:
    learner = Person.objects.filter(user_ID=user_ID)
    if not(learner):
        return HttpResponse('Invalid (learner)')
    else:
        learner = learner[0]


    gfp = Group_Formation_Process.objects.filter(id=gfp)
    if not(gfp):
        return HttpResponse('Invalid (GFP)')
    else:
        gfp = gfp[0]


    # Now we can split off for students vs. instructors, to keep this function
    # overzichtelijk
    if learner.role == 'Admin':
        return admin_action_process(request, action, gfp)


    # Check if group formation is still allowed. The user can have the link
    # from a time prior to the cut-off. If they click that link afterward
    # the cut-off they are told they cannot enrol.
    if (timezone.now() > gfp.dt_group_selection_stops):
        return HttpResponse(('The cut-off date and time to join, or leave, a '
                             'group has passed.'))


    group = Group.objects.filter(id=group_id)
    if not(group):
        return HttpResponse('Invalid (you cannot view this page "as student")')
    else:
        group = group[0]


    if group.gfp.id != gfp.id:
        return HttpResponse('Invalid (mismatch)')

    allowed = Allowed.objects.filter(person=learner,
                                     course=group.gfp.course).count()
    if not(allowed):
        return HttpResponse('Invalid (not authorized)')

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



def get_group_status(gfp):
    """
    Get's the net (end-result) of the group formation process. Students may have
    enrolled and unenrolled. This gets the final state, at this current point
    in the database.

    Returns a dictionary: each student (id) is a key. The value is itself a dict
    where the group (id) are the keys, and the values are the actions.

    # For the multiple-enrollments case:

    {'Student A': {'Group 1': 'enrol', 'Group 2': 'enrol'},
     'Student B': {'Group 1': 'unenrol'}, <-- she unenrolled, but not reenrolled
     'Student C': {'Group 2': 'enrol', 'Group 3': 'enrol'}
    }

    # When multiple-enrollment is not allowed: it will be the same, only then
    # we will see fewer key-value pairs in the dictionary.

    This function is useful for:
    (1) exporting the groups to CSV, and
    (2) pushing the results of the group formation via Valence to Brightspace.
    """
    out = defaultdict(dict)
    for action in Enrolled.objects.filter(group__gfp=gfp):
        if action.is_enrolled:
            out[action.person][action.group] = 'enrol'
        else:
            out[action.person][action.group] = 'unenrol'

    for key, value in out.items():
        # Only if there is more than 1 non-unique values in the set, then
        # we need to clean out the 'unenrol' items. Use list comprehensions.
        if len(set([v for v in value.values()])) > 1:
            out[key] = {k : v for k,v in value.items() if v=='enrol'}

    return out



def admin_action_process(request, action, gfp):
    """
    The administrator can click in the user-interface to take certain
    ``action``s for a given ``gfp``.

    Must return an HttpResponse object here.
    """
    now_time = datetime.datetime.now()
    if action =='group-enrollment-log':
        # Gets a log history for display in the browser. Returns a JSON object.

        log = []
        log_items = Tracking.objects.filter(gfp=gfp).order_by('-datetime')
        for item in log_items:
            log.append([item.datetime.strftime('%d/%B/%Y %H:%M:%S.%f'),
                        item.person.email, item.action, item.group.name])

        return HttpResponse(json.dumps(log))

    elif action =='group-CSV-download':
        raw_data = get_group_status(gfp)

        response = HttpResponse(content_type='text/csv')
        filename = '{0}--{1}.csv'.format(gfp.LTI_id,
                                         datetime.datetime.now().\
                                               strftime('%d-%B-%Y-%H-%M-%S'))
        response['Content-Disposition'] = 'attachment; filename="{0}"'.format(
                                                                       filename)
        writer = csv.writer(response)
        writer.writerow(['Student identifier', 'Group name', 'Final result'])
        for student, results in raw_data.items():
            for group_key, action in results.items():
                writer.writerow([student.email, group_key.name, action])
        return response

    elif action == 'group-push-enrollment':
        return HttpResponse('GROUP PUSH TODO')

    elif action == 'see-members':
        try:
            group_id = int(request.POST.get('group_id', '0').strip())
        except ValueError:
            return HttpResponse('Invalid group selected.')

        enrolleds = Enrolled.objects.filter(group=group_id, is_enrolled=True)
        return HttpResponse('<br>'.join([joined.person.display_name for \
                                                        joined in enrolleds]))

    # These action occur when admin is setting up groups

    elif action == 'row-update':
        message = ''
        group_name = request.POST.get('group_name', '')
        group_description = request.POST.get('group_description', '')
        group_capacity = request.POST.get('group_capacity', 0)
        group_id = request.POST.get('table_group_id', 0)
        try:
            group_capacity = int(group_capacity)
        except ValueError:
            group_capacity = 0
            message = "Invalid value entered in the Group's capacity column."


        group = Group.objects.filter(gfp=gfp, order=group_id)
        if group.count() >= 1: # the ">" case shouldn't occur
            group = group[0]
        else:
            # The Group does not exist in our database; create it
            group = Group.objects.create(gfp=gfp, order=group_id)
            logger.info('Created group in gfp={0}[id={1}]'.format(gfp,
                                                                  group.id))

        group.name = group_name[0:499]
        group.description = group_description
        group.capacity = group_capacity
        group.save()


        message = message or 'Last saved at {}'.format(
                                                 now_time.strftime('%H:%M:%S'))
        if group.name == '' and group.capacity==0 and group.description == '':
            group.delete()
            message = 'Group deleted. {}'.format(now_time.strftime('%H:%M:%S'))


        return HttpResponse(message)

    elif action == 'group-CSV-upload':
        groups = [] # what we will return to the UI
        message = ''
        csvfile = request.FILES.get('file_upload')
        filename = '/tmp/tmp-csv-{0}-{1}-{2}-{3}.csv'.format(now_time.hour,
                                                        now_time.minute,
                                                        now_time.second,
                                                        now_time.microsecond)
        with open(filename,'wb+') as destination:
            for chunk in csvfile.chunks():
                destination.write(chunk)

        filetype_sniff = magic.from_file(filename)
        if (b'ASCII' not in filetype_sniff) and (b'ISO-8859 text' not in\
                                                               filetype_sniff):
            return HttpResponse(('Invalid, or unreadable file. It was not a '
                                 'CSV file. Reload the page to try again.'))


        with open(filename, 'rt') as csvfile:
            reader = csv.reader(csvfile)

            for row in reader:
                if not(row):
                    continue # if the row is empty, ignore it
                if reader.line_num == 1:
                    mapper = {}
                    for idx, cell in enumerate(row):
                        cell = cell.lower()
                        if 'name' in cell:
                            mapper[idx] = 'name'
                        elif 'capacity' in cell:
                            mapper[idx] = 'capacity'
                        elif 'description' in cell:
                            mapper[idx] = 'description'

                    continue

                group = {'gfp': gfp,}
                for idx, cell in enumerate(row):
                    try:
                        group[mapper[idx]] = str.strip(cell)
                    except KeyError:
                        message += ('Too many columns found when processing row'
                                    ' {0}<br>').format(reader.line_num)
                        continue

                    if mapper[idx] == 'capacity':
                        try:
                            group[mapper[idx]] = int(cell)
                        except ValueError:
                            message += ('The group capacity in line {0} could '
                                        'not be converted to a number.<br>')\
                                                    .format(reader.line_num)
                groups.append(group)


        if message:
            seen = set()
            seen_add = seen.add
            message = '<br>'.join([x for x in message.split('<br>') if not \
                                               (x in seen or seen_add(x))])
            # gets the unique elements only
            message += ('<br>Please refresh this page and load an improved '
                        'version of the CSV file.')

            return HttpResponse(message)

        else:
            # Only do this at the end; if the CSV was successfully read
            for group in groups:
                new_group = Group.objects.get_or_create(**group)

            logger.debug('gfp[{}]: successfully loaded the CSV at {}'.format(
                            gfp.id, now_time))
            return HttpResponse(b'')

    elif action == 'clear-everything':
        # Without prompting, delete everything for this gfp:
        Group.objects.filter(gfp=gfp).delete()
        Tracking.objects.filter(gfp=gfp).delete()
        gfp.dt_group_selection_stops = datetime.datetime(2050, 12, 31,
                                                         23, 59, 59, 999999)
        gfp.setup_mode = True
        gfp.allow_multi_enrol = False
        gfp.show_fellows = False
        gfp.has_been_pushed = False
        gfp.save()



        return HttpResponse('Please reload GO AWAY 2.'  + str(now_time))
    elif action == 'date-update':
        datestring = request.POST.get('datestring', '2050-12-31 23:59:59')
        try:
            dt_stop = datetime.datetime.strptime(datestring, "%d-%m-%Y %H:%M")
        except ValueError:
            return HttpResponse('Invalid date and time; please try again.')

        gfp.dt_group_selection_stops = dt_stop
        gfp.save()
        message = 'Date/time saved at {}'.format(now_time.strftime('%H:%M:%S'))
        return HttpResponse(message)
    elif action == 'admin-settings-updated':
        category_name = request.POST.get('category_name', '|')
        multi_group = request.POST.get('multi_group', '|false')
        category_name = ''.join(category_name.split('|')[0:-1])
        multi_group = multi_group.split('|')[1].lower()
        multi_group = multi_group == 'true'
        gfp.allow_multi_enrol = multi_group
        gfp.title = category_name
        gfp.save()
        message = 'Updated settings: {}'.format(now_time.strftime('%H:%M:%S'))
        return HttpResponse(message)




    # end: if-elif-elif-elif-...




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

    learner, newbie = Person.objects.get_or_create(user_ID=user_ID,
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
        learner.user_ID = learner.user_ID or user_ID
        learner.email = learner.email or email
        learner.role = role
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
        gfp = Group_Formation_Process(LTI_id=gfp_ID, course=course)
        gfp.save()

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
    group_s_enrolled_in = []
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
                group_s_enrolled_in.append(group)
                is_enrolled_already = True

    return is_enrolled_already, group_s_enrolled_in


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
        B = Multi-group evaluation allowed (gfp.allow_multi_enrol=False||True)
        C = Capacity of group reached?
        D = Student is already enrolled in at least one group

          |y1  y2  y3 |  A   B   C   D
          |===========|===============
        1a|T   F   F  |  F   F   F   F
        1b|F   F   F  |  F   F   F   T
        2.|F   T   F  |  T   F   F
        3a|T   F   F  |  F   T   F   F
        3b|T   F   F  |  F   T   F   T
        4.|F   T   F  |  T   T   F
          |-----------|---------------
        5.|F   F   T  |  F   F   T
        6.|F   T   F  |  T   F   T
        7.|F   F   T  |  F   T   T
        8.|F   T   F  |  T   T   T
          |-----------|---------------

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
            # rows 1 and 3a/b
            group.unenrol_link = False
            # check 1a/1b and 3a/b
            if not(is_enrolled_already) or group.gfp.allow_multi_enrol:
                group.enrol_link = True


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
                        'resource_link_id': '24426107',
                        #'roles': (u'urn:lti:instrole:ims/lis/Instructor,Admin,'
                        #           'urn:lti:instrole:ims/lis/Admin,Admin'),
                        'roles': u'Instructor',
                        #'roles': u'Student',
                        'lis_person_contact_email_primary': 'kgdunn@gmail.com1',
                        'lis_person_name_full': 'Kevin Dunn',
                        'user_id': '01a7b8a9-f1c9-430d-b7d9-eca804cbde10_701',
                        }

        request.META = {'REMOTE_ADDR': '127.0.0.1'}
    else:
        original_request = request


    if request.method != 'POST' and (len(request.GET.keys())==0):
        return HttpResponse("This is the Brightspace Groups LTI component.")

    # Special case: instructor is uploading a CSV file
    if original_request.FILES.get('file_upload', ''):

        error_message = process_action(original_request,
                                       original_request.POST.get('user_ID', ''))
        if error_message.getvalue():
            return HttpResponse(error_message)
        else:
            original_request.FILES['file_upload'] = None



    person_or_error, course, gfp = starting_point(request)

    if not(isinstance(person_or_error, Person)):
        return person_or_error      # Error path if student does not exist

    learner = person_or_error
    logger.debug('Person entering: {0}'.format(learner))


    # Do the work here; Return the HTTP Response
    if learner.role == 'Student':
        # Get them alphabetically, and then within the fixed order specified
        groups = Group.objects.filter(gfp=gfp).order_by('name').order_by('order')
        is_enrolled_already, joined = add_enrollment_summary(groups, learner)

        if (timezone.now() > gfp.dt_group_selection_stops):
            ctx = {'groups_joined': joined,
                   'learner': learner,
                   'gfp': gfp,
                   'is_enrolled_already': is_enrolled_already,
                  }

            return render(original_request,
                        'formation/student_summary_afterwards.html', ctx)
        else:
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
        ctx = {'groups': groups, 'learner': learner, 'gfp': gfp,
               'course': course}


        if gfp.setup_mode or groups.count() == 0:

            no_groups = """
            {id:1, group_name:"Group 1 (edit this cell)",
            capacity:42, description:"Group 1 will meet in ..."},
            """

            if groups.count() == 0:
                ctx['no_groups'] = no_groups
            return render(original_request,
                          'formation/instructor_create_groups.html',
                          ctx)
        else:

            _ = add_enrollment_summary(groups, learner)
            return render(original_request,
                          'formation/instructor_summary_view.html',
                          ctx)


