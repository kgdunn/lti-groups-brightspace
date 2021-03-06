from django.db import models
from django.utils.encoding import python_2_unicode_compatible
import datetime

@python_2_unicode_compatible
class Person(models.Model):
    """
    A learner, with their details provided from the LTI system.
    """
    ROLES = (('Admin',   "Administrator"),
             ('Student', "Student"),
            )
    email = models.EmailField(blank=False)
    student_number = models.CharField(max_length=15, blank=True, default='')

    # Brightspace: lis_person_name_given
    person_firstname = models.CharField(max_length=100, blank=True, default='')

    # Brightspace: lis_person_name_family
    person_lastname = models.CharField(max_length=100, blank=True, default='')

    # Brightspace: lis_person_name_full
    display_name = models.CharField(max_length=400, verbose_name='Display name',
                                   blank=True)
    user_ID = models.CharField(max_length=100, blank=True,
                                            verbose_name='User ID from LMS/LTI')
    role = models.CharField(max_length=7, choices=ROLES, default='Student')

    def __str__(self):
        return u'[{0}]{1}'.format(self.role,
                                  self.email)


@python_2_unicode_compatible
class Course(models.Model):
    """ Which course is being supported here"""
    name = models.CharField(max_length=300, verbose_name="Course name")
    label = models.CharField(max_length=300, verbose_name="LTI POST label",
        help_text=("Obtain this from the HTML POST field: 'context_id' "))

    offering = models.PositiveIntegerField(default='0000', blank=True,
        help_text="Which year/quarter is it being offered?")

    def __str__(self):
        return u'[{0}] {1}'.format(self.label, self.name)


@python_2_unicode_compatible
class Allowed(models.Model):
    """ A one-time flag to ensure a student is allowed in a course."""
    person = models.ForeignKey(Person)
    course = models.ForeignKey(Course)
    allowed = models.BooleanField(default=False)

    def __str__(self):
        return u'[{0}] {1}'.format(self.course.label, self.person.email)



@python_2_unicode_compatible
class Group_Formation_Process(models.Model):
    """ Describes the Group Formation Process: requirements and deadlines.
    """
    class Meta:
        verbose_name = 'Group formation process'
        verbose_name_plural = 'Group formation processes'

    LTI_id = models.CharField(max_length=50, verbose_name="LTI ID",
            help_text=('In Brightspace LTI post: "resource_link_id"'))

    course = models.ForeignKey(Course)

    setup_mode = models.BooleanField(default=True, help_text=("When the group "
        "settings are still being added/edited; outside of `setup_mode` it is "
        "not possible to update the group names and descriptions anymore."))

    title = models.CharField(max_length=300, blank=True,
                             verbose_name="Group formation name")

    instructions = models.TextField(help_text='May contain HTML instructions',
                verbose_name='Overall instructions to learners', blank=True)

    added_dt = models.DateTimeField(auto_now_add=True)

    # True/False settings:
    allow_multi_enrol = models.BooleanField(default=False,
        help_text=('If True, the student can be in more than 1 group in this '
                   'category.'))

    show_fellows = models.BooleanField(default=False,
        help_text=('Can learners see the FirstName LastName of the other '
                   'people enrolled in their groups.'))

    has_been_pushed = models.BooleanField(default=False)

    push_dt = models.DateTimeField(editable=False, auto_now_add=True,
        verbose_name='When was the group formation pushed to Brightspace?')

    # Dates and times
    #dt_groups_open_up = models.DateTimeField(
    #    verbose_name='When can learners start to register', )

    #dt_selfenroll_starts = models.DateTimeField(
    #    verbose_name="When does self-enrolment start?",
    #    help_text='Usually the same as above date/time, but can be later', )

    dt_group_selection_stops = models.DateTimeField(
        default=None, blank=True, null=True,
        verbose_name=('When does group enrolment stop?'))


    #show_description = models.BooleanField(default=True,
    #    help_text=('Should we show the group descriptions also?'))

    #random_add_unenrolled_after_cutoff = models.BooleanField(default=False,
    #    verbose_name=('Randomly add unenrolled learners after the cutoff date/time'),
    #    help_text=('Should we randomly allocate unenrolled users after '
    #               'the cut-off date/time ("dt_group_selection_stops")?'))


    def __str__(self):
        return 'GFP[{0}]::[{1}]'.format(self.course.label, self.LTI_id)


@python_2_unicode_compatible
class Group(models.Model):
    """ Used when learners work/submit in groups."""
    gfp = models.ForeignKey(Group_Formation_Process)
    name = models.CharField(max_length=500, blank=True,
                verbose_name="Group name",
                help_text='An empty name is effectively a non-existant group.')
    description = models.TextField(blank=True,
                                   verbose_name="Detailed group description")
    capacity = models.PositiveIntegerField(default=0,
        help_text=('How many people in this particular group instance?'))
    order = models.PositiveIntegerField(default=0, help_text=('For ordering '
            'purposes in the tables.'))

    def __str__(self):
        return u'{0}'.format(self.name)

    def save(self, *args, **kwargs):

        # Don't overwrite the ID: let the table form it.
        #groups = Group.objects.filter(gfp=self.gfp)
        #all_orders = [g.order for g in groups]
        #all_orders.append(0)
        #self.order = (max(all_orders) + 1)
        super(Group, self).save(*args, **kwargs)



class Enrolled(models.Model):
    """
    Which group is a learner enrolled in
    """
    person = models.ForeignKey(Person)
    group = models.ForeignKey(Group, null=True)
    is_enrolled = models.BooleanField(default=False)
    #confirmation_code = models.CharField(default='')
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)


class WaitList(models.Model):
    """
    Which group is a learner waiting to be enrolled in
    """
    person = models.ForeignKey(Person)
    group = models.ForeignKey(Group, null=True)
    is_waiting = models.BooleanField(default=False)
    started_to_wait = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)



class Tracking(models.Model):
    """General logging."""
    action_type = (
                    ('create',         'create'),
                    ('login',          'login'),
                    ('join',           'group-join'),
                    ('leave',          'group-leave'),
                    ('waitlist-add',   'waitlist-add'),
                    ('waitlist-left',  'waitlist-left'),
                 )
    action = models.CharField(max_length=80, choices=action_type)
    ip_address = models.GenericIPAddressField()
    datetime = models.DateTimeField(auto_now_add=True)

    person = models.ForeignKey(Person, blank=True, null=True)
    group = models.ForeignKey(Group, blank=True, null=True)
    gfp = models.ForeignKey(Group_Formation_Process, blank=True, null=True)

    def __str__(self):
        return '%s [%s]' % (self.action, self.person)

