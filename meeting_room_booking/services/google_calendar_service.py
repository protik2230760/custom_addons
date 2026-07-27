# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests
from datetime import datetime, timedelta
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

def get_google_access_token(env):
    """
    Retrieves the stored access token. If expired, automatically refreshes it using the refresh token.
    Returns the valid access token, or raises UserError if connection is missing.
    """
    params = env['ir.config_parameter'].sudo()
    
    sync_enabled = params.get_param('meeting_room_booking.google_sync_enabled')
    if not sync_enabled:
        return False
        
    access_token = params.get_param('meeting_room_booking.google_access_token')
    refresh_token = params.get_param('meeting_room_booking.google_refresh_token')
    expiry_str = params.get_param('meeting_room_booking.google_token_expiry')

    if not refresh_token:
        raise UserError(_("Google Account is not connected. Please connect it in settings first."))

    # Check if expired (with a 60 second buffer)
    is_expired = True
    if expiry_str:
        try:
            expiry_time = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
            if datetime.now() < (expiry_time - timedelta(seconds=60)):
                is_expired = False
        except Exception:
            _logger.warning("Error parsing Google token expiry timestamp, assuming expired.")

    if is_expired:
        # Refresh the token
        client_id = params.get_param('meeting_room_booking.google_client_id')
        client_secret = params.get_param('meeting_room_booking.google_client_secret')
        
        if not client_id or not client_secret:
            raise UserError(_("Google Calendar Client credentials are not configured."))

        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        try:
            _logger.info("Refreshing expired Google Calendar access token...")
            response = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            new_access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)
            new_expiry = datetime.now() + timedelta(seconds=int(expires_in))
            
            params.set_param('meeting_room_booking.google_access_token', new_access_token)
            params.set_param('meeting_room_booking.google_token_expiry', new_expiry.strftime('%Y-%m-%d %H:%M:%S'))
            
            _logger.info("Google Calendar access token successfully refreshed.")
            return new_access_token
        except Exception as e:
            _logger.error(f"Failed to refresh Google Calendar OAuth token: {str(e)}")
            raise UserError(_("Could not refresh Google OAuth connection. Please reconnect Google Calendar in Settings. Error: %s") % str(e))
            
    return access_token

def prepare_google_event_data(booking):
    """
    Constructs the JSON request payload for Google Calendar API.
    """
    # Clean description / agenda text
    agenda = booking.description or "No agenda provided."
    # Strip HTML tags if present (since Odoo's html widget might add them)
    try:
        from odoo.tools import html2plaintext
        agenda = html2plaintext(agenda)
    except Exception:
        pass
        
    description = (
        f"{agenda}\n\n"
        f"--- Meeting Details ---\n"
        f"Meeting Room: {booking.room_id.name}\n"
        f"Organizer: {booking.organizer_id.name}\n"
        f"Status: Confirmed\n"
    )

    # Format Datetimes (convert to ISO format strings)
    # Booking times are stored in UTC in the DB. Send UTC directly with Z suffix.
    start_iso = booking.start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_iso = booking.end_time.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Compile participants emails
    attendees = []
    for p in booking.participant_ids:
        if p.work_email:
            attendees.append({'email': p.work_email, 'displayName': p.name})

    event_data = {
        'summary': booking.purpose or f"Booking {booking.name}",
        'description': description,
        'location': booking.room_id.name,
        'start': {
            'dateTime': start_iso,
            'timeZone': 'UTC'
        },
        'end': {
            'dateTime': end_iso,
            'timeZone': 'UTC'
        },
        'attendees': attendees,
        'conferenceData': {
            'createRequest': {
                'requestId': f"booking_{booking.id}_{datetime.now().strftime('%M%S')}",
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                }
            }
        }
    }
    return event_data

def create_google_event(env, booking):
    """
    Creates a new Google Calendar Event. Returns (event_id, meet_url)
    """
    token = get_google_access_token(env)
    if not token:
        return False, False
        
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    event_payload = prepare_google_event_data(booking)
    
    # Request HangoutsMeet generation by setting conferenceDataVersion=1
    url = f"{GOOGLE_CALENDAR_EVENTS_URL}?conferenceDataVersion=1"
    
    _logger.info(f"Creating Google Calendar event for booking {booking.name}")
    response = requests.post(url, json=event_payload, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    event_id = data.get('id')
    
    # Extract meet URL
    meet_url = False
    conf_data = data.get('conferenceData', {})
    entry_points = conf_data.get('entryPoints', [])
    for entry in entry_points:
        if entry.get('entryPointType') == 'video':
            meet_url = entry.get('uri')
            break
            
    return event_id, meet_url

def update_google_event(env, booking, google_event_id):
    """
    Updates an existing Google Calendar Event.
    """
    token = get_google_access_token(env)
    if not token:
        return False
        
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    event_payload = prepare_google_event_data(booking)
    
    url = f"{GOOGLE_CALENDAR_EVENTS_URL}/{google_event_id}?conferenceDataVersion=1"
    
    _logger.info(f"Updating Google Calendar event {google_event_id} for booking {booking.name}")
    response = requests.put(url, json=event_payload, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    # Extract updated meet URL if available
    meet_url = False
    conf_data = data.get('conferenceData', {})
    entry_points = conf_data.get('entryPoints', [])
    for entry in entry_points:
        if entry.get('entryPointType') == 'video':
            meet_url = entry.get('uri')
            break
            
    return meet_url

def delete_google_event(env, google_event_id):
    """
    Deletes a Google Calendar Event.
    """
    token = get_google_access_token(env)
    if not token:
        return False
        
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    url = f"{GOOGLE_CALENDAR_EVENTS_URL}/{google_event_id}"
    
    _logger.info(f"Deleting Google Calendar event {google_event_id}")
    try:
        response = requests.delete(url, headers=headers, timeout=15)
        # 410 Gone means the event is already deleted, which is a success for us
        if response.status_code not in (204, 410):
            response.raise_for_status()
        return True
    except Exception as e:
        _logger.warning(f"Failed to delete Google Calendar event: {str(e)}")
        # Raise here to let caller log the failure details
        raise e
