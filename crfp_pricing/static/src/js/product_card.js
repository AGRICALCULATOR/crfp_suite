/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

export class ProductCard extends Component {
    static template = "crfp_pricing.ProductCard";
    static props = {
        line: Object,
        boxTypes: Array,
        onUpdate: Function,
        onToggleInclude: Function,
    };

    setup() {
        this.state = useState({ showDetail: false });
    }

    toggleDetail() {
        this.state.showDetail = !this.state.showDetail;
    }

    onFieldChange(field, ev) {
        const value = parseFloat(ev.target.value) || 0;
        this.props.onUpdate(this.props.line.crfp_product_id, field, value);
    }

    onBoxTypeChange(ev) {
        const cost = parseFloat(ev.target.value) || 0;
        this.props.onUpdate(this.props.line.crfp_product_id, 'box_cost', cost);
    }

    onToggle() {
        this.props.onToggleInclude(this.props.line.crfp_product_id);
    }

    fmt(v, d = 2) {
        return (v || 0).toFixed(d);
    }
}
