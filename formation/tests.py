from django.test import TestCase
from django.utils import timezone
from .models import Group, Group_Formation_Process, Enrolled
from .models import Course, Person, Allowed

import random
import datetime
class SpeedTestCase(TestCase):
    """
    To test how fast students can enrol themselves in a database"""
    def setUp(self):
        start = datetime.datetime.now()
        course = Course.objects.create(name='Testing', label='abc123')
        
        n_people = 200
        people = []
        for person in range(n_people):
            p = Person.objects.create(email='p{0}@example.com'.format(person),
                                  display_name = 'Person {0}'.format(person),
                                  user_ID = 'User_ID_{0}'.format(person),
                                  role = 'Student')
            Allowed.objects.create(person=p, course=course)
            people.append(p)
            
        gfp = Group_Formation_Process.objects.create(LTI_id='987', 
                                            course=course,
                                            title='TestingGFP', 
                                            allow_multi_enrol=True,
                                                     )

        n_groups = 40
        groups = []
        for idx in range(n_groups):
            group = Group.objects.create(gfp=gfp, name='Group {0}'.format(idx),
                        description = 'Group Description {0}'.format(idx),
                        capacity = random.randint(20, 50), order=idx)
        groups.append(group)
        print('Time taken to create {0} users in {1} groups: {2}'.format(\
                n_people, n_groups, datetime.datetime.now() - start))
