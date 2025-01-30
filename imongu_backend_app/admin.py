from django.contrib import admin
from .models import User,Goal, okr,team_Table
# Register your models here.
admin.site.register(User)
admin.site.register(Goal)
admin.site.register(okr)
admin.site.register(team_Table)
