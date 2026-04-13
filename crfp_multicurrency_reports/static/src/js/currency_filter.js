/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

patch(AccountReportFilters.prototype, {
    /**
     * Handle currency selection from the dropdown.
     * Follows the same pattern as selectJournal():
     *   1. Toggle selected state
     *   2. Call this.applyFilters("key")
     */
    onCurrencySelected(currencyId) {
        const cf = this.controller.cachedFilterOptions.currency_filter;
        if (!cf) return;
        for (const currency of cf.available_currencies) {
            currency.selected = (currency.id === currencyId);
        }
        cf.selected_currency_id = currencyId;
        this.applyFilters("currency_filter");
    },

    /**
     * Get label for the currently selected currency.
     * Called from the template toggler slot.
     */
    getSelectedCurrencyName() {
        const cf = this.controller.cachedFilterOptions?.currency_filter;
        if (!cf) return "";
        const selected = cf.available_currencies.find(
            (c) => c.id === cf.selected_currency_id
        );
        return selected ? selected.name : "Currency";
    },
});
