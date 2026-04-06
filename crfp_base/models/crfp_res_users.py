from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    crfp_role = fields.Selection([
        ('user', 'User'),
        ('manager', 'Manager'),
    ], string='CR Farm Role',
       compute='_compute_crfp_role',
       inverse='_set_crfp_role',
       store=False,
    )

    def _compute_crfp_role(self):
        manager_group = self.env.ref('crfp_base.group_crfp_manager', raise_if_not_found=False)
        user_group = self.env.ref('crfp_base.group_crfp_user', raise_if_not_found=False)
        for user in self:
            if manager_group and manager_group in user.groups_id:
                user.crfp_role = 'manager'
            elif user_group and user_group in user.groups_id:
                user.crfp_role = 'user'
            else:
                user.crfp_role = False

    def _set_crfp_role(self):
        manager_group = self.env.ref('crfp_base.group_crfp_manager', raise_if_not_found=False)
        user_group = self.env.ref('crfp_base.group_crfp_user', raise_if_not_found=False)
        for user in self:
            role = user.crfp_role
            if manager_group:
                user.groups_id = [(4, manager_group.id)] if role == 'manager' else [(3, manager_group.id)]
            if user_group:
                user.groups_id = [(4, user_group.id)] if role in ('user', 'manager') else [(3, user_group.id)]
