# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestMeetingRoomBooking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create a work location
        cls.work_location = cls.env['hr.work.location'].create({
            'name': 'HQ Office Room A',
            'location_type': 'office',
            'address_id': cls.env.company.partner_id.id,
        })
        
        # Create a meeting room linked to this work location
        cls.room = cls.env['meeting.room'].create({
            'name': 'Conference Room A',
            'capacity': 10,
            'location': 'HQ Office Room A',
            'work_location_id': cls.work_location.id,
        })
        
        # Create users/employees for organizer and participants
        cls.user_organizer = cls.env['res.users'].create({
            'name': 'Organizer User',
            'login': 'organizer_user_login',
            'email': 'org@example.com',
        })
        cls.employee_organizer = cls.env['hr.employee'].create({
            'name': 'Organizer Employee',
            'user_id': cls.user_organizer.id,
        })
        
        cls.employee_participant = cls.env['hr.employee'].create({
            'name': 'Participant Employee',
            'work_email': 'part@example.com',
        })

    def test_01_booking_overlap_prevention(self):
        """ Test that overlapping draft/confirmed bookings are blocked. """
        start_time = datetime.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        
        # Create first draft booking
        booking1 = self.env['meeting.room.booking'].create({
            'room_id': self.room.id,
            'purpose': 'Project Planning',
            'start_time': start_time,
            'end_time': end_time,
            'organizer_id': self.user_organizer.id,
        })
        self.assertTrue(booking1)
        
        # Attempting to create an overlapping booking should raise ValidationError
        with self.assertRaises(ValidationError):
            self.env['meeting.room.booking'].create({
                'room_id': self.room.id,
                'purpose': 'Project Review (Overlapping)',
                'start_time': start_time + timedelta(minutes=30),
                'end_time': end_time + timedelta(minutes=30),
                'organizer_id': self.user_organizer.id,
            })

    def test_02_work_location_assignment(self):
        """ Test that confirming a booking updates the work location of organizer and participants. """
        start_time = datetime.now() + timedelta(days=2)
        end_time = start_time + timedelta(hours=1)
        
        # Create a booking with participant
        booking = self.env['meeting.room.booking'].create({
            'room_id': self.room.id,
            'purpose': 'Design Sync',
            'start_time': start_time,
            'end_time': end_time,
            'organizer_id': self.user_organizer.id,
            'participant_ids': [(6, 0, [self.employee_participant.id])],
        })
        
        # Check initial work locations are not set to this room's work location
        self.assertNotEqual(self.employee_organizer.work_location_id.id, self.work_location.id)
        self.assertNotEqual(self.employee_participant.work_location_id.id, self.work_location.id)
        
        # Confirm booking as manager (using sudo to ensure we have rights)
        booking.sudo().action_confirm()
        
        # Check work locations are automatically assigned
        self.assertEqual(self.employee_organizer.work_location_id.id, self.work_location.id)
        self.assertEqual(self.employee_participant.work_location_id.id, self.work_location.id)
