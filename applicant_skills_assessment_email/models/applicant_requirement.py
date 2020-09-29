# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import re

# for validating an Email
EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")


class RequirementDetail(models.Model):
    _name = 'requirement.detail'
    _description = 'Requirements used for PDF file'

    @api.model
    def _get_default_parent(self):
        return self.env['applicant.requirement'].search(
            [('id', '=', self.env.context.get('default_requirement_id'))]).id or False

    text = fields.Text(required=True, copy=True)
    sequence = fields.Integer('Sequence')
    parent_id = fields.Many2one(comodel_name="applicant.requirement", string="Assigned to", copy=False,
                                default=_get_default_parent, invisible=True, readonly=True)


class ApplicantRequirement(models.Model):
    _name = 'applicant.requirement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'
    _description = 'Applicant Requirements to pass test case'

    name = fields.Char(required=True, copy=True, tracking=True)
    user_id = fields.Many2one('res.users', 'Me', readonly=True, required=True, default=lambda self: self.env.user)
    active = fields.Boolean(default=True, copy=False, tracking=True,
                            help="Set active to false to hide the requirement without removing it.")
    target_applied_job_id = fields.Many2one(comodel_name="hr.job", tracking=True, copy=True, required=True,
                                            string="Target applied job")
    categ_ids = fields.Many2many('hr.applicant.category', copy=False, tracking=True, string="Applicant category")
    stage_ids = fields.Many2many('hr.recruitment.stage', string="Stage", tracking=True, copy=False, required=True,
                                 domain="['|', ('job_ids', '=', False), ('job_ids', '=', target_applied_job_id)]")
    applicant_found_count = fields.Integer(string="Number of applicants", compute='_compute_applicants', tracking=True)
    applicant_no_email_count = fields.Integer(string="Number of applicants without email or wrong email address",
                                              compute='_compute_applicants', tracking=True)
    requirement_state = fields.Selection([
        ('normal', 'Standby'),
        ('done', 'Sent')], string='Requirements state', tracking=True,
        copy=False, default='normal', readonly=True, required=True)
    title = fields.Char(string="Main title", copy=False, tracking=True)
    view_title = fields.Boolean(string="View title on PDF", default=True, copy=False, tracking=True)
    subtitle = fields.Char(string="Subtitle", copy=False, tracking=True)
    view_subtitle = fields.Boolean(string="View subtitle on PDF", default=True, copy=False, tracking=True)
    document_ids = fields.One2many('ir.attachment', compute='_compute_document_ids', string="Documents")
    document_count = fields.Integer(compute='_compute_document_ids', string="Document Count")
    mail_ids = fields.One2many('mail.mail', compute='_compute_mail_ids', string="Mails")
    mail_count = fields.Integer(compute='_compute_mail_ids', string="Mail Count")
    applicant_ids = fields.Many2many('hr.applicant', copy=False, string="Applicants", compute='_compute_applicants')
    state = fields.Selection([('draft', 'New'), ('confirmed', 'Ready to send'), ('sent', 'Mail sent')],
                             string='Status', copy=False, default='draft', tracking=True)
    requirement_detail_ids = fields.One2many('requirement.detail', 'parent_id', string="List of requirements")

    @api.depends('target_applied_job_id', 'categ_ids', 'stage_ids')
    def _compute_applicants(self):
        for requirement in self:
            if requirement.categ_ids.ids:
                domain = ['&', ('job_id', '=', requirement.target_applied_job_id.id),
                          '&', ('stage_id', 'in', requirement.stage_ids.ids),
                          ('categ_ids', 'in', requirement.categ_ids.ids)]
            else:
                domain = ['&', ('job_id', '=', requirement.target_applied_job_id.id),
                          ('stage_id', 'in', requirement.stage_ids.ids)]
            applicants = self.env['hr.applicant'].search(domain)
            requirement.applicant_ids = applicants
            requirement.applicant_found_count = len(applicants)
            requirement.applicant_no_email_count = len(
                applicants.filtered(lambda l: not l.email_from or not EMAIL_REGEX.match(l.email_from)))

    def _compute_document_ids(self):
        attachments = self.env['ir.attachment'].search([
            '&', ('res_model', '=', 'applicant.requirement'), ('res_id', 'in', self.ids)])
        result = dict.fromkeys(self.ids, self.env['ir.attachment'])
        for attachment in attachments:
            result[attachment.res_id] |= attachment
        for requirement in self:
            requirement.document_ids = result[requirement.id]
            requirement.document_count = len(requirement.document_ids)

    def _compute_mail_ids(self):
        mails = self.env['mail.mail'].search([
            '&', ('model', '=', 'applicant.requirement'), ('res_id', 'in', self.ids)])
        result = dict.fromkeys(self.ids, self.env['mail.mail'])
        for mail in mails:
            result[mail.res_id] |= mail
        for requirement in self:
            requirement.mail_ids = result[requirement.id]
            requirement.mail_count = len(requirement.mail_ids)

    def action_get_attachment_tree_view(self):
        action = self.env.ref('base.action_attachment').read()[0]
        action['context'] = {
            'default_res_model': self._name,
            'default_res_id': self.ids[0]
        }
        action['domain'] = ['&', ('res_model', '=', 'applicant.requirement'), ('res_id', 'in', self.ids)]
        return action

    def action_get_mail_tree_view(self):
        action = self.env.ref('mail.action_view_mail_mail').read()[0]
        action['context'] = {
            'default_model': self._name,
            'default_res_id': self.ids[0]
        }
        action['domain'] = ['&', ('model', '=', 'applicant.requirement'), ('res_id', 'in', self.ids)]
        return action

    def action_regenerate_pdf(self):
        self.env['ir.attachment'].search(
            ['&', ('res_model', '=', 'applicant.requirement'), '&', ('res_id', 'in', self.ids),
             ('name', '=', 'Applicant Requirements.pdf')]).unlink()
        self.action_do_pdf()

    def action_do_pdf(self):
        for requirement in self:
            self.env.ref('applicant_skills_assessment_email.action_pdf_requirement').render_qweb_pdf(requirement.id)
            requirement.state = 'confirmed'
            requirement.requirement_state = 'done'

    def action_reactivate(self):
        self.state = 'confirmed'

    @api.model
    def create(self, vals):
        res = super(ApplicantRequirement, self).create(vals)
        if len(res.requirement_detail_ids.ids) == 0:
            raise ValidationError(_('No line of requirements found in this record. Please add at least one line!'))
        return res

    def write(self, vals):
        if 'requirement_detail_ids' in vals and len(vals['requirement_detail_ids']) == 1 and \
                vals['requirement_detail_ids'][0][2] == False:
            raise ValidationError(_('No line of requirements found in this record. Please add at least one line!'))
        return super(ApplicantRequirement, self).write(vals)

    def _find_mail_template(self):
        template_id = self.env['ir.model.data'].xmlid_to_res_id('sale.mail_template_sale_confirmation',
                                                                raise_if_not_found=False)
        if not template_id:
            template_id = self.env['ir.model.data'].xmlid_to_res_id('sale.email_template_edi_sale',
                                                                    raise_if_not_found=False)
        return template_id

    def action_requirements_send(self):
        self.ensure_one()
        template = self.env.ref('applicant_skills_assessment_email.email_template_applicant_requirement',
                                raise_if_not_found=False)
        if template:
            for receipt in self.applicant_ids:
                if receipt.email_from and EMAIL_REGEX.match(receipt.email_from):
                    email_values = {'subject': self.name,
                                    'email_to': receipt.email_from,
                                    'email_from': self.env.user.email or '',
                                    }
                    attachments = []
                    for document in self.document_ids:
                        if document.type == 'binary':
                            attachments.append((0, 0, {'name': document.name,
                                                       'mimetype': document.mimetype,
                                                       'datas': base64.b64encode(document.datas)}))
                    email_values['attachment_ids'] = attachments
                    template.sudo().send_mail(self.id,
                                              email_values=email_values, force_send=True)
            self.state = 'sent'
        else:
            raise ValidationError(
                _('Can not find the mail template required to send email. Please contact your admin.'))
