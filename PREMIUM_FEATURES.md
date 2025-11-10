# FocusFrame Premium Edition - Feature Overview

This document outlines all the premium enhancements added to FocusFrame.

## Overview

FocusFrame Premium Edition includes significant UI/UX improvements and Google Calendar integration for intelligent, context-aware notification management.

---

## 1. Premium UI Improvements

### Enhanced Visual Design

#### Modern Color Scheme
- **Deep dark theme** with professional indigo/purple accent colors
- **Improved contrast** for better readability
- **Consistent color palette** across all UI elements
- Premium gradient effects on interactive elements

#### Typography & Spacing
- **Larger, bolder fonts** for better hierarchy
- **Improved spacing** between elements for cleaner look
- **Professional font sizing**:
  - Titles: 18pt bold
  - Cards: 11pt bold
  - Emotion display: 44pt bold

#### Enhanced Components
- **Styled buttons** with hover and active states
- **Modern tab design** with visual selection indicators
- **Professional progress bars** with custom styling
- **Bordered text panels** with subtle highlights

### Fixed Data Display Issues

#### Battery Status Display
- **Before**: Showed "None" when battery info unavailable
- **After**: Shows actual percentage (e.g., "85%") or "AC Power" when plugged in
- Location: dashboard.py:223-229

#### Time Formatting
- **Before**: Time not displayed in context panel
- **After**: Shows formatted timestamp (e.g., "14:23:45") in context
- Location: dashboard.py:220-222

#### Network Data Display
- **Before**: Raw bytes (e.g., "5234234234")
- **After**: Human-readable format with auto-scaling:
  - Bytes (< 1 KB)
  - KB (< 1 MB)
  - MB (< 1 GB)
  - GB (≥ 1 GB)
- Location: dashboard.py:233-242

#### System Metrics
- **CPU %**: Displayed with one decimal precision
- **Memory %**: Displayed with one decimal precision
- **All metrics**: Properly formatted with units

### Window & Layout Improvements
- **Larger default size**: 1024x720 (was 960x640)
- **Improved minimum size**: 920x600 (was 880x560)
- **Better padding and margins** throughout
- **Responsive layout** that scales properly

---

## 2. Google Calendar Integration

### Features

#### Real-Time Calendar Awareness
- Connects to your Google Calendar via OAuth 2.0
- Reads calendar events in real-time
- Determines if you're currently busy (in a meeting/event)
- Uses calendar state for notification decisions

#### Context Integration
- Calendar status appears in Live Feed context panel
- Shows "busy" or "free" status
- Displays current event name when busy
- Updates automatically with calendar changes

### Dashboard Menu Options

#### Calendar Menu (New)
Access via the menu bar when Google Calendar packages are installed:

1. **Connect Google Calendar**
   - Initiates OAuth authentication flow
   - Opens browser for Google sign-in
   - Stores credentials securely

2. **Disconnect Google Calendar**
   - Removes saved authentication
   - Falls back to static calendar

3. **View Upcoming Events**
   - Shows next 10 calendar events
   - Formatted with times and titles
   - Easy-to-read event list

4. **Check Calendar Status**
   - Shows current busy/free status
   - Displays active event if busy

### Security & Privacy
- **Read-only access**: Cannot modify your calendar
- **Local storage**: Tokens saved locally in `token.pickle`
- **OAuth 2.0**: Industry-standard authentication
- **Easy revocation**: Disconnect anytime via menu or Google settings

### Fallback Behavior
- Automatically falls back to static calendar if:
  - Google Calendar not configured
  - Authentication fails
  - Network unavailable
  - User disconnects
- Seamless transition ensures app always works

---

## 3. Configuration Enhancements

### New Config Options

Add to your `config.yaml`:

```yaml
calendar:
  # Enable Google Calendar integration
  use_google_calendar: true

  # OAuth credentials file (download from Google Cloud Console)
  google_credentials_path: "credentials.json"

  # Token storage (auto-generated after first auth)
  google_token_path: "token.pickle"

  # Static calendar blocks (used as fallback)
  busy_blocks:
    - name: "Morning Focus"
      days: ["mon", "tue", "wed", "thu", "fri"]
      start: "09:00"
      end: "12:00"
```

---

## 4. Technical Improvements

### Code Organization
- New module: `focusframe/gcal.py` - Google Calendar integration
- Enhanced: `focusframe/context.py` - Calendar context management
- Enhanced: `focusframe/dashboard.py` - UI improvements and calendar menu
- Enhanced: `focusframe/main.py` - Integration with context manager

### Dependencies
Added to requirements.txt:
```
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
google-api-python-client>=2.100.0
```

### Error Handling
- Graceful fallback when Google Calendar unavailable
- User-friendly error messages
- Console logging for debugging
- Automatic retry on token refresh

### Performance
- Cached authentication tokens
- Efficient calendar API calls
- No blocking operations on UI thread
- Minimal performance impact

---

## 5. Getting Started

### Quick Start (Without Google Calendar)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run FocusFrame:
   ```bash
   python -m focusframe.main
   ```

3. Enjoy the premium UI improvements!

### Full Setup (With Google Calendar)

1. Install all dependencies including Google Calendar packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Follow the [Google Calendar Setup Guide](GOOGLE_CALENDAR_SETUP.md)

3. Update your `config.yaml` to enable Google Calendar

4. Run FocusFrame and authenticate when prompted

---

## 6. Visual Comparison

### Before vs After

#### Display Issues Fixed
| Component | Before | After |
|-----------|--------|-------|
| Battery | "None" | "85%" or "AC Power" |
| Time | Not shown | "14:23:45" |
| Network | "5234234234" | "4.9 GB" |
| CPU | "45.2" | "45.2%" |

#### UI Improvements
| Element | Before | After |
|---------|--------|-------|
| Window Size | 960x640 | 1024x720 |
| Title Font | 16pt | 18pt bold |
| Emotion Font | 42pt | 44pt bold |
| Tab Padding | Minimal | 16x10 spacious |
| Progress Bar | Basic | Custom styled |
| Text Panels | No borders | Subtle highlights |

---

## 7. Feature Highlights

### Intelligent Context Awareness
- **15+ context variables** tracked in real-time
- **Calendar integration** for meeting awareness
- **App categorization** (focus vs casual)
- **Time-of-day awareness** (morning, afternoon, evening, night)
- **Work hours detection**
- **System resource monitoring**

### Professional Dashboard
- **Live emotion feed** with confidence scores
- **Visual timeline** with color-coded emotions
- **Recent snapshots** panel
- **Context display** with all metrics
- **Rules studio** for customization
- **Analytics insights** tab
- **Export capabilities** (summary, CSV)

### Smart Notification Management
- **Rule-based decisions** (deliver, defer, batch)
- **Emotion-aware** deferral
- **Calendar-aware** timing
- **Context-based** intelligence
- **User feedback loop** for learning

---

## 8. Files Modified/Created

### New Files
- `focusframe/gcal.py` - Google Calendar integration module
- `GOOGLE_CALENDAR_SETUP.md` - Detailed setup instructions
- `PREMIUM_FEATURES.md` - This documentation

### Modified Files
- `focusframe/dashboard.py` - UI improvements + calendar menu
- `focusframe/context.py` - Google Calendar integration
- `focusframe/main.py` - Pass context_manager to dashboard
- `requirements.txt` - Added Google Calendar dependencies

---

## 9. Backward Compatibility

All changes are **fully backward compatible**:
- Works without Google Calendar packages installed
- Falls back to static calendar configuration
- All existing features remain functional
- No breaking changes to config format
- Optional dependencies (Google Calendar won't break if not installed)

---

## 10. Future Enhancements

Potential future improvements:
- Multiple calendar support
- Calendar event filtering by type
- Visual calendar widget in dashboard
- Calendar event notifications
- Meeting duration predictions
- Focus time suggestions based on calendar

---

## Support & Documentation

- **Setup Guide**: See [GOOGLE_CALENDAR_SETUP.md](GOOGLE_CALENDAR_SETUP.md)
- **Main README**: See [README.md](README.md)
- **Configuration**: See `config.yaml` for all options
- **Issues**: Report bugs via project repository

---

## Summary

FocusFrame Premium Edition transforms the application with:
1. ✅ **Professional UI** - Modern, clean, and visually appealing
2. ✅ **Fixed Display Issues** - All data properly formatted
3. ✅ **Google Calendar** - Real-time event integration
4. ✅ **Enhanced Context** - Better awareness for smarter decisions
5. ✅ **Easy Setup** - Comprehensive documentation
6. ✅ **Backward Compatible** - Works with or without new features

Enjoy your premium FocusFrame experience!
