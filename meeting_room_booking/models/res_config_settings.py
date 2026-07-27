from odoo import fields, models, _
from odoo.exceptions import UserError
from urllib.parse import urlencode

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_meeting_room_booking_email_notifications = fields.Boolean(
        string="Enable Meeting Email Notifications",
        config_parameter="meeting_room_booking.email_notifications",
        default=True
    )
    meeting_room_booking_reminder_time = fields.Selection([
        ('15', '15 Minutes Before'),
        ('30', '30 Minutes Before'),
        ('60', '1 Hour Before'),
        ('1440', '1 Day Before'),
    ], string="Meeting Reminder Time", config_parameter="meeting_room_booking.reminder_time", default='15')

    module_meeting_room_booking_google_sync = fields.Boolean(
        string="Enable Google Calendar Sync",
        config_parameter="meeting_room_booking.google_sync_enabled",
        default=False
    )
    google_client_id = fields.Char(
        string="Google Client ID",
        config_parameter="meeting_room_booking.google_client_id"
    )
    google_client_secret = fields.Char(
        string="Google Client Secret",
        config_parameter="meeting_room_booking.google_client_secret"
    )
    google_redirect_uri = fields.Char(
        string="Redirect URI",
        compute="_compute_google_redirect_uri"
    )
    google_connection_status = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Not Connected')
    ], string="Connection Status", compute="_compute_google_connection_status")

    def _compute_google_redirect_uri(self):
        for rec in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
            rec.google_redirect_uri = f"{base_url.rstrip('/')}/google_calendar/authentication"

    def _compute_google_connection_status(self):
        for rec in self:
            refresh_token = self.env['ir.config_parameter'].sudo().get_param('meeting_room_booking.google_refresh_token')
            rec.google_connection_status = 'connected' if refresh_token else 'disconnected'

    def action_connect_google_calendar(self):
        self.ensure_one()
        self.env['ir.config_parameter'].sudo().set_param('meeting_room_booking.google_client_id', self.google_client_id)
        self.env['ir.config_parameter'].sudo().set_param('meeting_room_booking.google_client_secret', self.google_client_secret)
        
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
        redirect_uri = f"{base_url.rstrip('/')}/google_calendar/authentication"
        self.env['ir.config_parameter'].sudo().set_param('meeting_room_booking.google_redirect_uri', redirect_uri)
        
        if not self.google_client_id or not self.google_client_secret:
            raise UserError(_("Please configure Client ID and Client Secret first."))
            
        params = {
            'client_id': self.google_client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/calendar',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': self.env.user.id,
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }

    def action_disconnect_google_calendar(self):
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('meeting_room_booking.google_access_token', False)
        params.set_param('meeting_room_booking.google_refresh_token', False)
        params.set_param('meeting_room_booking.google_token_expiry', False)
        return True

