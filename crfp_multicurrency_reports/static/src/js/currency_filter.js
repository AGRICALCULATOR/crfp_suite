/** @odoo-module **/

import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { patch } from "@web/core/utils/patch";

/**
 * Patch the AccountReportFilters component to handle currency selection.
 *
 * When the user selects a currency from the dropdown, we update the
 * options and trigger a full report reload.
 */
patch(AccountReportFilters.prototype, {
    /**
     * Handle currency selection from the dropdown.
     * @param {Number} currencyId - The selected currency's res.currency ID
     */
    _onCurrencySelected(currencyId) {
        const opts = this.controller.options;
        if (!opts.currency_filter) {
            return;
        }

        // Update selected state on all currencies
        for (const currency of opts.currency_filter.available_currencies) {
            currency.selected = (currency.id === currencyId);
        }
        opts.currency_filter.selected_currency_id = currencyId;

        // Trigger report reload with updated options
        this.controller.reload({ opts });
    },

    /**
     * Get the label for the currently selected currency.
     * Used in the template as a fallback.
     * @returns {String} Currency name or "Currency"
     */
    _getCurrencyLabel(options) {
        const cf = options && options.currency_filter;
        if (!cf) {
            return "Currency";
        }
        const selected = cf.available_currencies.find(
            (c) => c.id === cf.selected_currency_id
        );
        return selected ? selected.name : "Currency";
    },
});
