import uuid
from django.db import models
from django.utils import timezone
from enum import Enum
from django_countries.fields import CountryField


class Role(models.Model):
    role_name = models.CharField(max_length=255, default="")

    class Meta:
        db_table = "role"


class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    password = models.CharField(max_length=255)
    verify_token = models.CharField(max_length=255, null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    profile_image = models.CharField(max_length=255, null=True, blank=True)
    country = CountryField(null=True, blank=True, max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user"


class company(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    company_id = models.CharField(primary_key=True, max_length=255)
    company_name = models.CharField(max_length=255, default="")

    class Meta:
        db_table = "company"


class employee(models.Model):
    employee_id = models.CharField(primary_key=True, max_length=255)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="employee_role", null=True)
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)
    report_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')
    deactivated = models.BooleanField(default=False)

    class Meta:
        db_table = "employee"


class team_Table(models.Model):
    team_id = models.CharField(primary_key=True, max_length=255)
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)
    team_name = models.CharField(max_length=255)

    class Meta:
        db_table = "team"


class team_employees(models.Model):
    team_employees_id = models.CharField(primary_key=True, max_length=255)
    team_id = models.ForeignKey(team_Table, on_delete=models.CASCADE)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="team_role", null=True)

    class Meta:
        db_table = "team_employee"


class Goal(models.Model):
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)
    goal_id = models.CharField(primary_key=True, max_length=255)
    session = models.CharField(max_length=255)
    title = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True, max_length=600)
    parent_id = models.CharField(max_length=40, null=True, blank=True)
    average_gain = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    epic_key = models.CharField(max_length=100, null=True, blank=True)
    trello_board_id = models.CharField(max_length=255, null=True, blank=True)
    asana_project_id = models.CharField(max_length=255, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "goal"


class goal_owners(models.Model):
    goal_id = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="goal_owners")
    goal_owner_id = models.CharField(primary_key=True, max_length=255)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    team_id = models.ForeignKey(team_Table, on_delete=models.CASCADE, null=True)

    class Meta:
        db_table = "goal_owner"


class okr(models.Model):
    okr_id = models.CharField(primary_key=True, max_length=255)
    goal_id = models.ForeignKey(Goal, on_delete=models.CASCADE)
    session = models.CharField(max_length=50)
    parent_id = models.CharField(max_length=40, null=True, blank=True)
    title = models.TextField()
    description = models.TextField(max_length=600, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    average_gain = models.IntegerField(default=0)
    story_key = models.CharField(max_length=100, null=True, blank=True)
    trello_card_id = models.CharField(max_length=255, null=True, blank=True)
    trello_checklist_id = models.CharField(max_length=255, null=True, blank=True)
    asana_task_id = models.CharField(max_length=255, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "okr"


class owners(models.Model):
    okr_id = models.ForeignKey(okr, on_delete=models.CASCADE, related_name="owners")
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    owners_id = models.CharField(primary_key=True, max_length=255)
    team_id = models.ForeignKey(team_Table, on_delete=models.CASCADE, null=True)

    class Meta:
        db_table = "okr_owner"


class key_results(models.Model):
    okr_id = models.ForeignKey(okr, on_delete=models.CASCADE, related_name="key_results")
    key_id = models.CharField(primary_key=True, max_length=255)
    title = models.TextField()
    key_result_type = models.CharField(max_length=255)
    unit = models.CharField(max_length=255)
    target_number = models.FloatField()
    initial_number = models.FloatField()
    current_number = models.FloatField()
    description = models.TextField(max_length=600, null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    overall_gain = models.IntegerField(default=0)
    confidence_value = models.IntegerField(default=1)
    subtask_key = models.CharField(max_length=100, null=True, blank=True)
    trello_checklist_item_id = models.CharField(max_length=255, null=True, blank=True)
    asana_subtask_id = models.CharField(max_length=255, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "key_result"


class result_owner(models.Model):
    key_id = models.ForeignKey(key_results, on_delete=models.CASCADE, related_name="result_owner")
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    result_owner_id = models.CharField(primary_key=True, max_length=255)
    team_id = models.ForeignKey(team_Table, on_delete=models.CASCADE, null=True)

    class Meta:
        db_table = "key_result_owner"


class update_key_results(models.Model):
    update_key_id = models.CharField(primary_key=True, max_length=255)
    key_id = models.ForeignKey(key_results, on_delete=models.CASCADE)
    new_number = models.FloatField()
    changed_at = models.DateTimeField()
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    confidence_level = models.CharField(max_length=255)
    note = models.TextField()
    gain = models.IntegerField()

    class Meta:
        db_table = "update_key_results"


class Parents(models.Model):
    parent_id = models.CharField(primary_key=True, max_length=255)
    parent_type = models.CharField(max_length=255)
    child_type = models.CharField(max_length=255)
    okr_id = models.ForeignKey(okr, on_delete=models.CASCADE, null=True)
    key_id = models.ForeignKey(key_results, on_delete=models.CASCADE, null=True)
    goal_id = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True)

    class Meta:
        db_table = "parents"


class Comments(models.Model):
    comment_id = models.CharField(primary_key=True, max_length=255)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)
    text = models.TextField()
    date_created = models.DateTimeField(default=timezone.now)
    okr_id = models.ForeignKey(okr, on_delete=models.CASCADE, null=True)
    key_id = models.ForeignKey(key_results, on_delete=models.CASCADE, null=True)
    update_key_id = models.ForeignKey(update_key_results, on_delete=models.CASCADE, null=True)

    class Meta:
        db_table = "comments"


class Emoji(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    name = models.CharField(max_length=255)
    emoji = models.CharField(max_length=255)
    comment_id = models.ForeignKey(Comments, on_delete=models.CASCADE)
    user_ids = models.JSONField(default=dict)

    class Meta:
        db_table = "emoji"


class Reports(models.Model):
    report_id = models.CharField(primary_key=True, max_length=255)
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "reports"


class JiraConnection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)
    connection_name = models.CharField(max_length=100)
    sub_domain_url = models.URLField()
    username = models.CharField(max_length=100)
    api_token = models.CharField(max_length=300)
    project_key = models.CharField(max_length=100)
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "jira_credentials"
        unique_together = ("user", "company_id")


class TemplateType(Enum):
    weekly_template = "weekly_template"
    monthly_template = "monthly_template"
    quarterly_template = "quarterly_template"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]

    @classmethod
    def values(cls):
        return [item.value for item in cls]


class Template(models.Model):
    description = models.CharField(max_length=500)
    template_title = models.TextField()
    comment_text = models.TextField(null=True, blank=True)
    template_type = models.CharField(max_length=50, choices=TemplateType.choices())  # Use choices method
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    default_temp = models.BooleanField(null=False, default=False)

    def __str__(self):
        return f"{self.title} ({self.template_type.name})"

    class Meta:
        db_table = "template"


class templateUserRelation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    template = models.ForeignKey(Template, on_delete=models.CASCADE, db_column="template_id", null=True)
    company = models.ForeignKey(company, on_delete=models.CASCADE)

    class Meta:
        db_table = "template_user_relation"


class QuestionTitle(models.Model):
    template = models.ForeignKey(Template, related_name="question_titles", on_delete=models.CASCADE)
    question_title = models.TextField()

    class Meta:
        db_table = "question_title"


class Question(models.Model):
    template = models.ForeignKey(Template, related_name="template_questions", on_delete=models.CASCADE)
    text = models.TextField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    question_title = models.ForeignKey(QuestionTitle, related_name="questions", on_delete=models.CASCADE)

    def __str__(self):
        return self.text

    class Meta:
        db_table = "question"


class RecurrenceType(Enum):
    one_time = "one_time"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"
    custom = "custom"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]


class Schedule(models.Model):
    name = models.CharField(max_length=255)
    goal_id = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True)
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    recurrence = models.CharField(
        max_length=50,
        choices=RecurrenceType.choices(),
        default=RecurrenceType.one_time.value,
    )
    start_time = models.DateTimeField(null=True, blank=True)  # When the schedule starts
    end_time = models.DateTimeField(null=True, blank=True)  # When the event ends (optional)
    participations = models.JSONField(null=True, blank=True)
    # Fields for week-based scheduling (store multiple days)
    repeat_on_days = models.JSONField(null=True, blank=True)  # Example: ["Monday", "Wednesday", "Friday"]

    # Fields for month-based scheduling (store multiple days)
    on_week_of_month = models.CharField(max_length=10, null=True, blank=True)  # Store values like '1st', '2nd', etc.
    weekday_of_month = models.JSONField(null=True, blank=True)  # Example: ["Monday", "Wednesday"]

    # Custom recurrence settings
    custom_frequency = models.IntegerField(null=True, blank=True)  # Repeat every X units
    custom_unit = models.CharField(
        max_length=10,
        choices=[
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("year", "Year"),
        ],
        null=True,
        blank=True,
    )  # Custom unit for recurring events

    # End conditions for recurrence
    end_condition = models.CharField(
        max_length=20,
        choices=[
            ("never", "Never"),
            ("on_date", "On a Specific Date"),
            ("after_occurrences", "After X Occurrences"),
        ],
        default="never",
    )
    end_date = models.DateTimeField(null=True, blank=True)  # Used when 'end_condition' is 'on_date'
    occurrences = models.IntegerField(null=True, blank=True)  # Used when 'end_condition' is 'after_occurrences'
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "schedule"

    def __str__(self):
        return self.name


class Room(models.Model):
    room_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    company_id = models.ForeignKey(company, on_delete=models.CASCADE)

    class Meta:
        db_table = "room"


class TempComments(models.Model):
    sender_id = models.CharField(max_length=255)
    receiver_id = models.CharField(max_length=255)
    text = models.CharField(max_length=500, null=True, blank=True)
    Schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "temp_comments"


class StatusType(Enum):
    on_track = "on_track"
    off_track = "off_track"
    behind = "behind"
    in_progress = "in_progress"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]

    @classmethod
    def values(cls):
        return [item.value for item in cls]


class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="user_answers")
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="template_answer",
    )
    answer = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    okr_id = models.ForeignKey(okr, on_delete=models.CASCADE, null=True)
    key_result_id = models.ForeignKey(key_results, on_delete=models.CASCADE, null=True)
    schedule_id = models.ForeignKey(Schedule, on_delete=models.CASCADE, null=True)
    project_status = models.CharField(max_length=50, choices=StatusType.choices())  # Use choices method

    class Meta:
        db_table = "user_answer"


class Feature(models.Model):
    feature_name = models.CharField(max_length=255, default="")

    class Meta:
        db_table = "feature"


class Activity(models.Model):
    activity_name = models.CharField(max_length=255, default="")
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name="activity_features")

    class Meta:
        db_table = "activity"


class RoleAccess(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="roles")
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name="features")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="activities")
    activity_status = models.BooleanField(default=True)
    company = models.ForeignKey(company, on_delete=models.CASCADE, related_name="company")

    class Meta:
        db_table = "role_access"

class EBookContact(models.Model):
    first_name = models.CharField(null=True, blank=True, max_length=50)
    last_name = models.CharField(null=True, blank=True, max_length=50)
    company_name = models.CharField(null=True, blank=True, max_length=100)
    country = CountryField(null=True, blank=True, max_length=100)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(null=True, blank=True, max_length=15)

    class Meta:
        db_table = "ebook_contact"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
