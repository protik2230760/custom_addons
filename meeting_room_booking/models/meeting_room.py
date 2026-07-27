from odoo import models, fields, api, _

class MeetingRoomAmenity(models.Model):
    _name = 'meeting.room.amenity'
    _description = 'Meeting Room Amenity'
    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', 'Amenity name must be unique!')
    ]

    name = fields.Char(string='Name', required=True)
    color = fields.Integer(string='Color')

class MeetingRoom(models.Model):
    _name = 'meeting.room'
    _description = 'Meeting Room'
    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', 'Meeting Room name must be unique!'),
        ('capacity_positive', 'CHECK (capacity > 0)', 'The capacity must be greater than zero!')
    ]

    name = fields.Char(string='Room Name', required=True)
    capacity = fields.Integer(string='Capacity', required=True)
    location = fields.Char(string='Location')
    floor = fields.Char(string='Floor')
    building = fields.Char(string='Building')
    status = fields.Selection([
        ('available', 'Available'),
        ('maintenance', 'Under Maintenance'),
        ('out_of_service', 'Out of Service')
    ], string='Status', default='available', required=True)
    amenity_ids = fields.Many2many('meeting.room.amenity', string='Amenities')
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')
    booking_ids = fields.One2many('meeting.room.booking', 'room_id', string='Bookings')
    booking_count = fields.Integer(string='Booking Count', compute='_compute_booking_count')

    @api.depends('booking_ids.status')
    def _compute_booking_count(self):
        for rec in self:
            rec.booking_count = len(rec.booking_ids.filtered(lambda b: b.status not in ('cancelled', 'rejected')))

    def action_view_bookings(self):
        self.ensure_one()
        return {
            'name': _('Bookings for %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'meeting.room.booking',
            'view_mode': 'calendar,tree,form,kanban',
            'domain': [('room_id', '=', self.id)],
            'context': {'default_room_id': self.id},
        }
