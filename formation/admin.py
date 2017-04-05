from django.contrib import admin
from .models import Person, Course, Enrolled, Group_Formation_Process
from .models import Group, Tracking

class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "label", )

class PersonAdmin(admin.ModelAdmin):
    list_display = ("role", "email", "user_ID", "display_name",)

class Group_Formation_ProcessAdmin(admin.ModelAdmin):
    list_display = ("LTI_id", "course",  "title", 
                    "show_fellows", )

class GroupAdmin(admin.ModelAdmin):
    list_display = ("gfp", "name", "description", "capacity", "order")

class EnrolledAdmin(admin.ModelAdmin):
    list_display = ("person", "group", "is_enrolled", "created", "modified")

class TrackingAdmin(admin.ModelAdmin):
    list_display = ("person", "action", "group", "gfp", "datetime")
    

admin.site.register(Course, CourseAdmin)
admin.site.register(Person, PersonAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(Group_Formation_Process, Group_Formation_ProcessAdmin)
admin.site.register(Enrolled, EnrolledAdmin)
admin.site.register(Tracking, TrackingAdmin)



