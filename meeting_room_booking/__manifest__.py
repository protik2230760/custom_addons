{
    'name': 'Meeting Room Booking',
    'version': '1.0',
    'category': 'Extra Tools',
    'summary': 'Simple booking system for meeting rooms.',
    'depends': ['mail'],
    'data': [
        'security/meeting_room_booking_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/meeting_room_booking_views.xml',
        'views/meeting_room_views.xml',
        'views/meeting_room_booking_menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}