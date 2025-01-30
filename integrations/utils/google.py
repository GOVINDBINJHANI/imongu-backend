from google_auth_oauthlib.flow import Flow
from django.conf import settings
from django.contrib.auth.decorators import login_required
from ..models import GoogleToken
from decouple import config
import uuid, logging
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

GOOGLE_OAUTH_TOKEN_ENDPOINT = config("GOOGLE_OAUTH_TOKEN_ENDPOINT")

GOOGLE_CREDENTIALS = {
    "installed": {
        "client_id": config("GOOGLE_CLIENT_ID"),
        "project_id": "flowing-castle-440806-n4",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": config("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": ["https://dev.imongu.com"],
        "grant_type": "authorization_code",
    }
}


def get_auth_url():
    state_store = {}
    # Initialize the OAuth flow with the credentials and required scopes
    flow = Flow.from_client_config(GOOGLE_CREDENTIALS, scopes=SCOPES)
    flow.redirect_uri = config("GOOGLE_CLIENT_REDIRECT_URI")

    # Generate a unique state
    state = str(uuid.uuid4())
    state_store[state] = True  # Store the state in the dictionary

    # Generate the authorization URL and return it to the frontend
    authorization_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=state)
    return authorization_url, state


def exchange_code_for_token(auth_code):
    # Initialize the flow with the client secrets and required scopes
    flow = Flow.from_client_config(GOOGLE_CREDENTIALS, scopes=SCOPES)
    flow.redirect_uri = config("GOOGLE_CLIENT_REDIRECT_URI")

    # Exchange the authorization code for tokens
    flow.fetch_token(code=auth_code)
    credentials = flow.credentials
    return credentials.to_json()


def is_google_calendar_authorized(user):
    try:
        token = GoogleToken.objects.get(user=user)
        return True

    except GoogleToken.DoesNotExist:
        print("User not authorized google calendar")
        return False


def schedule_google_meet(user, participants, start_datetime, name, id, recurrence):
    creds = None

    # Retrieve the token from the database
    try:
        token_instance = GoogleToken.objects.get(user=user)

        token_json = {
            "token": token_instance.access_token,
            "refresh_token": token_instance.refresh_token,
            "token_uri": token_instance.token_uri,
            "client_id": config("GOOGLE_CLIENT_ID"),
            "client_secret": config("GOOGLE_CLIENT_SECRET"),
            "expiry": token_instance.expiry,
            "scopes": SCOPES,
        }
        # Create credentials from model fields
        creds = Credentials.from_authorized_user_info(token_json, SCOPES)

    except GoogleToken.DoesNotExist:
        print("No credentials found for the user.")
        return

    # Check if credentials are valid, if expired then refresh
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save the updated token data to the database
            token_instance.access_token = creds.token
            token_instance.expiry = creds.expiry
            token_instance.save()
        else:
            print("Credentials are expired and cannot be refreshed.")
            return

    try:
        # Initialize the Calendar API
        service = build("calendar", "v3", credentials=creds)

        if isinstance(start_datetime, str):
            start_datetime = datetime.fromisoformat(start_datetime)

        adjusted_start_time = start_datetime - timedelta(hours=5, minutes=30)
        adjusted_end_time = adjusted_start_time + timedelta(hours=1)
        start_time = adjusted_start_time.isoformat()
        end_time = adjusted_end_time.isoformat()
        event = {
            "summary": name,
            "start": {
                "dateTime": start_time,
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "UTC",
            },
            "conferenceData": {
                "createRequest": {
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    "requestId": f"{id}",
                }
            },
            "attendees": [{"email": email} for email in participants],
        }

        if recurrence:
            event["recurrence"] = [{"rule": recurrence}]

        event = (
            service.events().insert(calendarId="primary", body=event, conferenceDataVersion=1, sendUpdates="all").execute()
        )

        print("Event created with Meet link: %s" % event["hangoutLink"])

    except Exception as error:
        print(f"An error occurred: {error}")


def get_recurrence(recurrence):
    recurrence_dict = {
        "one_time": None,
        "daily": "FREQ=DAILY;COUNT=10",
        "weekly": "FREQ=WEEKLY;INTERVAL=2;COUNT=10",
        "monthly": "FREQ=MONTHLY;BYDAY=1MO;COUNT=12",
        "yearly": "FREQ=YEARLY;BYMONTH=1;BYDAY=SU;COUNT=5",
        "custom": None,
    }
    return recurrence_dict[recurrence]


def revoke_google_token(user):
    try:
        token_entry = GoogleToken.objects.get(user=user)
        revoke_url = "https://oauth2.googleapis.com/revoke"
        requests.post(revoke_url, params={"token": token_entry.access_token})
        token_entry.delete() 
    except GoogleToken.DoesNotExist:
        pass  

