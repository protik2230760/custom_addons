# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    blood_group = fields.Selection([
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-')
    ], string='Blood Group')

    employee_signature = fields.Binary(string='Employee Signature', attachment=True)
