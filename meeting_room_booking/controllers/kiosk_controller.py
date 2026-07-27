# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class KioskController(http.Controller):

    @http.route('/meeting_room_booking/kiosk', type='http', auth='user', website=False)
    def kiosk_index(self, **kw):
        return request.render('meeting_room_booking.kiosk_mode_dashboard')

    @http.route('/meeting_room_booking/kiosk/data', type='json', auth='user')
    def kiosk_data(self, **kw):
        now = fields.Datetime.now()
        today = fields.Date.context_today(request.env['meeting.room.booking'])
        
        rooms = request.env['meeting.room'].sudo().search([('active', '=', True)])
        bookings = request.env['meeting.room.booking'].sudo().search([
            ('booking_date', '=', today),
            ('status', '=', 'confirmed')
        ])
        
        # Build rooms status mapping
        room_data = []
        occupied_count = 0
        available_count = 0
        
        # User timezone for displaying times nicely on the frontend
        user_tz = request.env.user.tz or 'UTC'
        import pytz
        tz = pytz.timezone(user_tz)
        
        def format_time_local(dt):
            if not dt:
                return ""
            # dt is naive UTC datetime from Odoo DB
            utc_dt = pytz.utc.localize(dt)
            local_dt = utc_dt.astimezone(tz)
            return local_dt.strftime('%I:%M %p')

        for room in rooms:
            room_bookings = bookings.filtered(lambda b: b.room_id.id == room.id)
            
            # Check if there is an ongoing meeting
            current_booking = room_bookings.filtered(lambda b: b.start_time <= now <= b.end_time)
            
            status = 'available'
            current_meeting_info = {}
            next_meeting_info = {}
            
            if current_booking:
                current_booking = current_booking[0]
                status = 'occupied'
                occupied_count += 1
                current_meeting_info = {
                    'purpose': current_booking.purpose,
                    'organizer': current_booking.organizer_id.name,
                    'end_time': format_time_local(current_booking.end_time)
                }
            else:
                available_count += 1
                # Find the next upcoming meeting today for this room
                upcoming_room_bookings = room_bookings.filtered(lambda b: b.start_time > now).sorted('start_time')
                if upcoming_room_bookings:
                    next_b = upcoming_room_bookings[0]
                    next_meeting_info = {
                        'purpose': next_b.purpose,
                        'organizer': next_b.organizer_id.name,
                        'start_time': format_time_local(next_b.start_time)
                    }

            # Gather room amenities
            amenities = [a.name for a in room.amenity_ids]

            room_data.append({
                'id': room.id,
                'name': room.name,
                'capacity': room.capacity,
                'floor': room.floor or '',
                'building': room.building or '',
                'amenities': amenities,
                'status': status,
                'current_meeting': current_meeting_info,
                'next_meeting': next_meeting_info
            })
            
        # Get all upcoming meetings today across all rooms
        upcoming_bookings = bookings.filtered(lambda b: b.start_time > now).sorted('start_time')
        upcoming_meetings_data = []
        for b in upcoming_bookings:
            upcoming_meetings_data.append({
                'id': b.id,
                'room_name': b.room_id.name,
                'purpose': b.purpose,
                'organizer': b.organizer_id.name,
                'start_time': format_time_local(b.start_time),
                'end_time': format_time_local(b.end_time)
            })
            
        return {
            'rooms': room_data,
            'upcoming_meetings': upcoming_meetings_data,
            'summary': {
                'total': len(rooms),
                'occupied': occupied_count,
                'available': available_count
            }
        }
