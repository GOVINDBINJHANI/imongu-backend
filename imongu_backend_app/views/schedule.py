from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from imongu_backend_app.models import (
    Schedule,
    User,
    TempComments,
    team_employees,
    goal_owners,
    okr,
    owners,
    result_owner,
    key_results,
    UserAnswer,
)
from imongu_backend_app.Serializers import ScheduleSerializer
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django.utils.dateformat import format as date_format
from datetime import datetime
from django.utils.dateparse import parse_date
from django.core.exceptions import ValidationError
from django.utils.timezone import make_aware, now
from datetime import datetime, timedelta
import sys
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from imongu_backend_app.utils.validate_user_access import (
    validate_user_company_access,
    validate_feature_activity_access,
)
import calendar
from integrations.utils.google import schedule_google_meet, is_google_calendar_authorized, get_recurrence
# from integrations.utils.outlook import *

class ScheduleView(APIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.data.get("company_id")
        feature_name = request.resolver_match.url_name
        activity_name = "Create"
        role_id = validate_user_company_access(user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        if not user_id:
            return Response({"error": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data["user_id"] = user_id
        serializer = ScheduleSerializer(data=data)
        if serializer.is_valid():
            with transaction.atomic():
                schedule = serializer.save()

                # Get the template associated with this schedule
                template = schedule.template

                # Create TempComments for each participant
                if not template.default_temp:
                    for participant_id in schedule.participations or []:
                        TempComments.objects.create(
                            sender_id=str(user.user_id),
                            receiver_id=str(participant_id),
                            text=template.comment_text,
                            Schedule=schedule,
                        )

                # create meet on google calendar
                if is_google_calendar_authorized(user):
                    participants_id = request.data.get("participations")
                    meeting_name = request.data.get("name")
                    date = request.data.get("start_time")
                    recurrence = get_recurrence(request.data.get("recurrence"))
                    participants = [User.objects.get(user_id=user_id).email for user_id in participants_id]
                    schedule_google_meet(user, participants, date, meeting_name, schedule.id, recurrence)

                # if is_microsoft_calendar_authorized(user):
                #     participants_emails = [User.objects.get(user_id=user_id).email]
                #     time = request.data.get("start_time")
                #     meeting_name = request.data.get("name")
                #     recurrence_str = request.data.get("recurrence")
                #     meeting_link = schedule_microsoft_meeting(user, participants_emails, time, meeting_name, schedule.id, recurrence_str)
                #     if meeting_link:
                #         print("Microsoft Teams Meeting created:", meeting_link)


            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        user_id = GetUserId.get_user_id(request)
        schedule_id = request.query_params.get("schedule_id")

        if not user_id:
            return Response({"error": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not schedule_id:
            return Response(
                {"error": "Schedule ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate user existence
        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve the schedule
        try:
            schedule = Schedule.objects.get(
                id=schedule_id,
            )
        except Schedule.DoesNotExist:
            return Response(
                {"error": "Schedule not found or user is not a participant."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Serialize and return the schedule
        serializer = ScheduleSerializer(schedule)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request):
        user_id = GetUserId.get_user_id(request)
        schedule_id = request.query_params.get("schedule_id")

        if not user_id:
            return Response({"error": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not schedule_id:
            return Response(
                {"error": "Schedule ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate user existence
        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve the schedule
        try:
            schedule = Schedule.objects.get(
                id=schedule_id,
            )
        except Schedule.DoesNotExist:
            return Response(
                {"error": "Schedule not found or user is not a participant."},
                status=status.HTTP_404_NOT_FOUND,
            )
        schedule.delete()
        return Response(
            {"message": "User removed from all teams in the schedule."},
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        schedule_id = request.data.get("schedule_id")
        user_id = GetUserId.get_user_id(request)

        if not schedule_id or not user_id:
            return Response(
                {"error": "schedule_id and user_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Fetch the schedule for the specific user and schedule_id
            schedule = Schedule.objects.get(
                pk=schedule_id,
            )
        except Schedule.DoesNotExist:
            return Response(
                {"error": "Schedule not found for the given user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Deserialize the data with the instance to update
        serializer = ScheduleSerializer(schedule, data=request.data, partial=True)

        # Validate and save the data
        if serializer.is_valid():
            recurrence = request.data.get("recurrence")

            # Handle custom recurrence type validation
            if recurrence == "custom":
                required_fields = ["custom_frequency", "custom_unit", "end_condition"]
                for field in required_fields:
                    if not request.data.get(field):
                        return Response(
                            {f"error": f"{field} is required when recurrence is 'custom'."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # Depending on the end_condition, validate end_date or occurrences
                end_condition = request.data.get("end_condition")
                if end_condition == "on_date" and not request.data.get("end_date"):
                    return Response(
                        {"error": "end_date is required when end_condition is 'on_date'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if end_condition == "after_occurrences" and not request.data.get("occurrences"):
                    return Response(
                        {"error": "occurrences are required when end_condition is 'after_occurrences'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            with transaction.atomic():
                serializer.save()

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserScheduleGetView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get("company_id")

        if not user_id or not company_id:
            return Response(
                {"error": "User ID and Company ID are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedules = Schedule.objects.filter(user_id=user_id, company_id=company_id)

        if not schedules.exists():
            return Response([], status=status.HTTP_200_OK)

        schedules = schedules.select_related("template", "user")

        schedule_data = []
        for schedule in schedules:
            serialized_schedule = ScheduleSerializer(schedule).data
            serialized_schedule["participations"] = get_participation_details(schedule.participations)
            serialized_schedule["answer_count"] = get_answer_count(schedule)
            serialized_schedule["day_name"] = get_day_name(schedule)
            serialized_schedule["upcoming_meeting"] = get_next_occurrence(schedule)
            schedule_data.append(serialized_schedule)

        return Response(schedule_data, status=status.HTTP_200_OK)


class ParticipationScheduleGetView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        participation_id = request.query_params.get("participation_id")
        company_id = request.query_params.get("company_id")
        today = make_aware(datetime.now()).date()
        past_week_start = today - timedelta(days=7)

        if not participation_id or not company_id:
            return Response(
                {"error": "Participation ID and Company ID are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            participation_id = int(participation_id)  # Convert participation_id to integer
        except ValueError:
            return Response(
                {"error": "Participation ID must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedules = Schedule.objects.filter(participations__contains=[participation_id], company_id=company_id)

        if not schedules.exists():
            return Response(
                {"Today": [], "Past Week": [], "Upcoming": []},
                status=status.HTTP_200_OK,
            )

        schedules = schedules.select_related("template", "user")

        today_schedule_data = []
        past_week_schedule_data = []
        upcoming_schedule_data = []

        for schedule in schedules:
            schedule_date = schedule.start_time.date()  # Assuming start_time is a datetime field
            next_occurrence = get_next_occurrence(schedule)
            if is_today(schedule, today):
                serialized_schedule = ScheduleSerializer(schedule).data
                serialized_schedule["participations"] = get_participation_details(schedule.participations)
                serialized_schedule["answer_count"] = get_answer_count(schedule)
                serialized_schedule["day_name"] = get_day_name(schedule)
                serialized_schedule["upcoming_date"] = get_next_occurrence(schedule)
                today_schedule_data.append(serialized_schedule)

            elif past_week_start <= schedule_date < today:  # Check if it's in the past week
                serialized_schedule = ScheduleSerializer(schedule).data
                serialized_schedule["participations"] = get_participation_details(schedule.participations)
                serialized_schedule["answer_count"] = get_answer_count(schedule)
                serialized_schedule["day_name"] = get_day_name(schedule)
                past_week_schedule_data.append(serialized_schedule)

            if next_occurrence:
                serialized_schedule = ScheduleSerializer(schedule).data
                serialized_schedule["participations"] = get_participation_details(schedule.participations)
                serialized_schedule["answer_count"] = get_answer_count(schedule)
                serialized_schedule["day_name"] = get_day_name(schedule)
                serialized_schedule["upcoming_date"] = get_next_occurrence(schedule)
                upcoming_schedule_data.append(serialized_schedule)

        return Response(
            {
                "Today": today_schedule_data,
                "Past Week": past_week_schedule_data,
                "Upcoming": upcoming_schedule_data,
            },
            status=status.HTTP_200_OK,
        )


class GoalUserAPIView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        # Get goal_id from request
        goal_id = request.query_params.get("goal_id")

        if not goal_id:
            return Response({"error": "Goal ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Initialize a set to collect unique user_ids
            user_ids = set()

            # 1. Fetch goal owners and associated teams' employees
            goal_owner_entries = goal_owners.objects.filter(goal_id=goal_id)

            for owner in goal_owner_entries:
                # Add goal owner's user_id
                if owner.user_id:
                    user_ids.add(owner.user_id.user_id)

                # Fetch associated team's employees
                if owner.team_id:
                    team_employees_entries = team_employees.objects.filter(team_id=owner.team_id)
                    for employee in team_employees_entries:
                        user_ids.add(employee.user_id.user_id)

            # 2. Fetch OKR owners and associated teams' employees
            okr_entries = okr.objects.filter(goal_id=goal_id)
            for okr_entry in okr_entries:
                okr_owners_entries = owners.objects.filter(okr_id=okr_entry)

                for owner in okr_owners_entries:
                    # Add OKR owner's user_id
                    if owner.user_id:
                        user_ids.add(owner.user_id.user_id)

                    # Fetch associated team's employees
                    if owner.team_id:
                        team_employees_entries = team_employees.objects.filter(team_id=owner.team_id)
                        for employee in team_employees_entries:
                            user_ids.add(employee.user_id.user_id)

            # 3. Fetch key results' owners and associated teams' employees
            for okr_entry in okr_entries:
                key_results_entries = key_results.objects.filter(okr_id=okr_entry)

                for key_result in key_results_entries:
                    result_owner_entries = result_owner.objects.filter(key_id=key_result)

                    for result_owner_entry in result_owner_entries:
                        # Add key result owner's user_id
                        if result_owner_entry.user_id:
                            user_ids.add(result_owner_entry.user_id.user_id)

                        # Fetch associated team's employees
                        if result_owner_entry.team_id:
                            team_employees_entries = team_employees.objects.filter(team_id=result_owner_entry.team_id)
                            for employee in team_employees_entries:
                                user_ids.add(employee.user_id.user_id)

            # Fetch User details based on collected user_ids
            users = User.objects.filter(user_id__in=user_ids).values("user_id", "username", "profile_image")

            return Response({"users": list(users)}, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle any other exceptions
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminGoalDetailsView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get("company_id")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        session_number = request.query_params.get("session")

        schedules = Schedule.objects.filter(user__user_id=user_id, company_id=company_id)

        try:
            if start_date:
                start_date = parse_date(start_date.strip())
                if not start_date:
                    raise ValidationError("Invalid start_date format")
            if end_date:
                end_date = parse_date(end_date.strip())
                if not end_date:
                    raise ValidationError("Invalid end_date format")
            if start_date and end_date and start_date > end_date:
                raise ValidationError("start_date cannot be later than end_date")
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if start_date and end_date:
            schedules = schedules.filter(created_at__range=[start_date, end_date])

        # Update the schedules query with session number filtering
        if session_number:
            schedules = schedules.filter(goal_id__session=session_number)

        if not schedules.exists():
            return Response([], status=status.HTTP_200_OK)

        results = []
        grouped_results = {}

        # Step 2: Extract goal details for each schedule
        for schedule in schedules:
            goal = schedule.goal_id
            goal_title = goal.title if goal else None
            goal_session = goal.session if goal else None

            # Fetch the template ID and title from the schedule
            schedule_id = schedule.pk
            template_id = schedule.template.pk if schedule.template else None
            template_title = schedule.template.template_title if schedule.template else None
            template_type = schedule.template.template_type if schedule.template else None
            # Step 3: Fetch participations from the schedule
            participations = schedule.participations if schedule.participations else []

            participations_data = []
            total_participations = len(participations)
            participants_with_answers = 0

            # Step 4: For each participation, get the relevant data
            for participation_id in participations:
                # Fetch OKRs and Key Results using UserAnswer data
                user_answers = UserAnswer.objects.filter(user_id=participation_id, schedule_id=schedule)

                if user_answers.exists():
                    participants_with_answers += 1

                    for user_answer in user_answers:
                        # participant = User.objects.filter(user_id=participation_id).first()
                        participations_data.append(
                            {
                                "okr_title": (user_answer.okr_id.title if user_answer.okr_id else None),
                                "key_result_title": (
                                    user_answer.key_result_id.title if user_answer.key_result_id else None
                                ),
                                "project_status": user_answer.project_status,
                                "overall_gain": (
                                    round(user_answer.key_result_id.overall_gain, 2) if user_answer.key_result_id else None
                                ),
                                "session": goal_session,
                                "participant_name": user_answer.user.username,  # Direct access, assuming participation_id is a User instance
                                "participant_profile_pic": (
                                    user_answer.user.profile_image if user_answer.user.profile_image else None
                                ),
                                "participant_id": user_answer.user.user_id,
                            }
                        )
                else:
                    participant = User.objects.filter(user_id=participation_id).first()
                    participations_data.append(
                        {
                            "participant_name": (participant.username if participant else None),
                            "participant_profile_pic": (
                                participant.profile_image if participant and participant.profile_image else None
                            ),
                            "participant_id": participant.user_id if participant else None, 
                        }
                    )

            # Calculate the percentage of participants who gave answers
            value = round((participants_with_answers / total_participations * 100) if total_participations > 0 else 0, 2)

            # Group data by goal_id
            if goal.goal_id not in grouped_results:
                grouped_results[goal.goal_id] = {
                    "goal_id": goal.goal_id,
                    "goal_title": goal_title,
                    "templates": [],
                }

            # Append participations data to the corresponding goal
            grouped_results[goal.goal_id]["templates"].append(
                {
                    "template_id": template_id,
                    "template_title": template_title,
                    "schedule_id": schedule_id,
                    "template_type": template_type,
                    "key_results": participations_data,
                    "value": value,
                }
            )
        # Convert grouped results to a list
        results = list(grouped_results.values())

        return Response(results, status=status.HTTP_200_OK)


def get_participation_details(participation_ids):
    participation_profiles = User.objects.filter(user_id__in=participation_ids).values(
        "user_id", "profile_image", "username", "email"
    )
    return [
        {
            "id": profile["user_id"],
            "profile_image": profile["profile_image"],
            "username": profile["username"],
            "email": profile["email"],
        }
        for profile in participation_profiles
    ]


def get_answer_count(schedule):
    total_participants = len(schedule.participations)
    answered_participants = UserAnswer.objects.filter(
        user_id__in=schedule.participations, schedule_id=schedule.id
    ).count()
    return f"{answered_participants} out of {total_participants}"


def get_day_name(schedule):
    if schedule.recurrence in ["one_time", "daily", "weekly", "monthly", "yearly"]:
        return [date_format(schedule.start_time, "l")[:3]]  # 'l' returns the full day name
    elif schedule.recurrence == "custom":
        if schedule.custom_unit in ["day", "year"]:
            return [date_format(schedule.start_time, "l")[:3]]
        elif schedule.custom_unit == "week":
            return [day[:3] for day in schedule.repeat_on_days or []]
        elif schedule.custom_unit == "month":
            return [day[:3] for day in schedule.weekday_of_month or []]
    return []


def is_today(schedule, today):
    """
    Determines if the given schedule occurs today based on its recurrence.
    """
    start_time = schedule.start_time.date()  # Get only the date part
    recurrence = schedule.recurrence

    if recurrence == "one_time":
        # One-time event happens on the start date
        return start_time == today

    elif recurrence == "daily":
        # Daily event repeats every day
        return today >= start_time

    elif recurrence == "weekly":
        # Weekly event occurs on the same weekday as start_time
        return (today >= start_time) and (start_time.weekday() == today.weekday())

    elif recurrence == "monthly":
        # Monthly event repeats on the same day of the month
        return start_time.day == today.day

    elif recurrence == "yearly":
        # Yearly event repeats on the same month and day
        return start_time.month == today.month and start_time.day == today.day

    elif recurrence == "custom":
        # Custom recurrence logic based on custom_frequency and custom_unit
        return today >= start_time and check_custom(schedule, today)

    return False


def check_custom(schedule, today):
    """
    Handles custom recurrence logic.
    """
    start_time = schedule.start_time.date()
    custom_frequency = schedule.custom_frequency
    custom_unit = schedule.custom_unit
    repeat_on_days = schedule.repeat_on_days  # If relevant (for weekly recurrences)

    # Check if the current day is in repeat_on_days
    if today.strftime("%A") not in repeat_on_days:
        return False

    if schedule.end_condition == "on_date" and schedule.end_date and today > schedule.end_date.date():
        # If recurrence ends on a specific date and today is after that date
        return False

    if schedule.end_condition == "after_occurrences" and schedule.occurrences:
        # Implement occurrence-based logic if needed
        return False

    if custom_unit == "day":
        delta_days = (today - start_time).days
        return delta_days % custom_frequency == 0

    elif custom_unit == "week":
        # Weekly custom recurrence; check the specified weekdays
        delta_weeks = (today - start_time).days // 7
        return delta_weeks % custom_frequency == 0

    elif custom_unit == "month":
        delta_months = (today.year - start_time.year) * 12 + (today.month - start_time.month)
        return delta_months % custom_frequency == 0 and start_time.day == today.day

    elif custom_unit == "year":
        delta_years = today.year - start_time.year
        return delta_years % custom_frequency == 0 and start_time.month == today.month and start_time.day == today.day

    return False


def get_next_occurrence(schedule):
    start_time = schedule.start_time
    recurrence = schedule.recurrence
    current_time = now()

    if recurrence == "one_time":
        # For one-time events, return start time if it's in the future
        return start_time if start_time > current_time else None

    # Initialize the next occurrence to start_time
    next_occurrence = start_time
    frequency = schedule.custom_frequency or 1  # Default to 1 if custom frequency is None

    # Loop until next_occurrence is in the future
    while next_occurrence <= current_time:
        if recurrence == "daily":
            next_occurrence += timedelta(days=1)
        elif recurrence == "weekly":
            next_occurrence += timedelta(weeks=1)
        elif recurrence == "monthly":
            # Calculate the next month while accounting for year change
            month = (next_occurrence.month % 12) + 1
            year = next_occurrence.year + (next_occurrence.month + 1) // 12
            day = min(next_occurrence.day, calendar.monthrange(year, month)[1])  # Adjust for end of month
            next_occurrence = next_occurrence.replace(year=year, month=month, day=day)
        elif recurrence == "yearly":
            next_occurrence = next_occurrence.replace(year=next_occurrence.year + 1)
        elif recurrence == "custom":
            if schedule.custom_unit == "day":
                next_occurrence += timedelta(days=frequency)
            elif schedule.custom_unit == "week":
                next_occurrence += timedelta(weeks=frequency)
            elif schedule.custom_unit == "month":
                month = (next_occurrence.month + frequency - 1) % 12 + 1
                year = next_occurrence.year + ((next_occurrence.month + frequency - 1) // 12)
                day = min(next_occurrence.day, calendar.monthrange(year, month)[1])
                next_occurrence = next_occurrence.replace(year=year, month=month, day=day)
            elif schedule.custom_unit == "year":
                next_occurrence = next_occurrence.replace(year=next_occurrence.year + frequency)

    return next_occurrence
