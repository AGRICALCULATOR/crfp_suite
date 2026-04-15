/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { CalculatorService } from "./calculator_service";
import { ProductCard } from "./product_card";

export class CrfpCalculator extends Component {
    static template = "crfp_pricing.CrfpCalculator";
    static components = { ProductCard };

    setup() {
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            products: [], ports: [], carriers: [], containerTypes: [],
            boxTypes: [], palletConfigs: [], incotermMatrix: {}, fixedCosts: {},
            quotationId: null, quotationName: '', partnerId: false,
            partnerSearchText: '', showPartnerDropdown: false,
            exchangeRate: 503, incoterm: 'FOB', totalBoxes: 1386,
            portId: false, containerTypeId: false, freightQuoteId: false,
            clientType: 'distribuidor',
            fc: {},
            lines: [], freightQuotes: [], quotations: [], partners: [],
            modified: false, compactView: false,
            sections: { global: true, freight: true, opCosts: false, basePrices: true, history: true },
        });

        onWillStart(async () => {
            await this.loadMasterData();
            await Promise.all([this.loadFreightQuotes(), this.loadQuotations(), this.loadPartners()]);
            this.initLines();
            this.recalcAll();
            this.state.loading = false;
        });
    }

    async loadMasterData() {
        const d = await rpc('/crfp/api/master-data', {});
        Object.assign(this.state, {
            products: d.products, ports: d.ports, carriers: d.carriers,
            containerTypes: d.container_types, boxTypes: d.box_types,
            palletConfigs: d.pallet_configs, incotermMatrix: d.incoterm_matrix,
            fixedCosts: d.fixed_costs,
            exchangeRate: d.fixed_costs.default_exchange_rate ?? 503,
            totalBoxes: d.fixed_costs.default_total_boxes || 1386,
            fc: {
                fc_transport: d.fixed_costs.transport, fc_thc_origin: d.fixed_costs.thc_origin,
                fc_fumigation: d.fixed_costs.fumigation, fc_broker: d.fixed_costs.broker,
                fc_thc_dest: d.fixed_costs.thc_dest, fc_fumig_dest: d.fixed_costs.fumig_dest,
                fc_inland_dest: d.fixed_costs.inland_dest,
                fc_insurance_pct: d.fixed_costs.insurance_pct, fc_duties_pct: d.fixed_costs.duties_pct,
            },
        });
    }
    async loadFreightQuotes() { this.state.freightQuotes = await rpc('/crfp/api/freight-quotes', {}); }
    async loadQuotations() { this.state.quotations = await rpc('/crfp/api/quotations', {}); }
    async loadPartners() { this.state.partners = await rpc('/crfp/api/partners', {}); }

    initLines() {
        this.state.lines = this.state.products.map(p => ({
            crfp_product_id: p.id, product_name: p.name, category: p.category,
            raw_price_crc: p.raw_price_crc, net_kg: p.net_kg,
            box_cost: p.default_box_cost, labor_per_kg: p.labor_per_kg,
            materials_per_kg: p.materials_per_kg, indirect_per_kg: p.indirect_per_kg,
            profit: p.default_profit, calc_type: p.calc_type,
            purchase_formula: p.purchase_formula, gross_weight_type: p.gross_weight_type,
            purchase_cost: 0, packing_cost: 0, exw_price: 0,
            logistics_per_box: 0, final_price: 0, gross_lbs: 0,
            pallets: 0,
            boxes_per_pallet: CalculatorService.getPalletBoxes(p.name, p.net_kg, this.state.palletConfigs),
            include_in_pdf: true,
        }));
    }

    recalcAll() {
        const aq = this.state.freightQuotes.find(q => q.id === this.state.freightQuoteId);
        const lc = CalculatorService.calcLogisticsCosts(this.state.fc, aq, this.state.totalBoxes);
        const im = this.state.incotermMatrix[this.state.incoterm] || {};
        for (const line of this.state.lines) {
            Object.assign(line, CalculatorService.calcSingleProduct(line, this.state.exchangeRate, lc, im));
        }
    }

    // ── Base Prices (sidebar) ──
    onBasePriceChange(productId, ev) {
        const v = parseFloat(ev.target.value) || 0;
        const l = this.state.lines.find(l => l.crfp_product_id === productId);
        if (l) { l.raw_price_crc = v; this.recalcAll(); this.state.modified = true; }
    }

    toggleSection(s) { this.state.sections[s] = !this.state.sections[s]; }

    // ── Header ──
    onQuotationNameChange(ev) { this.state.quotationName = ev.target.value; this.state.modified = true; }
    // ── Client search ──
    onPartnerSearch(ev) {
        this.state.partnerSearchText = ev.target.value;
        this.state.showPartnerDropdown = true;
    }
    onPartnerFocus() {
        this.state.showPartnerDropdown = true;
    }
    onPartnerBlur() {
        // Delay to allow mousedown on dropdown option
        setTimeout(() => { this.state.showPartnerDropdown = false; }, 200);
    }
    selectPartner(partner) {
        this.state.partnerId = partner.id;
        this.state.partnerSearchText = partner.name;
        this.state.showPartnerDropdown = false;
        if (!this.state.quotationName) {
            this.state.quotationName = `${partner.name} ${this.state.incoterm}`;
        }
        this.state.modified = true;
    }
    clearPartner() {
        this.state.partnerId = false;
        this.state.partnerSearchText = '';
        this.state.showPartnerDropdown = false;
        this.state.modified = true;
    }
    get filteredPartners() {
        const q = (this.state.partnerSearchText || '').toLowerCase().trim();
        if (!q) return this.state.partners.slice(0, 20);
        return this.state.partners.filter(p =>
            (p.name || '').toLowerCase().includes(q) ||
            (p.email || '').toLowerCase().includes(q)
        ).slice(0, 20);
    }

    // ── Global params ──
    onExchangeRateChange(ev) { this.state.exchangeRate = parseFloat(ev.target.value) || 503; this.recalcAll(); this.state.modified = true; }
    onIncotermChange(ev) { this.state.incoterm = ev.target.value; this.recalcAll(); this.state.modified = true; }
    onPortChange(ev) { this.state.portId = parseInt(ev.target.value) || false; this.state.modified = true; }
    onTotalBoxesChange(ev) { this.state.totalBoxes = parseInt(ev.target.value) || 1386; this.recalcAll(); this.state.modified = true; }
    onFreightQuoteChange(ev) { this.state.freightQuoteId = parseInt(ev.target.value) || false; this.recalcAll(); this.state.modified = true; }

    // ── Operation Costs (per quotation) ──
    onFcChange(field, ev) {
        const v = parseFloat(ev.target.value) || 0;
        this.state.fc[field] = v;
        this.recalcAll();
        this.state.modified = true;
    }
    activeQuoteIncludes(flag) {
        if (!this.state.freightQuoteId) return false;
        const fq = this.state.freightQuotes.find(q => q.id === this.state.freightQuoteId);
        return fq ? fq[flag] : false;
    }

    // ── Product card events ──
    updateLine(productId, field, value) {
        const l = this.state.lines.find(l => l.crfp_product_id === productId);
        if (l) { l[field] = value; this.recalcAll(); this.state.modified = true; }
    }
    toggleInclude(productId) {
        const l = this.state.lines.find(l => l.crfp_product_id === productId);
        if (l) { l.include_in_pdf = !l.include_in_pdf; this.state.modified = true; }
    }
    toggleCompact() { this.state.compactView = !this.state.compactView; }

    // ── Save / Load / New ──
    async saveQuotation() {
        if (!this.state.quotationName) { this.notification.add("Enter a quotation name", { type: "warning" }); return; }
        const data = {
            id: this.state.quotationId, name: this.state.quotationName,
            partner_id: this.state.partnerId || false, client_type: this.state.clientType,
            exchange_rate: this.state.exchangeRate, incoterm: this.state.incoterm,
            freight_quote_id: this.state.freightQuoteId || false,
            port_id: this.state.portId || false, container_type_id: this.state.containerTypeId || false,
            total_boxes: this.state.totalBoxes, etd: false, eta: false,
            vessel_name: '', shipping_company: '',
            ...this.state.fc,
            lines: this.state.lines.map(l => ({
                crfp_product_id: l.crfp_product_id, raw_price_crc: l.raw_price_crc,
                net_kg: l.net_kg, box_cost: l.box_cost, labor_per_kg: l.labor_per_kg,
                materials_per_kg: l.materials_per_kg, indirect_per_kg: l.indirect_per_kg,
                profit: l.profit, purchase_cost: l.purchase_cost, packing_cost: l.packing_cost,
                exw_price: l.exw_price, logistics_per_box: l.logistics_per_box,
                final_price: l.final_price, gross_lbs: l.gross_lbs,
                pallets: l.pallets, boxes_per_pallet: l.boxes_per_pallet, include_in_pdf: l.include_in_pdf,
            })),
        };
        const r = await rpc('/crfp/api/quotation/save', { data });
        this.state.quotationId = r.id;
        this.state.modified = false;
        await this.loadQuotations();
        this.notification.add(`Saved "${r.name}"`, { type: "success" });
    }

    async loadQuotation(qId) {
        const d = await rpc('/crfp/api/quotation/load', { quotation_id: qId });
        if (d.error) { this.notification.add(d.error, { type: "danger" }); return; }
        // Set partner search text from loaded partner name
        const partnerName = d.partner_id ? (this.state.partners.find(p => p.id === d.partner_id) || {}).name || '' : '';
        Object.assign(this.state, {
            quotationId: d.id, quotationName: d.name, partnerId: d.partner_id,
            partnerSearchText: partnerName,
            clientType: d.client_type, exchangeRate: d.exchange_rate, incoterm: d.incoterm,
            freightQuoteId: d.freight_quote_id, portId: d.port_id,
            containerTypeId: d.container_type_id, totalBoxes: d.total_boxes,
            fc: {
                fc_transport: d.fc_transport, fc_thc_origin: d.fc_thc_origin,
                fc_fumigation: d.fc_fumigation, fc_broker: d.fc_broker,
                fc_thc_dest: d.fc_thc_dest, fc_fumig_dest: d.fc_fumig_dest,
                fc_inland_dest: d.fc_inland_dest, fc_insurance_pct: d.fc_insurance_pct,
                fc_duties_pct: d.fc_duties_pct,
            },
        });
        for (const sl of d.lines) {
            const l = this.state.lines.find(l => l.crfp_product_id === sl.crfp_product_id);
            if (l) Object.assign(l, {
                raw_price_crc: sl.raw_price_crc, net_kg: sl.net_kg, box_cost: sl.box_cost,
                labor_per_kg: sl.labor_per_kg, materials_per_kg: sl.materials_per_kg,
                indirect_per_kg: sl.indirect_per_kg, profit: sl.profit,
                pallets: sl.pallets, boxes_per_pallet: sl.boxes_per_pallet, include_in_pdf: sl.include_in_pdf,
            });
        }
        this.recalcAll();
        this.state.modified = false;
    }

    newQuotation() {
        Object.assign(this.state, { quotationId: null, quotationName: '', partnerId: false, partnerSearchText: '' });
        this.initLines(); this.recalcAll(); this.state.modified = false;
    }

    openQuotationForm(qId) {
        this.action.doAction({
            type: 'ir.actions.act_window', res_model: 'crfp.quotation',
            res_id: qId || this.state.quotationId, views: [[false, 'form']], target: 'current',
        });
    }

    // ── Helpers ──
    get categories() {
        const c = [...new Set(this.state.lines.map(l => l.category))];
        return ['tubers','coconut','sugar_cane','vegetables'].filter(x => c.includes(x));
    }
    get activeQuoteName() {
        const q = this.state.freightQuotes.find(q => q.id === this.state.freightQuoteId);
        return q ? `${q.carrier_name} — $${(q.all_in_freight||0).toFixed(0)}` : 'No quote selected';
    }
    get logSummary() {
        const aq = this.state.freightQuotes.find(q => q.id === this.state.freightQuoteId);
        return CalculatorService.calcLogisticsCosts(this.state.fc, aq, this.state.totalBoxes);
    }
    get portDisplay() {
        const p = this.state.ports.find(p => p.id === this.state.portId);
        return p ? p.code : '—';
    }
    getCatLabel(c) { return {tubers:'Tubérculos y Raíces',coconut:'Coco',sugar_cane:'Caña de Azúcar',vegetables:'Vegetales y Otros'}[c]||c; }
    getCatIcon(c) { return {tubers:'fa-seedling',coconut:'fa-tree',sugar_cane:'fa-leaf',vegetables:'fa-carrot'}[c]||'fa-box'; }
    getLinesByCat(c) { return this.state.lines.filter(l => l.category === c); }
    fmt(v,d=2) { return (v||0).toFixed(d); }
}

registry.category("actions").add("crfp_pricing.calculator", CrfpCalculator);
