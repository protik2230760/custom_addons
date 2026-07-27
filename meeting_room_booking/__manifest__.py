{
    'name': 'Meeting Room Booking',
    'version': '1.0',
    'category': 'Extra Tools',
    'summary': 'Simple booking system for meeting rooms.',
    'depends': ['mail', 'hr'],
    'data': [
        'security/meeting_room_booking_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/meeting_room_booking_views.xml',
        'views/meeting_room_views.xml',
        'views/res_config_settings_views.xml',
        'views/kiosk_templates.xml',
        'views/meeting_room_booking_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'meeting_room_booking/static/src/css/meeting_room_booking_calendar.css',
            'meeting_room_booking/static/src/js/meeting_room_booking_calendar.js',
            'meeting_room_booking/static/src/xml/meeting_room_booking_calendar.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}