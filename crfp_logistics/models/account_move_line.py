from odoo import models, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _fp_apply_default_weights(self):
        """Override: skip weight recalculation when invoice is linked to a shipment.

        Without this override, editing quantity or product on an invoice line
        triggers the onchange in l10n_cr_einvoice that resets fp_net_weight and
        fp_gross_weight to product.weight * qty, overwriting the accurate
        weights that were pushed from crfp_logistics via
        _push_weights_and_dates_to_invoice().

        Export invoices ARE edited after creation (e.g. container-loading
        corrections), so this protection is necessary.
        """
        for line in self:
            ship = False
            if 'crfp_shipment_id' in line.move_id._fields:
                ship = line.move_id.crfp_shipment_id
            if ship:
                # Weights come from the shipment - do not reset them.
                # If the user needs to update weights after editing the
                # invoice, they should use the Push Weights button on
                # the shipment form.
                continue
            # No shipment linked - fall back to default product weight logic
            super(AccountMoveLine, line)._fp_apply_default_weights()
