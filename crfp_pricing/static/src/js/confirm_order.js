/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

export class ConfirmOrder extends Component {
    static template = "crfp_pricing.ConfirmOrder";
    static props = ["*"];

    setup() {
        this.state = useState({
            selectedQuotationId: null,
            selectedPartnerId: null,
            creating: false,
        });
    }

    async onQuotationSelect(ev) {
        const id = parseInt(ev.target.value);
        if (id) {
            this.state.selectedQuotationId = id;
            await this.props.onLoadQuotation(id);
        }
    }

    async onCreate() {
        this.state.creating = true;
        try {
            await this.props.onCreateSaleOrder(this.state.selectedPartnerId);
        } finally {
            this.state.creating = false;
        }
    }

    onPallet(productId, ev) {
        const val = parseInt(ev.target.value) || 0;
        this.props.onPalletChange(productId, val);
    }

    fmt(v) { return (v || 0).toFixed(2); }

    get includedLines() {
        return this.props.lines.filter(l => l.include_in_pdf && l.pallets > 0);
    }

    get totalBoxes() {
        return this.includedLines.reduce(
            (sum, l) => sum + (l.pallets * l.boxes_per_pallet), 0
        );
    }

    get totalAmount() {
        return this.includedLines.reduce(
            (sum, l) => sum + (l.pallets * l.boxes_per_pallet * l.final_price), 0
        );
    }
}
