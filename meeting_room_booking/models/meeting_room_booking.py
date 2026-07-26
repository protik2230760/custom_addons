# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, AccessError, UserError

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
        default=1,
        tracking=True
    )

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
                # Convert times to user's timezone for clear display
                overlap_details = []
                for b in overlap_bookings:
                    b_start = fields.Datetime.context_timestamp(self, b.start_time)
                    b_end = fields.Datetime.context_timestamp(self, b.end_time)
                    overlap_details.append(
                        f"{b.name} ({b_start.strftime('%Y-%m-%d %H:%M')} - {b_end.strftime('%H:%M')})"
                    )
                raise ValidationError(_(
                    "The room '%s' is already booked or pending approval during this time slot.\n"
                    "Overlapping Bookings: %s"
                ) % (rec.room_id.name, ", ".join(overlap_details)))

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
            rec.status = 'confirmed'
            # Send message to chatter
            rec.message_post(body=_("Booking approved and confirmed."))

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
