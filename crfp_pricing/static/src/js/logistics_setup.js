/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

export class LogisticsSetup extends Component {
    static template = "crfp_pricing.LogisticsSetup";
    static props = ["*"];

    setup() {
        this.state = useState({
            showAddForm: false,
            editQuoteId: null,
            form: this.emptyForm(),
            filterPortId: null,
        });
    }

    emptyForm() {
        return {
            carrier_id: '',
            port_id: '',
            container_type_id: '',
            delivery_type: 'port-port',
            all_in_freight: 0,
            transit_days: 0,
            routing: 'direct',
            transship_port: '',
            valid_from: '',
            valid_until: '',
            source: '',
            name: '',
            notes: '',
            inc_transport: false,
            inc_thc_origin: false,
            inc_broker: false,
            inc_thc_dest: false,
            inc_inland_dest: false,
            inc_fumig_dest: false,
        };
    }

    openAdd() {
        this.state.form = this.emptyForm();
        this.state.editQuoteId = null;
        this.state.showAddForm = true;
    }

    openEdit(quote) {
        this.state.form = {
            carrier_id: quote.carrier_id[0],
            port_id: quote.port_id[0],
            container_type_id: quote.container_type_id ? quote.container_type_id[0] : '',
            delivery_type: quote.delivery_type,
            all_in_freight: quote.all_in_freight,
            transit_days: quote.transit_days,
            routing: quote.routing,
            transship_port: quote.transship_port || '',
            valid_from: quote.valid_from || '',
            valid_until: quote.valid_until || '',
            source: quote.source || '',
            name: quote.name || '',
            notes: quote.notes || '',
            inc_transport: quote.inc_transport,
            inc_thc_origin: quote.inc_thc_origin,
            inc_broker: quote.inc_broker,
            inc_thc_dest: quote.inc_thc_dest,
            inc_inland_dest: quote.inc_inland_dest,
            inc_fumig_dest: quote.inc_fumig_dest,
        };
        this.state.editQuoteId = quote.id;
        this.state.showAddForm = true;
    }

    cancelForm() {
        this.state.showAddForm = false;
    }

    async saveForm() {
        const vals = { ...this.state.form };
        vals.carrier_id = parseInt(vals.carrier_id) || false;
        vals.port_id = parseInt(vals.port_id) || false;
        vals.container_type_id = parseInt(vals.container_type_id) || false;
        vals.all_in_freight = parseFloat(vals.all_in_freight) || 0;
        vals.transit_days = parseInt(vals.transit_days) || 0;
        if (this.state.editQuoteId) {
            vals.id = this.state.editQuoteId;
        }
        await this.props.onSaveQuote(vals);
        this.state.showAddForm = false;
    }

    onFixedField(field, ev) {
        const value = parseFloat(ev.target.value) || 0;
        this.props.onFixedCostChange(field, value);
    }

    fmt(v) { return (v || 0).toFixed(2); }

    get filteredQuotes() {
        if (!this.state.filterPortId) return this.props.freightQuotes;
        return this.props.freightQuotes.filter(
            q => q.port_id && q.port_id[0] === parseInt(this.state.filterPortId)
        );
    }

    getIncotermCostPerBox(incCode) {
        const m = this.props.incotermMatrix[incCode];
        if (!m) return 0;
        // Simplified — uses average EXW for display (actual calc is per-product)
        return 0; // Will be computed per-product in main calculator
    }
}
