# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    authorized_signature = fields.Binary(
        related='company_id.authorized_signature',
        readonly=False,
        string='Authorized Signature'
    )
    company_emergency_contact = fields.Char(
        related='company_id.company_emergency_contact',
        readonly=False,
        string='Emergency Contact Number'
    )
    company_fax = fields.Char(
        related='company_id.company_fax',
        readonly=False,
        string='Fax'
    )
