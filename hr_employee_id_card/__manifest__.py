# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Custom Employee ID Card',
    'version': '1.0',
    'category': 'Human Resources/Employees',
    'summary': 'Generate PVC-sized employee ID cards (Front and Back)',
    'description': """
Custom Employee ID Card PDF Generation
=======================================
* Adds blood group and employee signature fields to employees.
* Adds company authorized signature, emergency contact, and fax settings.
* Generates a PVC-sized (CR80) Portrait ID card with QR code and Barcode side-by-side.
    """,
    'depends': ['hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'report/ir_actions_report.xml',
        'report/employee_id_card_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
