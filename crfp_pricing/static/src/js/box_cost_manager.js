/** @odoo-module **/
import { Component } from "@odoo/owl";

export class BoxCostManager extends Component {
    static template = "crfp_pricing.BoxCostManager";
    static props = {
        boxTypes: Array,
    };

    fmt(v) { return (v || 0).toFixed(2); }
}
