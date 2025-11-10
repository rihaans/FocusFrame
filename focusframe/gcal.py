"""Google Calendar integration for FocusFrame."""
import datetime as dt
import json
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GCAL_AVAILABLE = True
except ImportError:
    GCAL_AVAILABLE = False


# If modifying these scopes, delete the token.pickle file.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class GoogleCalendarManager:
    """Manages Google Calendar authentication and event retrieval."""

    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.pickle"):
        """
        Initialize Google Calendar Manager.

        Args:
            credentials_path: Path to credentials.json from Google Cloud Console
            token_path: Path to save/load authentication token
        """
        if not GCAL_AVAILABLE:
            raise ImportError(
                "Google Calendar integration requires: pip install google-auth google-auth-oauthlib google-api-python-client"
            )

        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds: Optional[Credentials] = None
        self.service = None

    def authenticate(self) -> bool:
        """
        Authenticate with Google Calendar API.

        Returns:
            True if authentication successful, False otherwise
        """
        # Load existing token if available
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as token:
                    self.creds = pickle.load(token)
            except Exception as e:
                print(f"Error loading token: {e}")
                self.creds = None

        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    # Delete invalid token and re-authenticate
                    if os.path.exists(self.token_path):
                        os.remove(self.token_path)
                    self.creds = None

            if not self.creds:
                if not os.path.exists(self.credentials_path):
                    print(f"Error: credentials.json not found at {self.credentials_path}")
                    print("Please download credentials from Google Cloud Console")
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Error during authentication: {e}")
                    return False

            # Save the credentials for the next run
            try:
                with open(self.token_path, 'wb') as token:
                    pickle.dump(self.creds, token)
            except Exception as e:
                print(f"Error saving token: {e}")

        # Build the service
        try:
            self.service = build('calendar', 'v3', credentials=self.creds)
            return True
        except Exception as e:
            print(f"Error building calendar service: {e}")
            return False

    def get_current_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get current and upcoming events from Google Calendar.

        Args:
            max_results: Maximum number of events to retrieve

        Returns:
            List of event dictionaries
        """
        if not self.service:
            if not self.authenticate():
                return []

        try:
            # Get current time in RFC3339 format
            now = dt.datetime.utcnow().isoformat() + 'Z'

            # Call the Calendar API
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return events

        except Exception as e:
            print(f"Error fetching calendar events: {e}")
            return []

    def get_current_event_status(self) -> Tuple[str, Optional[str]]:
        """
        Get current calendar status (busy/free) and event name if in an event.

        Returns:
            Tuple of (status, event_name) where status is "busy" or "free"
        """
        if not self.service:
            if not self.authenticate():
                return "free", None

        try:
            now = dt.datetime.utcnow()

            # Get events for the next hour
            time_min = now.isoformat() + 'Z'
            time_max = (now + dt.timedelta(hours=1)).isoformat() + 'Z'

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Check if currently in an event
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                # Parse times
                try:
                    if 'T' in start:  # DateTime format
                        start_time = dt.datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_time = dt.datetime.fromisoformat(end.replace('Z', '+00:00'))

                        # Convert to local time for comparison
                        start_time = start_time.replace(tzinfo=None)
                        end_time = end_time.replace(tzinfo=None)

                        if start_time <= now <= end_time:
                            event_name = event.get('summary', 'Busy')
                            return "busy", event_name
                except Exception as e:
                    print(f"Error parsing event time: {e}")
                    continue

            return "free", None

        except Exception as e:
            print(f"Error checking calendar status: {e}")
            return "free", None

    def is_authenticated(self) -> bool:
        """Check if already authenticated with Google Calendar."""
        return os.path.exists(self.token_path)

    def disconnect(self) -> None:
        """Disconnect from Google Calendar (remove token)."""
        if os.path.exists(self.token_path):
            try:
                os.remove(self.token_path)
                self.creds = None
                self.service = None
            except Exception as e:
                print(f"Error disconnecting: {e}")
