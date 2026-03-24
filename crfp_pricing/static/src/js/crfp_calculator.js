/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

import { CalculatorService } from "./calculator_service";
import { PriceCalculator } from "./price_calculator";
import { LogisticsSetup } from "./logistics_setup";
import { BoxCostManager } from "./box_cost_manager";
import { ConfirmOrder } from "./confirm_order";
import { PriceHistory } from "./price_history";

export class CrfpCalculator extends Component {
    static template = "crfp_pricing.CrfpCalculator";
    static components = {
        PriceCalculator, LogisticsSetup, BoxCostManager, ConfirmOrder, PriceHistory,
    };

    setup() {
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            // UI state
            activeTab: 'calculator',
            loading: true,

            // Master data
            products: [],
            ports: [],
            carriers: [],
            containerTypes: [],
            boxTypes: [],
            palletConfigs: [],
            incotermMatrix: {},
            fixedCosts: {},

            // Current quotation state
            quotationId: null,
            quotationName: 'New Quotation',
            exchangeRate: 503,
            incoterm: 'FOB',
            totalBoxes: 1386,
            portId: null,
            containerTypeId: null,
            freightQuoteId: null,
            etd: '',
            eta: '',
            vesselName: '',
            shippingCompany: '',
            clientType: 'distribuidor',

            // Fixed costs for current quotation
            fc: {
                fc_transport: 600,
                fc_thc_origin: 380,
                fc_fumigation: 180,
                fc_broker: 150,
                fc_thc_dest: 0,
                fc_fumig_dest: 0,
                fc_inland_dest: 0,
                fc_insurance_pct: 0.30,
                fc_duties_pct: 0,
            },

            // Product lines (calculated)
            lines: [],

            // Freight quotes
            freightQuotes: [],

            // Saved quotations
            quotations: [],

            // Partners
            partners: [],

            // Price history
            historyData: [],

            // Modified flag
            modified: false,
        });

        onWillStart(async () => {
            await this.loadMasterData();
            await this.loadFreightQuotes();
            await this.loadQuotations();
            await this.loadPartners();
            await this.loadPriceHistory();
            this.initLines();
            this.recalcAll();
            this.state.loading = false;
        });
    }

    // ─── DATA LOADING ──────────────────────────────────────────

    async loadMasterData() {
        const data = await rpc('/crfp/api/master-data', {});
        this.state.products = data.products;
        this.state.ports = data.ports;
        this.state.carriers = data.carriers;
        this.state.containerTypes = data.container_types;
        this.state.boxTypes = data.box_types;
        this.state.palletConfigs = data.pallet_configs;
        this.state.incotermMatrix = data.incoterm_matrix;
        this.state.fixedCosts = data.fixed_costs;

        // Set defaults from fixed costs
        this.state.exchangeRate = data.fixed_costs.default_exchange_rate || 503;
        this.state.totalBoxes = data.fixed_costs.default_total_boxes || 1386;
        this.state.fc = {
            fc_transport: data.fixed_costs.transport,
            fc_thc_origin: data.fixed_costs.thc_origin,
            fc_fumigation: data.fixed_costs.fumigation,
            fc_broker: data.fixed_costs.broker,
            fc_thc_dest: data.fixed_costs.thc_dest,
            fc_fumig_dest: data.fixed_costs.fumig_dest,
            fc_inland_dest: data.fixed_costs.inland_dest,
            fc_insurance_pct: data.fixed_costs.insurance_pct,
            fc_duties_pct: data.fixed_costs.duties_pct,
        };
    }

    async loadFreightQuotes() {
        this.state.freightQuotes = await rpc('/crfp/api/freight-quotes', {});
    }

    async loadQuotations() {
        this.state.quotations = await rpc('/crfp/api/quotations', {});
    }

    async loadPartners() {
        this.state.partners = await rpc('/crfp/api/partners', {});
    }

    async loadPriceHistory() {
        this.state.historyData = await rpc('/crfp/api/price-history', {});
    }

    // ─── INITIALIZATION ────────────────────────────────────────

    initLines() {
        this.state.lines = this.state.products.map(p => ({
            crfp_product_id: p.id,
            product_name: p.name,
            category: p.category,
            raw_price_crc: p.raw_price_crc,
            net_kg: p.net_kg,
            box_cost: p.default_box_cost,
            labor_per_kg: p.labor_per_kg,
            materials_per_kg: p.materials_per_kg,
            indirect_per_kg: p.indirect_per_kg,
            profit: p.default_profit,
            calc_type: p.calc_type,
            purchase_formula: p.purchase_formula,
            gross_weight_type: p.gross_weight_type,
            // Calculated (filled by recalcAll)
            purchase_cost: 0,
            packing_cost: 0,
            exw_price: 0,
            logistics_per_box: 0,
            final_price: 0,
            gross_lbs: 0,
            // Order
            pallets: 0,
            boxes_per_pallet: CalculatorService.getPalletBoxes(
                p.name, p.net_kg, this.state.palletConfigs
            ),
            include_in_pdf: true,
        }));
    }

    // ─── CALCULATION ───────────────────────────────────────────

    recalcAll() {
        const activeQuote = this.state.freightQuotes.find(
            q => q.id === this.state.freightQuoteId
        );
        const logCosts = CalculatorService.calcLogisticsCosts(
            this.state.fc, activeQuote, this.state.totalBoxes
        );
        const incFlags = this.state.incotermMatrix[this.state.incoterm] || {};

        for (const line of this.state.lines) {
            const result = CalculatorService.calcSingleProduct(
                line, this.state.exchangeRate, logCosts, incFlags
            );
            Object.assign(line, result);
        }
    }

    // ─── EVENT HANDLERS ────────────────────────────────────────

    setTab(tab) {
        this.state.activeTab = tab;
    }

    onExchangeRateChange(ev) {
        this.state.exchangeRate = parseFloat(ev.target.value) || 503;
        this.recalcAll();
        this.state.modified = true;
    }

    onIncotermChange(ev) {
        this.state.incoterm = ev.target.value;
        this.recalcAll();
        this.state.modified = true;
    }

    onTotalBoxesChange(ev) {
        this.state.totalBoxes = parseInt(ev.target.value) || 1386;
        this.recalcAll();
        this.state.modified = true;
    }

    onPortChange(ev) {
        this.state.portId = parseInt(ev.target.value) || null;
        this.state.modified = true;
    }

    onQuotationNameChange(ev) {
        this.state.quotationName = ev.target.value;
        this.state.modified = true;
    }

    updateLine(productId, field, value) {
        const line = this.state.lines.find(l => l.crfp_product_id === productId);
        if (line) {
            line[field] = value;
            this.recalcAll();
            this.state.modified = true;
        }
    }

    toggleInclude(productId) {
        const line = this.state.lines.find(l => l.crfp_product_id === productId);
        if (line) {
            line.include_in_pdf = !line.include_in_pdf;
            this.state.modified = true;
        }
    }

    onFixedCostChange(field, value) {
        this.state.fc[field] = value;
        this.recalcAll();
        this.state.modified = true;
    }

    // ─── FREIGHT QUOTES ────────────────────────────────────────

    async selectFreightQuote(quoteId) {
        this.state.freightQuoteId = quoteId;
        this.recalcAll();
        this.state.modified = true;
    }

    async saveFreightQuote(vals) {
        await rpc('/crfp/api/freight-quote/save', { vals });
        await this.loadFreightQuotes();
        this.notification.add("Freight quote saved", { type: "success" });
    }

    async deleteFreightQuote(quoteId) {
        await rpc('/crfp/api/freight-quote/delete', { quote_id: quoteId });
        if (this.state.freightQuoteId === quoteId) {
            this.state.freightQuoteId = null;
        }
        await this.loadFreightQuotes();
        this.recalcAll();
    }

    // ─── SAVE / LOAD QUOTATIONS ────────────────────────────────

    async saveQuotation() {
        const data = {
            id: this.state.quotationId,
            name: this.state.quotationName,
            client_type: this.state.clientType,
            exchange_rate: this.state.exchangeRate,
            incoterm: this.state.incoterm,
            freight_quote_id: this.state.freightQuoteId || false,
            port_id: this.state.portId || false,
            container_type_id: this.state.containerTypeId || false,
            total_boxes: this.state.totalBoxes,
            etd: this.state.etd || false,
            eta: this.state.eta || false,
            vessel_name: this.state.vesselName,
            shipping_company: this.state.shippingCompany,
            fc_transport: this.state.fc.fc_transport,
            fc_thc_origin: this.state.fc.fc_thc_origin,
            fc_fumigation: this.state.fc.fc_fumigation,
            fc_broker: this.state.fc.fc_broker,
            fc_thc_dest: this.state.fc.fc_thc_dest,
            fc_fumig_dest: this.state.fc.fc_fumig_dest,
            fc_inland_dest: this.state.fc.fc_inland_dest,
            fc_insurance_pct: this.state.fc.fc_insurance_pct,
            fc_duties_pct: this.state.fc.fc_duties_pct,
            lines: this.state.lines.map(l => ({
                crfp_product_id: l.crfp_product_id,
                raw_price_crc: l.raw_price_crc,
                net_kg: l.net_kg,
                box_cost: l.box_cost,
                labor_per_kg: l.labor_per_kg,
                materials_per_kg: l.materials_per_kg,
                indirect_per_kg: l.indirect_per_kg,
                profit: l.profit,
                purchase_cost: l.purchase_cost,
                packing_cost: l.packing_cost,
                exw_price: l.exw_price,
                logistics_per_box: l.logistics_per_box,
                final_price: l.final_price,
                gross_lbs: l.gross_lbs,
                pallets: l.pallets,
                boxes_per_pallet: l.boxes_per_pallet,
                include_in_pdf: l.include_in_pdf,
            })),
        };

        const result = await rpc('/crfp/api/quotation/save', { data });
        this.state.quotationId = result.id;
        this.state.modified = false;
        await this.loadQuotations();
        await this.loadPriceHistory();
        this.notification.add(`Quotation "${result.name}" saved`, { type: "success" });
    }

    async loadQuotation(quotationId) {
        const data = await rpc('/crfp/api/quotation/load', { quotation_id: quotationId });
        if (data.error) {
            this.notification.add(data.error, { type: "danger" });
            return;
        }

        this.state.quotationId = data.id;
        this.state.quotationName = data.name;
        this.state.clientType = data.client_type;
        this.state.exchangeRate = data.exchange_rate;
        this.state.incoterm = data.incoterm;
        this.state.freightQuoteId = data.freight_quote_id;
        this.state.portId = data.port_id;
        this.state.containerTypeId = data.container_type_id;
        this.state.totalBoxes = data.total_boxes;
        this.state.etd = data.etd;
        this.state.eta = data.eta;
        this.state.vesselName = data.vessel_name;
        this.state.shippingCompany = data.shipping_company;
        this.state.fc = {
            fc_transport: data.fc_transport,
            fc_thc_origin: data.fc_thc_origin,
            fc_fumigation: data.fc_fumigation,
            fc_broker: data.fc_broker,
            fc_thc_dest: data.fc_thc_dest,
            fc_fumig_dest: data.fc_fumig_dest,
            fc_inland_dest: data.fc_inland_dest,
            fc_insurance_pct: data.fc_insurance_pct,
            fc_duties_pct: data.fc_duties_pct,
        };

        // Restore lines from saved data
        for (const savedLine of data.lines) {
            const line = this.state.lines.find(
                l => l.crfp_product_id === savedLine.crfp_product_id
            );
            if (line) {
                Object.assign(line, {
                    raw_price_crc: savedLine.raw_price_crc,
                    net_kg: savedLine.net_kg,
                    box_cost: savedLine.box_cost,
                    labor_per_kg: savedLine.labor_per_kg,
                    materials_per_kg: savedLine.materials_per_kg,
                    indirect_per_kg: savedLine.indirect_per_kg,
                    profit: savedLine.profit,
                    pallets: savedLine.pallets,
                    boxes_per_pallet: savedLine.boxes_per_pallet,
                    include_in_pdf: savedLine.include_in_pdf,
                });
            }
        }

        this.recalcAll();
        this.state.modified = false;
    }

    newQuotation() {
        this.state.quotationId = null;
        this.state.quotationName = 'New Quotation';
        this.initLines();
        this.recalcAll();
        this.state.modified = false;
    }

    // ─── SALE ORDER ────────────────────────────────────────────

    async createSaleOrder(partnerId) {
        if (!this.state.quotationId) {
            this.notification.add("Please save the quotation first", { type: "warning" });
            return;
        }
        // Update partner on quotation
        await rpc('/crfp/api/quotation/save', {
            data: {
                id: this.state.quotationId,
                partner_id: partnerId,
                lines: this.state.lines.map(l => ({
                    crfp_product_id: l.crfp_product_id,
                    raw_price_crc: l.raw_price_crc,
                    net_kg: l.net_kg,
                    box_cost: l.box_cost,
                    labor_per_kg: l.labor_per_kg,
                    materials_per_kg: l.materials_per_kg,
                    indirect_per_kg: l.indirect_per_kg,
                    profit: l.profit,
                    purchase_cost: l.purchase_cost,
                    packing_cost: l.packing_cost,
                    exw_price: l.exw_price,
                    logistics_per_box: l.logistics_per_box,
                    final_price: l.final_price,
                    gross_lbs: l.gross_lbs,
                    pallets: l.pallets,
                    boxes_per_pallet: l.boxes_per_pallet,
                    include_in_pdf: l.include_in_pdf,
                })),
            }
        });

        const result = await rpc('/crfp/api/quotation/create-so', {
            quotation_id: this.state.quotationId,
        });
        if (result.error) {
            this.notification.add(result.error, { type: "danger" });
            return;
        }
        this.notification.add(
            `Sale Order ${result.sale_order_name} created!`,
            { type: "success" }
        );
        // Open the SO
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'sale.order',
            res_id: result.sale_order_id,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    onPalletChange(productId, value) {
        const line = this.state.lines.find(l => l.crfp_product_id === productId);
        if (line) {
            line.pallets = value;
        }
    }

    // ─── HELPERS ───────────────────────────────────────────────

    get categories() {
        const cats = [...new Set(this.state.lines.map(l => l.category))];
        const order = ['tubers', 'coconut', 'sugar_cane', 'vegetables'];
        return order.filter(c => cats.includes(c));
    }

    get activeQuoteName() {
        const q = this.state.freightQuotes.find(
            fq => fq.id === this.state.freightQuoteId
        );
        return q ? `${q.carrier_name} — $${q.all_in_freight}` : 'No quote selected';
    }

    get logisticsSummary() {
        const activeQuote = this.state.freightQuotes.find(
            q => q.id === this.state.freightQuoteId
        );
        return CalculatorService.calcLogisticsCosts(
            this.state.fc, activeQuote, this.state.totalBoxes
        );
    }

    fmt(v, d = 2) { return (v || 0).toFixed(d); }
}

// Register as a client action
registry.category("actions").add("crfp_pricing.calculator", CrfpCalculator);
