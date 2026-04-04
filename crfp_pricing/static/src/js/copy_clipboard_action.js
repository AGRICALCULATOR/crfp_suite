/** @odoo-module **/
import { registry } from "@web/core/registry";

/**
 * Client action that copies text to the system clipboard.
 * Used by Field Buyer's "Copiar Link" button via action_copy_link().
 */
registry.category("actions").add("crfp_pricing.copy_to_clipboard", async ({ action }) => {
    const text = action.params && action.params.text ? action.params.text : "";
    if (text && navigator.clipboard) {
        try {
            await navigator.clipboard.writeText(text);
        } catch (_e) {
            // Clipboard API denied (e.g. non-HTTPS context) — no-op, URL is visible in the notification
        }
    }
});
