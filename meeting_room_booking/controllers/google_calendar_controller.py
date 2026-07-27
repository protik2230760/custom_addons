# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests
from datetime import datetime, timedelta
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class GoogleCalendarController(http.Controller):

    @http.route('/google_calendar/authentication', type='http', auth='user', website=False, csrf=False)
    def oauth2callback(self, **kw):
        code = kw.get('code')
        error = kw.get('error')
        if error:
            return f"<h3>Authentication Failed</h3><p>Google returned error: {error}</p>"
        if not code:
            return "<h3>Authentication Failed</h3><p>No authorization code received.</p>"

        # Retrieve Client ID and Secret
        params = request.env['ir.config_parameter'].sudo()
        client_id = params.get_param('meeting_room_booking.google_client_id')
        client_secret = params.get_param('meeting_room_booking.google_client_secret')
        redirect_uri = params.get_param('meeting_room_booking.google_redirect_uri')

        if not client_id or not client_secret:
            return "<h3>Authentication Failed</h3><p>Google Credentials are not configured in Odoo Settings.</p>"

        # Exchange authorization code for access and refresh tokens
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }

        try:
            response = requests.post(token_url, data=payload, timeout=15)
            response.raise_for_status()
            token_data = response.json()
            
            # Save tokens
            access_token = token_data.get('access_token')
            refresh_token = token_data.get('refresh_token') # offline access_type gets this
            expires_in = token_data.get('expires_in', 3600)
            
            expiry_time = datetime.now() + timedelta(seconds=int(expires_in))
            
            params.set_param('meeting_room_booking.google_access_token', access_token)
            if refresh_token:
                params.set_param('meeting_room_booking.google_refresh_token', refresh_token)
            params.set_param('meeting_room_booking.google_token_expiry', expiry_time.strftime('%Y-%m-%d %H:%M:%S'))
            
            _logger.info("Google Calendar OAuth connection successful.")
            
            return """
            <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 50px;">
                    <div style="display: inline-block; padding: 30px; border: 1px solid #22c55e; border-radius: 8px; background-color: #f0fdf4;">
                        <h2 style="color: #15803d; margin-top: 0;">Connection Successful!</h2>
                        <p style="color: #166534;">Your Google Calendar account is successfully connected to Odoo.</p>
                        <p style="color: #4b5563; font-size: 14px;">You can now close this tab and refresh the Odoo Settings page.</p>
                        <button onclick="window.close()" style="background-color: #15803d; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold; margin-top: 15px;">Close Window</button>
                    </div>
                </body>
            </html>
            """
        except Exception as e:
            _logger.exception("Error during Google OAuth code exchange")
            return f"<h3>Authentication Failed</h3><p>An error occurred during token exchange: {str(e)}</p>"
