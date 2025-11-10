# Google Calendar Integration Setup

FocusFrame Premium Edition includes Google Calendar integration to provide real-time calendar event awareness for better notification management.

## Prerequisites

1. Python 3.7 or higher
2. A Google account with Google Calendar access
3. Internet connection for initial setup

## Installation Steps

### 1. Install Required Python Packages

```bash
pip install google-auth google-auth-oauthlib google-api-python-client
```

Or update your requirements.txt and run:

```bash
pip install -r requirements.txt
```

### 2. Set Up Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Library"
4. Search for "Google Calendar API" and enable it

### 3. Create OAuth 2.0 Credentials

1. In Google Cloud Console, go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" user type
   - Fill in the application name (e.g., "FocusFrame")
   - Add your email as a test user
   - Save and continue through the remaining steps
4. Return to "Credentials" and create OAuth client ID:
   - Application type: "Desktop app"
   - Name: "FocusFrame Desktop"
5. Click "Download JSON" and save the file

### 4. Configure FocusFrame

1. Rename the downloaded JSON file to `credentials.json`
2. Place `credentials.json` in the root of your FocusFrame project directory
3. Update your `config.yaml` to enable Google Calendar:

```yaml
calendar:
  use_google_calendar: true
  google_credentials_path: "credentials.json"  # Optional, defaults to this
  google_token_path: "token.pickle"            # Optional, defaults to this

  # Static calendar blocks (used as fallback)
  busy_blocks: []
```

### 5. First-Time Authentication

1. Run FocusFrame normally:
   ```bash
   python -m focusframe.main
   ```

2. On first run, a browser window will open asking you to:
   - Sign in to your Google account
   - Grant FocusFrame permission to read your calendar (read-only access)
   - The authorization will be saved in `token.pickle` for future use

3. Once authenticated, you'll see:
   ```
   [FocusFrame] Google Calendar integration enabled
   ```

## Using Google Calendar in FocusFrame

### Dashboard Menu Options

FocusFrame Premium Edition includes a "Calendar" menu with the following options:

1. **Connect Google Calendar**
   - Manually trigger authentication
   - Use if you want to switch accounts or re-authenticate

2. **Disconnect Google Calendar**
   - Removes saved authentication token
   - Falls back to static calendar configuration

3. **View Upcoming Events**
   - Shows next 10 upcoming calendar events
   - Displays event titles and start times

4. **Check Calendar Status**
   - Shows if you're currently in a calendar event
   - Displays current event name if busy

### How It Works

- FocusFrame checks your Google Calendar in real-time
- If you're currently in a scheduled event, your calendar state is "busy"
- Otherwise, your calendar state is "free"
- This information is used by the rule engine to make smarter notification decisions
- For example: defer notifications during important meetings

### Context Panel Display

The Live Feed tab shows your calendar status in the context panel:
- **Calendar**: Shows "busy" or "free"
- **Event**: Shows current event name when busy

## Configuration Options

Add these to your `config.yaml` under the `calendar` section:

```yaml
calendar:
  # Enable/disable Google Calendar integration
  use_google_calendar: true

  # Path to Google OAuth credentials (from Google Cloud Console)
  google_credentials_path: "credentials.json"

  # Path to save authentication token (auto-generated)
  google_token_path: "token.pickle"

  # Static calendar blocks (used when Google Calendar is disabled or unavailable)
  busy_blocks:
    - name: "Morning Focus"
      days: ["mon", "tue", "wed", "thu", "fri"]
      start: "09:00"
      end: "12:00"
```

## Troubleshooting

### "Google Calendar integration not available"

**Solution**: Install required packages:
```bash
pip install google-auth google-auth-oauthlib google-api-python-client
```

### "credentials.json not found"

**Solution**:
1. Download OAuth credentials from Google Cloud Console
2. Rename the file to `credentials.json`
3. Place it in the FocusFrame project root directory

### "Authentication failed"

**Solutions**:
1. Delete `token.pickle` and try authenticating again
2. Check that the Google Calendar API is enabled in your Google Cloud project
3. Verify you're using a valid Google account
4. Make sure your email is added as a test user if the app is not published

### "Error fetching calendar events"

**Solutions**:
1. Check your internet connection
2. Verify your Google account has calendar access
3. Try disconnecting and reconnecting in the Calendar menu
4. Check the console for detailed error messages

### Calendar not updating

**Solution**: Calendar status is checked each time a context snapshot is taken (default: every 2 seconds). Events should appear with minimal delay.

## Privacy & Security

- **Read-Only Access**: FocusFrame only requests read permission for your calendar
- **Local Storage**: Authentication tokens are stored locally in `token.pickle`
- **No Data Sent**: Calendar data is only used locally for context awareness
- **Revoke Access**: You can revoke access anytime from your [Google Account Settings](https://myaccount.google.com/permissions)

## Fallback Behavior

If Google Calendar integration fails or is disabled, FocusFrame automatically falls back to using static calendar blocks defined in `config.yaml`. This ensures the application continues to work even without calendar integration.

## Advanced Configuration

### Multiple Calendar Support

To support multiple calendars, you can modify the `get_current_events` method in `focusframe/gcal.py` to specify different calendar IDs instead of `'primary'`.

### Custom Time Windows

Edit the time windows in `get_current_event_status` method in `focusframe/gcal.py` to look further ahead or behind the current time.

### Event Filtering

You can add logic in `gcal.py` to filter events by title, attendees, or other properties to customize which events mark you as "busy".

## Support

For issues or questions:
1. Check the console output for detailed error messages
2. Review the troubleshooting section above
3. Ensure all prerequisites are met
4. File an issue on the project repository with detailed logs

---

**Note**: Google Calendar integration is optional. FocusFrame works perfectly with static calendar configuration if you prefer not to connect your Google account.
