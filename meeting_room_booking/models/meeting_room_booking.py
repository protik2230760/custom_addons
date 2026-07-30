import logging
from datetime import timedelta
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, AccessError, UserError

_logger = logging.getLogger(__name__)

class MeetingRoomBooking(models.Model):
    _name = 'meeting.room.booking'
    _description = 'Meeting Room Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc'

    name = fields.Char(
        string='Booking Reference',
        required=False,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    room_id = fields.Many2one(
        'meeting.room',
        string='Meeting Room',
        required=True,
        domain=[('active', '=', True)],
        tracking=True
    )
    room_location = fields.Char(
        string='Room Location',
        related='room_id.location',
        store=True,
        readonly=True
    )
    work_location_id = fields.Many2one(
        'hr.work.location',
        string='Work Location',
        compute='_compute_work_location_id',
        store=True,
        readonly=False,
        tracking=True
    )
    booking_date = fields.Date(
        string='Booking Date',
        compute='_compute_booking_date',
        store=True,
        readonly=True,
        index=True
    )
    start_time = fields.Datetime(
        string='Start Time',
        required=True,
        default=lambda self: fields.Datetime.now(),
        tracking=True
    )
    end_time = fields.Datetime(
        string='End Time',
        required=True,
        default=lambda self: fields.Datetime.now() + timedelta(hours=1),
        tracking=True
    )
    organizer_id = fields.Many2one(
        'res.users',
        string='Organizer',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    purpose = fields.Char(
        string='Purpose',
        required=True,
        tracking=True
    )
    description = fields.Text(
        string='Description'
    )
    status = fields.Selection([
        ('draft', 'Draft / Pending'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', required=True, tracking=True)

    attendees_count = fields.Integer(
        string='Number of Attendees',
        compute='_compute_attendees_count',
        store=True,
        readonly=False,
        default=1,
        tracking=True
    )
    color_index = fields.Integer(
        string='Color Index',
        compute='_compute_color_index',
        store=True
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        compute='_compute_department_id',
        store=True,
        tracking=True
    )
    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
        readonly=True
    )
    ignore_conflicts = fields.Boolean(
        string='Ignore Participant Conflicts',
        default=False,
        tracking=True
    )
    has_participant_conflicts = fields.Boolean(
        string='Has Participant Conflicts',
        compute='_compute_participant_conflicts'
    )
    participant_ids = fields.Many2many(
        'hr.employee',
        'meeting_room_booking_employee_rel',
        'booking_id',
        'employee_id',
        string='Participants'
    )
    google_event_id = fields.Char(
        string='Google Event ID',
        readonly=True,
        copy=False
    )
    google_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('synced', 'Synced'),
        ('pending', 'Pending Sync'),
        ('failed', 'Sync Failed')
    ], string='Google Sync Status', default='not_synced', readonly=True, copy=False)
    google_last_sync = fields.Datetime(
        string='Last Sync Time',
        readonly=True,
        copy=False
    )
    google_meet_url = fields.Char(
        string='Google Meet URL',
        readonly=True,
        copy=False
    )
    google_sync_error = fields.Text(
        string='Last Sync Error Log',
        readonly=True,
        copy=False
    )

    @api.depends('status')
    def _compute_color_index(self):
        for rec in self:
            if rec.status == 'confirmed':
                rec.color_index = 10  # Green
            elif rec.status == 'draft':
                rec.color_index = 3   # Yellow
            elif rec.status == 'done':
                rec.color_index = 8   # Blue
            elif rec.status == 'cancelled':
                rec.color_index = 1   # Red
            else:
                rec.color_index = 0   # Gray

    @api.depends('room_id')
    def _compute_work_location_id(self):
        for rec in self:
            if rec.room_id and rec.room_id.work_location_id:
                rec.work_location_id = rec.room_id.work_location_id.id
            else:
                rec.work_location_id = False

    @api.depends('participant_ids')
    def _compute_attendees_count(self):
        for rec in self:
            rec.attendees_count = len(rec.participant_ids) + 1

    @api.depends('organizer_id')
    def _compute_department_id(self):
        for rec in self:
            if rec.organizer_id:
                employee = self.env['hr.employee'].search([('user_id', '=', rec.organizer_id.id)], limit=1)
                rec.department_id = employee.department_id.id if employee else False
            else:
                rec.department_id = False

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                diff = rec.end_time - rec.start_time
                rec.duration = diff.total_seconds() / 3600.0
            else:
                rec.duration = 0.0

    @api.depends('start_time', 'end_time', 'participant_ids', 'status')
    def _compute_participant_conflicts(self):
        for rec in self:
            if not rec.start_time or not rec.end_time or not rec.participant_ids or rec.status in ('cancelled', 'rejected'):
                rec.has_participant_conflicts = False
                continue
            
            employees = rec.participant_ids
            overlap_bookings = self.search([
                ('status', '=', 'confirmed'),
                ('start_time', '<', rec.end_time),
                ('end_time', '>', rec.start_time),
                ('id', '!=', rec._origin.id if rec._origin else rec.id),
                ('participant_ids', 'in', employees.ids)
            ])
            rec.has_participant_conflicts = bool(overlap_bookings)



    @api.model
    def get_dashboard_summary(self):
        now = fields.Datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        total_meetings_today = self.search_count([
            ('start_time', '<=', today_end),
            ('end_time', '>=', today_start),
            ('status', 'not in', ('cancelled', 'rejected'))
        ])

        active_meetings = self.search_count([
            ('start_time', '<=', now),
            ('end_time', '>=', now),
            ('status', '=', 'confirmed')
        ])

        upcoming_meetings = self.search_count([
            ('start_time', '>', now),
            ('status', '=', 'confirmed')
        ])

        total_rooms = self.env['meeting.room'].search_count([('active', '=', True)])
        
        # Rooms currently occupied by confirmed bookings
        occupied_rooms_ids = self.env['meeting.room.booking'].search([
            ('start_time', '<=', now),
            ('end_time', '>=', now),
            ('status', '=', 'confirmed')
        ]).mapped('room_id').ids
        occupied_rooms = len(set(occupied_rooms_ids))
        available_rooms = max(0, total_rooms - occupied_rooms)

        return {
            'total_meetings_today': total_meetings_today,
            'active_meetings': active_meetings,
            'upcoming_meetings': upcoming_meetings,
            'available_rooms': available_rooms,
            'occupied_rooms': occupied_rooms,
        }

    @api.depends('start_time')
    def _compute_booking_date(self):
        for rec in self:
            if rec.start_time:
                rec.booking_date = rec.start_time.date()
            else:
                rec.booking_date = False

    @api.constrains('room_id', 'start_time', 'end_time', 'status')
    def _check_booking_overlap(self):
        for rec in self:
            if not rec.room_id or not rec.start_time or not rec.end_time:
                continue
            if rec.start_time >= rec.end_time:
                raise ValidationError(_("Start Time must be strictly before End Time."))
            
            # Cancelled and Rejected bookings do not occupy the room
            if rec.status in ('cancelled', 'rejected'):
                continue
                
            domain = [
                ('room_id', '=', rec.room_id.id),
                ('status', 'in', ('draft', 'confirmed', 'done')),
                ('start_time', '<', rec.end_time),
                ('end_time', '>', rec.start_time),
            ]
            
            # Exclude current record
            if rec.id:
                domain.append(('id', '!=', rec.id))
                
            overlap_bookings = self.env['meeting.room.booking'].search(domain)
            if overlap_bookings:
                raise ValidationError(_("This meeting room is already booked during the selected time. Please choose another time slot or room."))

    @api.constrains('room_id', 'attendees_count')
    def _check_room_capacity(self):
        for rec in self:
            if rec.room_id and rec.attendees_count > rec.room_id.capacity:
                raise ValidationError(_(
                    "The number of attendees (%d) exceeds the capacity of the room '%s' (%d)."
                ) % (rec.attendees_count, rec.room_id.name, rec.room_id.capacity))

    @api.onchange('room_id', 'attendees_count')
    def _onchange_room_capacity(self):
        if self.room_id and self.attendees_count > self.room_id.capacity:
            room_name = self.room_id.name
            capacity = self.room_id.capacity
            self.room_id = False
            return {
                'warning': {
                    'title': _("Room Capacity Exceeded"),
                    'message': _("The number of attendees (%d) exceeds the capacity of '%s' (%d). The room selection has been reset.") % (self.attendees_count, room_name, capacity)
                }
            }

    @api.onchange('room_id', 'start_time', 'end_time')
    def _onchange_room_availability(self):
        if self.room_id and self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                return {
                    'warning': {
                        'title': _("Invalid Times"),
                        'message': _("Start time must be before end time.")
                    }
                }
            domain = [
                ('room_id', '=', self.room_id._origin.id if hasattr(self.room_id, '_origin') else self.room_id.id),
                ('status', 'in', ('draft', 'confirmed', 'done')),
                ('start_time', '<', self.end_time),
                ('end_time', '>', self.start_time),
            ]
            if self._origin:
                domain.append(('id', '!=', self._origin.id))
            overlaps = self.env['meeting.room.booking'].search_count(domain)
            if overlaps > 0:
                return {
                    'warning': {
                        'title': _("Room Unavailable"),
                        'message': _("Warning: The room '%s' has other bookings during this time period.") % self.room_id.name
                    }
                }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('meeting.room.booking') or _('New')
        return super().create(vals_list)

    # State Actions
    def action_confirm(self):
        if not self.env.user.has_group('meeting_room_booking.group_meeting_room_manager'):
            raise AccessError(_("Only meeting managers are allowed to confirm bookings."))
        for rec in self:
            if rec.status != 'draft':
                raise UserError(_("Only draft bookings can be confirmed."))
            
            # Check participant conflicts
            if rec.has_participant_conflicts and not rec.ignore_conflicts:
                conflicts = []
                employees = rec.participant_ids
                overlap_bookings = self.search([
                    ('status', '=', 'confirmed'),
                    ('start_time', '<', rec.end_time),
                    ('end_time', '>', rec.start_time),
                    ('id', '!=', rec.id),
                    ('participant_ids', 'in', employees.ids)
                ])
                for b in overlap_bookings:
                    for p in b.participant_ids:
                        if p in employees:
                            conflicts.append("%s is already busy in '%s'" % (p.name, b.purpose or b.name))
                
                raise UserError(_(
                    "Conflict detected: The following participants are already busy in another meeting:\n%s\n\n"
                    "If you want to confirm anyway, please check 'Ignore Participant Conflicts' and click confirm again."
                ) % "\n".join(set(conflicts)))

            rec.status = 'confirmed'
            
            # Automatically assign work location to organizer and participants
            if rec.work_location_id:
                if rec.organizer_id:
                    org_emp = self.env['hr.employee'].search([('user_id', '=', rec.organizer_id.id)], limit=1)
                    if org_emp:
                        org_emp.work_location_id = rec.work_location_id.id
                for participant in rec.participant_ids:
                    participant.work_location_id = rec.work_location_id.id
            
            # Send message to chatter
            rec.message_post(body=_("Booking approved and confirmed."))
            rec._send_notification_email('meeting_room_booking.email_template_meeting_invitation')
            rec.sync_booking_to_google()

    def action_reject(self):
        if not self.env.user.has_group('meeting_room_booking.group_meeting_room_manager'):
            raise AccessError(_("Only meeting managers are allowed to reject bookings."))
        for rec in self:
            if rec.status != 'draft':
                raise UserError(_("Only draft bookings can be rejected."))
            rec.status = 'rejected'
            rec.message_post(body=_("Booking rejected."))

    def action_cancel(self):
        for rec in self:
            # Users can cancel their own draft/confirmed bookings, managers can cancel any.
            is_manager = self.env.user.has_group('meeting_room_booking.group_meeting_room_manager')
            is_organizer = rec.organizer_id == self.env.user or rec.create_uid == self.env.user
            if not (is_manager or is_organizer):
                raise AccessError(_("You are not authorized to cancel this booking."))
            
            if rec.status in ('done', 'cancelled', 'rejected'):
                raise UserError(_("You cannot cancel a booking in status Done, Cancelled, or Rejected."))
            
            rec.status = 'cancelled'
            rec.message_post(body=_("Booking cancelled."))
            rec._send_notification_email('meeting_room_booking.email_template_meeting_cancelled')
            rec.delete_booking_from_google()

    def action_draft(self):
        if not self.env.user.has_group('meeting_room_booking.group_meeting_room_manager'):
            raise AccessError(_("Only meeting managers are allowed to reset bookings to draft."))
        for rec in self:
            if rec.status not in ('cancelled', 'rejected'):
                raise UserError(_("Only cancelled or rejected bookings can be reset to draft."))
            rec.status = 'draft'
            rec.message_post(body=_("Booking reset to Draft / Pending."))

    def action_done(self):
        for rec in self:
            is_manager = self.env.user.has_group('meeting_room_booking.group_meeting_room_manager')
            is_organizer = rec.organizer_id == self.env.user or rec.create_uid == self.env.user
            if not (is_manager or is_organizer):
                raise AccessError(_("You are not authorized to mark this booking as Done."))
            if rec.status != 'confirmed':
                raise UserError(_("Only confirmed bookings can be marked as Done."))
            rec.status = 'done'
            rec.message_post(body=_("Booking marked as Done."))

    def write(self, vals):
        time_changed = False
        sync_trigger_fields = {'start_time', 'end_time', 'room_id', 'participant_ids', 'purpose', 'description'}
        if any(f in vals for f in sync_trigger_fields):
            time_changed = True
            
        res = super().write(vals)
        
        if time_changed:
            for rec in self:
                if rec.status == 'confirmed':
                    rec._send_notification_email('meeting_room_booking.email_template_meeting_rescheduled')
                    rec.sync_booking_to_google()
        return res

    def unlink(self):
        for rec in self:
            if rec.google_event_id:
                try:
                    from ..services.google_calendar_service import delete_google_event
                    delete_google_event(self.env, rec.google_event_id)
                except Exception as e:
                    _logger.warning("Failed to delete Google event on record deletion: %s" % str(e))
        return super().unlink()

    def _send_notification_email(self, template_xml_id):
        enabled = self.env['ir.config_parameter'].sudo().get_param('meeting_room_booking.email_notifications', 'False')
        if enabled != 'True':
            return
            
        template = self.env.ref(template_xml_id, raise_if_not_found=False)
        if not template:
            return
            
        for rec in self:
            emails = []
            if rec.organizer_id and rec.organizer_id.email:
                emails.append(rec.organizer_id.email)
            for p in rec.participant_ids:
                if p.work_email:
                    emails.append(p.work_email)
            
            emails = list(set(emails))
            if not emails:
                continue
                
            email_values = {
                'email_to': ",".join(emails),
            }
            template.send_mail(rec.id, force_send=True, email_values=email_values)

    @api.model
    def _cron_refresh_google_token(self):
        try:
            from ..services.google_calendar_service import get_google_access_token
            get_google_access_token(self.env)
        except Exception as e:
            _logger.warning("Failed to refresh Google token in cron: %s" % str(e))

    @api.model
    def _cron_retry_failed_sync(self):
        failed_bookings = self.search([
            ('status', '=', 'confirmed'),
            ('google_sync_status', 'in', ('failed', 'pending'))
        ])
        if failed_bookings:
            failed_bookings.sync_booking_to_google()

    def sync_booking_to_google(self):
        """
        Syncs booking details to Google Calendar. Safe to run from actions or cron.
        """
        params = self.env['ir.config_parameter'].sudo()
        sync_enabled = params.get_param('meeting_room_booking.google_sync_enabled') == 'True'
        if not sync_enabled:
            return
            
        for rec in self:
            if rec.status != 'confirmed':
                continue
                
            try:
                if rec.google_event_id:
                    from ..services.google_calendar_service import update_google_event
                    meet_url = update_google_event(self.env, rec, rec.google_event_id)
                    if meet_url:
                        super(MeetingRoomBooking, rec).write({'google_meet_url': meet_url})
                else:
                    from ..services.google_calendar_service import create_google_event
                    event_id, meet_url = create_google_event(self.env, rec)
                    if event_id:
                        super(MeetingRoomBooking, rec).write({
                            'google_event_id': event_id,
                            'google_meet_url': meet_url
                        })
                
                super(MeetingRoomBooking, rec).write({
                    'google_sync_status': 'synced',
                    'google_last_sync': fields.Datetime.now(),
                    'google_sync_error': False
                })
                rec.message_post(body=_("Google Calendar synchronization successful."))
            except Exception as e:
                status = 'failed'
                if "Google Account is not connected" in str(e):
                    status = 'pending'
                super(MeetingRoomBooking, rec).write({
                    'google_sync_status': status,
                    'google_sync_error': str(e)
                })
                rec.message_post(body=_("Google Calendar synchronization failed. Error: %s") % str(e))

    def delete_booking_from_google(self):
        """
        Removes booking event from Google Calendar.
        """
        params = self.env['ir.config_parameter'].sudo()
        sync_enabled = params.get_param('meeting_room_booking.google_sync_enabled') == 'True'
        if not sync_enabled:
            return
            
        for rec in self:
            if rec.google_event_id:
                try:
                    from ..services.google_calendar_service import delete_google_event
                    delete_google_event(self.env, rec.google_event_id)
                    super(MeetingRoomBooking, rec).write({
                        'google_sync_status': 'not_synced',
                        'google_meet_url': False,
                        'google_event_id': False,
                        'google_sync_error': False
                    })
                except Exception as e:
                    super(MeetingRoomBooking, rec).write({
                        'google_sync_status': 'failed',
                        'google_sync_error': str(e)
                    })
                    rec.message_post(body=_("Failed to delete Google Calendar event: %s") % str(e))
