# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class KioskController(http.Controller):

    @http.route('/meeting_room_booking/kiosk', type='http', auth='user', website=False)
    def kiosk_index(self, **kw):
        # Render the room selection page by default
        rooms = request.env['meeting.room'].sudo().search([('active', '=', True)])
        return request.render('meeting_room_booking.kiosk_room_select', {'rooms': rooms})

    @http.route('/meeting_room_booking/kiosk/room/<int:room_id>', type='http', auth='user', website=False)
    def kiosk_room(self, room_id, **kw):
        room = request.env['meeting.room'].sudo().browse(room_id)
        if not room.exists() or not room.active:
            return request.not_found()
        return request.render('meeting_room_booking.kiosk_single_room', {'room': room})

    @http.route('/meeting_room_booking/kiosk/data', type='json', auth='user')
    def kiosk_data(self, **kw):
        room_id = kw.get('room_id')
        now = fields.Datetime.now()
        today = fields.Date.context_today(request.env['meeting.room.booking'])

        # User timezone for displaying times nicely on the frontend
        user_tz = request.env.user.tz or 'UTC'
        import pytz
        tz = pytz.timezone(user_tz)
        
        def format_time_local(dt):
            if not dt:
                return ""
            utc_dt = pytz.utc.localize(dt)
            local_dt = utc_dt.astimezone(tz)
            return local_dt.strftime('%I:%M %p')

        # Scenario 1: Individual Room Data Request
        if room_id:
            room = request.env['meeting.room'].sudo().browse(int(room_id))
            if not room.exists():
                return {'error': 'Room not found'}

            bookings = request.env['meeting.room.booking'].sudo().search([
                ('room_id', '=', room.id),
                ('booking_date', '=', today),
                ('status', '=', 'confirmed')
            ])

            # Current Active Meeting
            current_booking = bookings.filtered(lambda b: b.start_time <= now <= b.end_time)
            status = 'available'
            current_meeting_info = {}
            if current_booking:
                current_booking = current_booking[0]
                status = 'occupied'
                current_meeting_info = {
                    'purpose': current_booking.purpose,
                    'organizer': current_booking.organizer_id.name,
                    'start_time': format_time_local(current_booking.start_time),
                    'end_time': format_time_local(current_booking.end_time),
                }

            # Dynamic Timeline Generation from 9:00 AM to 6:00 PM local time
            local_now = datetime.now(tz)
            local_start = tz.localize(datetime(local_now.year, local_now.month, local_now.day, 9, 0, 0))
            local_end = tz.localize(datetime(local_now.year, local_now.month, local_now.day, 18, 0, 0))
            
            utc_start = local_start.astimezone(pytz.utc).replace(tzinfo=None)
            utc_end = local_end.astimezone(pytz.utc).replace(tzinfo=None)
            
            room_bookings = bookings.sorted('start_time')
            timeline_slots = []
            current_marker = utc_start
            
            for b in room_bookings:
                if b.start_time > current_marker:
                    timeline_slots.append({
                        'type': 'free',
                        'title': 'Available',
                        'start_time': format_time_local(current_marker),
                        'end_time': format_time_local(b.start_time),
                        'organizer': ''
                    })
                
                timeline_slots.append({
                    'type': 'booked',
                    'title': b.purpose,
                    'start_time': format_time_local(b.start_time),
                    'end_time': format_time_local(b.end_time),
                    'organizer': b.organizer_id.name
                })
                
                current_marker = max(current_marker, b.end_time)
                
            if current_marker < utc_end:
                timeline_slots.append({
                    'type': 'free',
                    'title': 'Available',
                    'start_time': format_time_local(current_marker),
                    'end_time': format_time_local(utc_end),
                    'organizer': ''
                })

            amenities = [a.name for a in room.amenity_ids]
            
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
            action = request.env.ref('meeting_room_booking.action_meeting_room_booking')
            booking_link = f"{base_url.rstrip('/')}/web#model=meeting.room.booking&action={action.id}"
            
            return {
                'room_id': room.id,
                'name': room.name,
                'capacity': room.capacity,
                'floor': room.floor or '',
                'building': room.building or '',
                'amenities': amenities,
                'status': status,
                'current_meeting': current_meeting_info,
                'timeline_slots': timeline_slots,
                'booking_link': booking_link
            }

        # Scenario 2: General Rooms Dashboard Data (Backup/Legacy support)
        rooms = request.env['meeting.room'].sudo().search([('active', '=', True)])
        bookings = request.env['meeting.room.booking'].sudo().search([
            ('booking_date', '=', today),
            ('status', '=', 'confirmed')
        ])
        
        room_data = []
        occupied_count = 0
        available_count = 0
        
        for room in rooms:
            room_bookings = bookings.filtered(lambda b: b.room_id.id == room.id)
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
                upcoming_room_bookings = room_bookings.filtered(lambda b: b.start_time > now).sorted('start_time')
                if upcoming_room_bookings:
                    next_b = upcoming_room_bookings[0]
                    next_meeting_info = {
                        'purpose': next_b.purpose,
                        'organizer': next_b.organizer_id.name,
                        'start_time': format_time_local(next_b.start_time)
                    }

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
