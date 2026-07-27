# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

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
