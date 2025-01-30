from rest_framework import serializers

from .models import (
    User,
    company,
    employee,
    Goal,
    okr,
    owners,
    key_results,
    result_owner,
    update_key_results,
    goal_owners,
    team_Table,
    team_employees,
    Comments,
    Reports,
    Emoji,
    Parents,
    JiraConnection,
    Question,
    Template,
    UserAnswer,
    Schedule,
    QuestionTitle,
    TempComments,
    StatusType,
    Role,
    Feature,
    RoleAccess,
    Activity,
    EBookContact,
)
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from imongu_backend_app.documents import (
    GoalDocument,
    TeamTableDocument,
    OKRDocument,
    KeyResultsDocument,
    ReportDocument,
    EmployeeDocument,
)
import requests
from django.core.exceptions import ObjectDoesNotExist


class userserializers(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["user_id", "username", "email", "profile_image"]


class companyserializers(serializers.ModelSerializer):
    class Meta:
        model = company
        fields = "__all__"


class employeeserializers(serializers.ModelSerializer):
    username = serializers.CharField(source="User.username", read_only=True)
    rolename = serializers.CharField(source="role.role_name", read_only=True)
    country = serializers.CharField(source="user_id.country", read_only=True)

    class Meta:
        model = employee
        fields = "__all__"


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = team_Table
        fields = "__all__"


class Goal_ownersSerializers(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()

    class Meta:
        model = goal_owners
        # fields = "__all__"

        exclude = ["goal_owner_id", "goal_id", "user_id", "team_id"]

    def get_user(self, obj):
        if obj.user_id:
            return {
                "id": obj.user_id.user_id,
                "name": obj.user_id.username,
                "profile_image": obj.user_id.profile_image,
                "type": "user",
            }
        return None

    def get_team(self, obj):
        if obj.team_id:
            return {
                "id": obj.team_id.team_id,
                "name": obj.team_id.team_name,
                "type": "team",
            }
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if instance.user_id:
            user_representation = self.get_user(instance)
            representation.update(user_representation)
            representation.pop("user", None)
        else:
            representation["user"] = None

        if instance.team_id:
            team_representation = self.get_team(instance)
            representation.update(team_representation)
            representation.pop("team", None)
        else:
            representation["team"] = None

        return representation


class GoalSerializers(serializers.ModelSerializer):
    # goal_owners = Goal_ownersSerializers(many=True, read_only=True)
    owners = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        # fields='__all__'
        exclude = ["average_gain"]

    def get_owners(self, obj):
        owners = obj.goal_owners.all()
        return Goal_ownersSerializers(owners, many=True).data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user_id = self.context.get("user_id")

        if user_id:
            # Check if the user_id exists in the goal_owners list
            goal_owners = representation.get("owners", [])
            user_in_goal_owners = any(owner["id"] == user_id for owner in goal_owners)

            if not user_in_goal_owners:
                for owner in goal_owners:
                    team_id = owner["id"]
                    if team_id:
                        team_employee_exists = team_employees.objects.filter(
                            team_id=team_id, user_id=user_id
                        ).exists()
                        if team_employee_exists:
                            user_in_goal_owners = True
                            break

            if not user_in_goal_owners:
                return None

        return representation


class result_ownerserializers(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()

    class Meta:
        model = result_owner
        exclude = ["result_owner_id", "key_id", "user_id", "team_id"]

    def get_user(self, obj):
        if obj.user_id:
            return {
                "id": obj.user_id.user_id,
                "name": obj.user_id.username,
                "profile_image": obj.user_id.profile_image,
                "type": "user",
            }
        return None

    def get_team(self, obj):
        if obj.team_id:
            return {
                "id": obj.team_id.team_id,
                "name": obj.team_id.team_name,
                "type": "team",
            }
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if instance.user_id:
            user_representation = self.get_user(instance)
            representation.update(user_representation)
            representation.pop("user", None)
        else:
            representation["user"] = None

        if instance.team_id:
            team_representation = self.get_team(instance)
            representation.update(team_representation)
            representation.pop("team", None)
        else:
            representation["team"] = None

        return representation


class key_resultsserializers(serializers.ModelSerializer):
    owners = serializers.SerializerMethodField()

    class Meta:
        model = key_results
        fields = "__all__"

    def get_owners(self, obj):
        owners = obj.result_owner.all()
        return result_ownerserializers(owners, many=True).data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user_id = self.context.get("user_id")

        if user_id:
            # Check if the user_id exists in the goal_owners list
            okr_owners = representation.get("owners", [])
            # user_in_okr_owners = any(
            #     owner["id"] == user_id for owner in okr_owners
            # )

            # if not user_in_okr_owners:
            user_in_okr_owners = False
            for owner in okr_owners:
                team_id = owner["id"]
                if team_id:
                    team_employee_exists = team_employees.objects.filter(
                        team_id=team_id, user_id=user_id
                    ).exists()
                    if team_employee_exists:
                        user_in_okr_owners = True
                        break

            if not user_in_okr_owners:
                return None

        return representation


class ownerserializers(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()

    class Meta:
        model = owners
        # fields = "__all__"

        exclude = ["owners_id", "okr_id", "user_id", "team_id"]

    def get_user(self, obj):
        if obj.user_id:
            return {
                "id": obj.user_id.user_id,
                "name": obj.user_id.username,
                "profile_image": obj.user_id.profile_image,
                "type": "user",
            }
        return None

    def get_team(self, obj):
        if obj.team_id:
            return {
                "id": obj.team_id.team_id,
                "name": obj.team_id.team_name,
                "type": "team",
            }
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if instance.user_id:
            user_representation = self.get_user(instance)
            representation.update(user_representation)
            representation.pop("user", None)
        else:
            representation["user"] = None

        if instance.team_id:
            team_representation = self.get_team(instance)
            representation.update(team_representation)
            representation.pop("team", None)
        else:
            representation["team"] = None

        return representation


class okrserializers(serializers.ModelSerializer):
    owners = ownerserializers(many=True, read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = okr
        # fields='__all__'
        exclude = ["average_gain"]

    def get_children(self, obj):
        children = obj.key_results.all()
        return key_resultsserializers(children, many=True).data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user_id = self.context.get("user_id")
        shared = self.context.get("shared")

        representation["average_gain"] = instance.average_gain
        if user_id:
            # Check if the user_id exists in the goal_owners list
            user_in_okr_owners = False
            okr_owners = representation.get("owners", [])
            if not shared and len(okr_owners) > 1:
                user_in_okr_owners = any(owner["id"] == user_id for owner in okr_owners)

            if not user_in_okr_owners:
                for owner in okr_owners:
                    team_id = owner["id"]
                    if team_id:
                        team_employee_exists = team_employees.objects.filter(
                            team_id=team_id, user_id=user_id
                        ).exists()
                        if team_employee_exists:
                            user_in_okr_owners = True
                            break

            if not user_in_okr_owners:
                return None

        return representation


class update_keyresultsserializers(serializers.ModelSerializer):
    class Meta:
        model = update_key_results
        fields = "__all__"


class TeamEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = team_employees
        fields = "__all__"


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comments
        fields = "__all__"


class ReportsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reports
        fields = "__all__"


class EmojiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emoji
        fields = "__all__"


class ParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parents
        fields = "__all__"


class GoalDocumentSerializer(DocumentSerializer):
    class Meta:
        document = GoalDocument
        fields = "__all__"


class OKRDocumentSerializer(DocumentSerializer):
    class Meta:
        document = OKRDocument
        fields = "__all__"


class KeyResultDocumentSerializer(DocumentSerializer):
    class Meta:
        document = KeyResultsDocument
        fields = "__all__"


class EmployeeDocumentSerializer(DocumentSerializer):
    class Meta:
        document = EmployeeDocument
        fields = "__all__"


class TeamTableDocumentSerializer(DocumentSerializer):
    class Meta:
        document = TeamTableDocument
        fields = "__all__"


class ReportDocumentSerializer(DocumentSerializer):
    class Meta:
        document = ReportDocument
        fields = "__all__"


class JiraConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JiraConnection
        fields = "__all__"

    def validate(self, attrs):
        sub_domain_url = f"{attrs.get('sub_domain_url')}/rest/api/2/issue/createmeta"

        headers = {"Content-Type": "application/json"}
        api_token = attrs.get("api_token")
        username = attrs.get("username")
        auth = (username, api_token)
        response = requests.get(sub_domain_url, headers=headers, auth=auth)
        if response.status_code != 200:
            raise serializers.ValidationError(
                {
                    "Error": "Jira credential is invalid Please provide correct credentials"
                }
            )

        return attrs


class UserValidationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()

    def validate_user_id(self, value):
        try:
            User.objects.get(user_id=value)
        except ObjectDoesNotExist:
            raise serializers.ValidationError("User does not exist.")
        return value


class QuestionListSerializer(serializers.Serializer):
    text = serializers.CharField()


class QuestionSerializer(serializers.Serializer):
    question_title = serializers.CharField()
    question_list = QuestionListSerializer(many=True)


class TemplateSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(
        many=True, write_only=True
    )  # This will be used only for writing

    class Meta:
        model = Template
        fields = [
            "id",
            "description",
            "template_type",
            "created_at",
            "updated_at",
            "questions",
            "template_title",
            "comment_text",
            "default_temp",
        ]
        extra_kwargs = {
            "comment_text": {"required": False, "allow_null": True, "allow_blank": True}
        }

    def create(self, validated_data):
        questions_data = validated_data.pop(
            "questions"
        )  # Remove questions from validated_data
        template = Template.objects.create(**validated_data)  # Create the Template

        for question_data in questions_data:
            question_title_instance = QuestionTitle.objects.create(
                template=template, question_title=question_data["question_title"]
            )

            for question_item in question_data["question_list"]:
                Question.objects.create(
                    template=template,
                    question_title=question_title_instance,
                    text=question_item["text"],
                )

        return template

    def update(self, instance, validated_data):
        questions_data = validated_data.pop("questions", [])
        instance.description = validated_data.get("description", instance.description)
        instance.template_type = validated_data.get(
            "template_type", instance.template_type
        )
        instance.template_title = validated_data.get(
            "template_title", instance.template_title
        )
        instance.comment_text = validated_data.get(
            "comment_text", instance.comment_text
        )
        instance.save()

        # Update existing question titles and questions or create new ones
        existing_question_titles = {
            qt.question_title: qt for qt in instance.question_titles.all()
        }

        for question_data in questions_data:
            question_title_text = question_data.get("question_title")
            question_list = question_data.get("question_list", [])

            if question_title_text in existing_question_titles:
                question_title = existing_question_titles[question_title_text]
            else:
                question_title = QuestionTitle.objects.create(
                    template=instance, question_title=question_title_text
                )

            existing_questions = {q.text: q for q in question_title.questions.all()}

            for question_item in question_list:
                question_text = question_item.get("text")
                if question_text in existing_questions:
                    question = existing_questions[question_text]
                    question.text = question_text  # Update text if needed
                    question.save()
                else:
                    Question.objects.create(
                        template=instance,
                        question_title=question_title,
                        text=question_text,
                    )

            # Remove questions not in the updated list
            questions_to_keep = set(q["text"] for q in question_list)
            for question in question_title.questions.all():
                if question.text not in questions_to_keep:
                    question.delete()

        # Remove question titles not in the updated list
        question_titles_to_keep = set(q["question_title"] for q in questions_data)
        for qt in instance.question_titles.all():
            if qt.question_title not in question_titles_to_keep:
                qt.delete()

        return instance


class UserAnswerSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    template = serializers.PrimaryKeyRelatedField(queryset=Template.objects.all())
    okr_id = serializers.PrimaryKeyRelatedField(
        queryset=okr.objects.all(), required=False, allow_null=True
    )
    key_result_id = serializers.PrimaryKeyRelatedField(
        queryset=key_results.objects.all(), required=False, allow_null=True
    )
    schedule_id = serializers.PrimaryKeyRelatedField(
        queryset=Schedule.objects.all(), required=False, allow_null=True
    )
    project_status = serializers.ChoiceField(
        choices=StatusType.choices(), required=True
    )

    class Meta:
        model = UserAnswer
        fields = [
            "user",
            "template",
            "answer",
            "okr_id",
            "key_result_id",
            "schedule_id",
            "project_status",
            "created_at",
        ]

    def validate_project_status(self, value):
        """Ensure project_status is a valid value from StatusType."""
        if value not in StatusType.values():
            raise serializers.ValidationError("Invalid project status.")
        return value

    def create(self, validated_data):
        # Handle any custom logic if needed before creating the instance.
        return super().create(validated_data)


class ScheduleSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        source="user", queryset=User.objects.all()
    )
    participations = serializers.ListField(
        child=serializers.IntegerField(),  # Expecting a list of integers representing user IDs
        required=False,
        allow_empty=True,
    )
    template_type = serializers.CharField(
        source="template.template_type", read_only=True
    )
    template_title = serializers.CharField(
        source="template.template_title", read_only=True
    )
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            "id",
            "user_id",
            "name",
            "recurrence",
            "start_time",
            "end_time",
            "custom_frequency",
            "custom_unit",
            "end_condition",
            "end_date",
            "occurrences",
            "template",
            "participations",
            "created_at",
            "updated_at",
            "goal_id",
            "repeat_on_days",
            "on_week_of_month",
            "weekday_of_month",
            "template_type",
            "template_title",
            "company_id",
            "user_details",
        ]

    def get_user_details(self, obj):
        # Fetch employee details using user_id and company_id
        user = obj.user
        company_id = obj.company_id
        try:
            employee_record = employee.objects.get(user_id=user, company_id=company_id)
            role_name = employee_record.role.role_name
        except employee.DoesNotExist:
            role_name = None

        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "profile_image": user.profile_image,
            "role_name": role_name,
        }

    def create(self, validated_data):
        participations = validated_data.pop("participations", [])
        schedule = Schedule.objects.create(**validated_data)
        schedule.participations = participations
        schedule.save()
        return schedule

    def update(self, instance, validated_data):
        participations = validated_data.pop("participations", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if participations is not None:
            instance.participations = participations
        instance.save()
        return instance

    def validate(self, data):
        # Keep the existing validation logic
        recurrence = data.get("recurrence")
        if recurrence == "custom":
            required_fields = ["custom_frequency", "custom_unit", "end_condition"]
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(
                        f"{field} is required when recurrence is set to custom."
                    )

            end_condition = data.get("end_condition")
            if end_condition == "on_date" and not data.get("end_date"):
                raise serializers.ValidationError(
                    {
                        "end_date": "end_date is required when end_condition is 'on_date'."
                    }
                )
            if end_condition == "after_occurrences" and not data.get("occurrences"):
                raise serializers.ValidationError(
                    {
                        "occurrences": "occurrences are required when end_condition is 'after_occurrences'."
                    }
                )

        return data


class TempCommentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TempComments
        fields = ["id", "sender_id", "receiver_id", "text", "Schedule", "created_at"]


class KeyResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = key_results
        fields = ["key_id", "title", 'overall_gain']


class OKRSerializer(serializers.ModelSerializer):
    key_results = KeyResultSerializer(
        many=True, read_only=True
    )  # Fetch related key results

    class Meta:
        model = okr
        fields = ['okr_id', 'goal_id','title', 'description', 
            'date_created', 'average_gain', 'story_key', 'trello_card_id', 
            'trello_checklist_id', 'asana_task_id', 'is_deleted', 'key_results']



class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = "__all__"


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = "__all__"


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = "__all__"


class RoleFeatureActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleAccess
        fields = "__all__"

    
class HierarchyOKRSerializer(serializers.ModelSerializer):
    key_results = serializers.SerializerMethodField()
    
    class Meta:
        model = okr
        fields = [
            'okr_id', 'title', 'average_gain', 'key_results'
        ]
    
    def get_key_results(self, obj):
        key_results_list = key_results.objects.filter(okr_id=obj.okr_id)
        return KeyResultSerializer(key_results_list, many=True).data

class HierarchyGoalSerializer(serializers.ModelSerializer):
    okrs = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = [
            'goal_id', 'title', 'description', 'session', 'average_gain', 'okrs'
        ]

    def get_okrs(self, obj):
        okrs = okr.objects.filter(goal_id=obj.goal_id)
        return HierarchyOKRSerializer(okrs, many=True).data

class SessionGoalsSerializer(serializers.Serializer):
    session = serializers.CharField()
    goals = serializers.ListField(child=HierarchyGoalSerializer())

class EmployeeHierarchySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    user_profile = userserializers(source='user_id', read_only=True)
    session_goals = serializers.SerializerMethodField()

    class Meta:
        model = employee
        fields = [
            'employee_id', 
            'user_id', 
            'user_profile', 
            'role', 
            'role_name', 
            'report_to', 
            'children', 
            'session_goals'
        ]

    def get_children(self, obj):
        children = employee.objects.filter(report_to=obj)
        return EmployeeHierarchySerializer(children, many=True).data

    def get_role_name(self, obj):
        return obj.role.role_name if obj.role else None

    def get_session_goals(self, obj):
        # Fetch all goals for the given employee
        goals = Goal.objects.filter(goal_owners__user_id=obj.user_id)
        
        # Group goals by session
        grouped_goals = {}
        for goal in goals:
            session_name = goal.session
            if session_name not in grouped_goals:
                grouped_goals[session_name] = []
            grouped_goals[session_name].append(goal)
        
        # Convert grouped data to serialized format
        session_goals_list = []
        for session, goals in grouped_goals.items():
            session_goals_list.append({
                'session': session,
                'goals': HierarchyGoalSerializer(goals, many=True).data
            })
        
        return session_goals_list

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EBookContact
        fields = ['first_name', 'last_name', 'company_name', 'country', 'email', 'phone']