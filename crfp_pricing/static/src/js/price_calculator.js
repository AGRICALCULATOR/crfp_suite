/** @odoo-module **/
import { Component } from "@odoo/owl";
import { ProductCard } from "./product_card";

export class PriceCalculator extends Component {
    static template = "crfp_pricing.PriceCalculator";
    static components = { ProductCard };
    static props = {
        lines: Array,
        boxTypes: Array,
        categories: Array,
        onUpdateLine: Function,
        onToggleInclude: Function,
    };

    getLinesByCategory(category) {
        return this.props.lines.filter(l => l.category === category);
    }

    getCategoryLabel(cat) {
        const labels = {
            tubers: 'Tubers & Root Vegetables',
            coconut: 'Coconut',
            sugar_cane: 'Sugar Cane',
            vegetables: 'Vegetables & Others',
        };
        return labels[cat] || cat;
    }

    getCategoryIcon(cat) {
        const icons = {
            tubers: 'fa-seedling',
            coconut: 'fa-tree',
            sugar_cane: 'fa-leaf',
            vegetables: 'fa-carrot',
        };
        return icons[cat] || 'fa-box';
    }
}
