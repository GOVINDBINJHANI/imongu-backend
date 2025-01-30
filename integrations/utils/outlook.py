from msal import ConfidentialClientApplication
from datetime import datetime, timedelta
from ..models import MicrosoftToken
import urllib.parse
from django.conf import settings
import requests
from django.utils import timezone
import requests
from django.utils.timezone import now
import logging
logger = logging.getLogger(__name__)

def get_microsoft_auth_url():
    try:
        base_auth_url = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize".format(
            tenant_id=settings.MICROSOFT_TENANT_ID
        )
        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(settings.MICROSOFT_SCOPES),
            "state": "random_state_string",
        }
        auth_url = f"{base_auth_url}?{urllib.parse.urlencode(params)}"
        return auth_url
    except Exception as e:
        raise Exception(f"Failed to generate Microsoft authorization URL: {str(e)}")


def exchange_microsoft_code_for_token(auth_code):
    try:
        app = ConfidentialClientApplication(
            settings.MICROSOFT_CLIENT_ID,
            authority=settings.MICROSOFT_AUTHORITY,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
        )
        result = app.acquire_token_by_authorization_code(
            auth_code, settings.MICROSOFT_SCOPES, redirect_uri=settings.MICROSOFT_REDIRECT_URI
        )
        if "error" in result:
            raise Exception(f"Token exchange failed: {result['error_description']}")
        return result
    except Exception as e:
        raise Exception(f"Failed to exchange authorization code for token: {str(e)}")


def refresh_microsoft_token(user):
    microsoft_token = MicrosoftToken.objects.get(user=user)
    url = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token".format(
            tenant_id=settings.MICROSOFT_TENANT_ID
        )
    data = {
        "grant_type": "refresh_token",
       "client_id": settings.MICROSOFT_CLIENT_ID,
        "client_secret": settings.MICROSOFT_CLIENT_SECRET ,
        "refresh_token": microsoft_token.refresh_token,
        "scope": "Calendars.ReadWrite OnlineMeetings.ReadWrite profile openid offline_access",
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        token_data = response.json()
        microsoft_token.access_token = token_data.get("access_token")
        microsoft_token.refresh_token = token_data.get("refresh_token", microsoft_token.refresh_token)
        microsoft_token.expiry = now() + timedelta(seconds=token_data.get("expires_in", 3600))
        microsoft_token.save()
        return microsoft_token
    else:
        raise Exception(f"Failed to refresh token: {response.json().get('error_description', 'Unknown error')}")


def is_microsoft_calendar_authorized(user):
    try:
        token = MicrosoftToken.objects.get(user=user)
        return True
    except MicrosoftToken.DoesNotExist:
        logger.error("User not authorized for Microsoft calendar")
        return False
    

def schedule_microsoft_meeting(user, participants, start_datetime, meeting_name, schedule_id, recurrence_str):
    try:
        token_instance = MicrosoftToken.objects.get(user=user)
        if token_instance.expiry < now():
            logger.info("Access token expired, refreshing...")
            token_instance = refresh_microsoft_token(user)

        access_token = token_instance.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        if isinstance(start_datetime, str):
            start_datetime = datetime.fromisoformat(start_datetime)

        start_time = start_datetime.astimezone(timezone.utc).isoformat()
        end_time = (start_datetime + timedelta(hours=1)).astimezone(timezone.utc).isoformat()

        if not (participants and start_time and end_time and meeting_name):
            logger.error("Missing required fields for meeting scheduling.")
            return None

        online_meeting_body = {
                "subject": meeting_name,
                "start": {
                    "dateTime": start_time,
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": "UTC"
                },
                "attendees": [{"emailAddress": {"address": email}, "type": "required"} for email in participants],
                "isOnlineMeeting": True,
                "onlineMeetingProvider": "teamsForBusiness"
            }
        if recurrence_str:
            recurrence = get_recurrence(
                recurrence_str,
                start_datetime.date().isoformat(),
                (start_datetime + timedelta(days=30)).date().isoformat()
            )
            if recurrence:
                online_meeting_body["recurrence"] = recurrence
        logger.debug(f"Payload being sent: {online_meeting_body}")

        url = "https://graph.microsoft.com/v1.0/me/events"
        response = requests.post(url, headers=headers, json=online_meeting_body )

        if response.status_code == 201:
            event_data = response.json()
            meeting_link = event_data.get("onlineMeeting", {}).get("joinUrl", None)
            logger.info("Teams meeting created:", meeting_link)
            return meeting_link
        else:
            logger.error(f"Error scheduling Microsoft meeting: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return None  

def get_recurrence(recurrence, start_date, end_date, interval=1):
    if recurrence == "daily":
        return {
            "pattern": {
                "type": "daily",
                "interval": interval,
            },
            "range": {
                "type": "endDate",
                "startDate": start_date,
                "endDate": end_date,
            },
        }
    elif recurrence == "weekly":
        return {
            "pattern": {
                "type": "weekly",
                "interval": interval,
            },
            "range": {
                "type": "endDate",
                "startDate": start_date,
                "endDate": end_date,
            },
        }
    elif recurrence == "monthly":
        return {
            "pattern": {
                "type": "absoluteMonthly",
                "interval": interval,
                "daysOfMonth": [start_date.split("-")[2]],
            },
            "range": {
                "type": "endDate",
                "startDate": start_date,
                "endDate": end_date,
            },
        }
    elif recurrence == "yearly":
        return {
            "pattern": {
                "type": "absoluteYearly",
                "interval": interval,
                "daysOfMonth": [start_date.split("-")[2]],
                "monthsOfYear": [int(start_date.split("-")[1])],
            },
            "range": {
                "type": "endDate",
                "startDate": start_date,
                "endDate": end_date,
            },
        }
    return None

