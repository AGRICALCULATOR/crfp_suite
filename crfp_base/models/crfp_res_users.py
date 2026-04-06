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
            if manager_group and user in manager_group.sudo().users:
                user.crfp_role = 'manager'
            elif user_group and user in user_group.sudo().users:
                user.crfp_role = 'user'
            else:
                user.crfp_role = False

    def _set_crfp_role(self):
        manager_group = self.env.ref('crfp_base.group_crfp_manager', raise_if_not_found=False)
        user_group = self.env.ref('crfp_base.group_crfp_user', raise_if_not_found=False)
        for user in self:
            role = user.crfp_role
            if manager_group:
                if role == 'manager':
                    manager_group.sudo().users = [(4, user.id)]
                else:
                    manager_group.sudo().users = [(3, user.id)]
            if user_group:
                if role in ('user', 'manager'):
                    user_group.sudo().users = [(4, user.id)]
                else:
                    user_group.sudo().users = [(3, user.id)]
