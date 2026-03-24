/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PriceHistory extends Component {
    static template = "crfp_pricing.PriceHistory";
    static props = ["*"];

    setup() {
        this.state = useState({
            selectedProductId: null,
        });
    }

    selectProduct(productId) {
        this.state.selectedProductId = productId;
    }

    get productHistory() {
        if (!this.state.selectedProductId) return [];
        return this.props.historyData
            .filter(h => h.crfp_product_id[0] === this.state.selectedProductId)
            .sort((a, b) => (a.date > b.date ? -1 : 1));
    }

    get productSummaries() {
        return this.props.products.map(p => {
            const history = this.props.historyData
                .filter(h => h.crfp_product_id[0] === p.id)
                .sort((a, b) => (a.date > b.date ? -1 : 1));
            const last = history[0];
            const prev = history[1];
            let change = 0;
            if (last && prev && prev.price_crc) {
                change = ((last.price_crc - prev.price_crc) / prev.price_crc) * 100;
            }
            return {
                ...p,
                lastPrice: last ? last.price_crc : 0,
                change,
                recordCount: history.length,
            };
        });
    }

    fmt(v, d = 0) { return (v || 0).toFixed(d); }
}
