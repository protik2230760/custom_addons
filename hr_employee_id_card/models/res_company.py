# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    authorized_signature = fields.Binary(string='Authorized Signature', attachment=True)
    company_emergency_contact = fields.Char(string='Emergency Contact Number')
    company_fax = fields.Char(string='Fax')
