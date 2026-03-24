/** @odoo-module **/

/**
 * Pure calculation logic for CR Farm export pricing.
 * Replicates exactly the formulas from the original HTML calculator.
 * No DOM, no Owl — just math.
 */
export const CalculatorService = {

    /**
     * Calculate purchase cost for a product.
     * @param {Object} product - product data with raw_price_crc, net_kg, purchase_formula
     * @param {number} exchangeRate - CRC per USD
     * @returns {number} purchase cost in USD
     */
    calcPurchaseCost(product, exchangeRate) {
        const p = product.raw_price_crc || 0;
        const k = product.net_kg || 0;
        const tc = exchangeRate || 503;
        if (product.purchase_formula === 'quintal') {
            // Quintal formula: (1 * kg / 46) * (price / tc)
            return (1 * k / 46) * (p / tc);
        }
        // Standard formula: (kg * price) / tc
        return (k * p) / tc;
    },

    /**
     * Calculate gross weight in pounds.
     */
    calcGrossLbs(product) {
        const k = product.net_kg || 0;
        switch (product.gross_weight_type) {
            case 'zero': return 0;
            case 'no_tare': return k * 2.2;
            default: return k * 2.2 + 2; // standard: add 2 lb tare
        }
    },

    /**
     * Calculate packing/fixed costs.
     */
    calcPackingCost(product) {
        const txk = (product.labor_per_kg || 0) +
                     (product.materials_per_kg || 0) +
                     (product.indirect_per_kg || 0);
        const k = product.net_kg || 0;
        const c = product.box_cost || 0;

        switch (product.calc_type) {
            case 'flat_no_box':   return txk;              // DRY COCONUT, SUGAR CANE BUNDLES
            case 'flat_plus_box': return txk + c;          // GREEN COCONUT BOX, SUGAR CANE BOX
            case 'kg_no_box':     return txk * k;          // PUMPKINS BAG
            default:              return (txk * k) + c;    // standard
        }
    },

    /**
     * Calculate logistics costs per box from fixed costs and freight quote.
     * @param {Object} fixedCosts - fc_transport, fc_thc_origin, etc.
     * @param {Object} freightQuote - all_in_freight, inc_transport, etc. (or null)
     * @param {number} totalBoxes - boxes in container
     * @returns {Object} per-box costs for each component
     */
    calcLogisticsCosts(fixedCosts, freightQuote, totalBoxes) {
        const tb = totalBoxes || 1386;
        const fq = freightQuote || {};
        const fc = fixedCosts || {};

        const frTotal = fq.all_in_freight || 0;
        const frPB = frTotal / tb;

        // Each fixed cost is zeroed if already included in freight quote
        const tUSD  = fq.inc_transport   ? 0 : (fc.fc_transport || fc.transport || 0);
        const fuUSD = fc.fc_fumigation || fc.fumigation || 0; // never included in quote
        const poUSD = fq.inc_thc_origin  ? 0 : (fc.fc_thc_origin || fc.thc_origin || 0);
        const agUSD = fq.inc_broker      ? 0 : (fc.fc_broker || fc.broker || 0);
        const tdUSD = fq.inc_thc_dest    ? 0 : (fc.fc_thc_dest || fc.thc_dest || 0);
        const fdUSD = fq.inc_fumig_dest  ? 0 : (fc.fc_fumig_dest || fc.fumig_dest || 0);
        const deUSD = fq.inc_inland_dest ? 0 : (fc.fc_inland_dest || fc.inland_dest || 0);

        return {
            tPB: tUSD / tb,
            fuPB: fuUSD / tb,
            poPB: poUSD / tb,
            agPB: agUSD / tb,
            frPB,
            tdPB: tdUSD / tb,
            fdPB: fdUSD / tb,
            dePB: deUSD / tb,
            sPct: fc.fc_insurance_pct ?? fc.insurance_pct ?? 0.30,
            aPct: fc.fc_duties_pct ?? fc.duties_pct ?? 0,
            tb,
            frTotal,
            tUSD, fuUSD, poUSD, agUSD, tdUSD, fdUSD, deUSD,
        };
    },

    /**
     * Calculate logistics cost per box for a given EXW price and incoterm.
     * @param {number} exwPrice - EXW price per box
     * @param {Object} logCosts - output of calcLogisticsCosts()
     * @param {Object} incotermFlags - from incoterm_matrix: inc_transport, inc_freight, etc.
     * @returns {number} total logistics cost per box
     */
    calcLogisticsPerBox(exwPrice, logCosts, incotermFlags) {
        const m = incotermFlags || {};
        const c = logCosts || {};

        let total = 0;
        if (m.inc_transport)   total += c.tPB  || 0;
        if (m.inc_fumigation)  total += c.fuPB || 0;
        if (m.inc_thc_origin)  total += c.poPB || 0;
        if (m.inc_broker)      total += c.agPB || 0;
        if (m.inc_freight)     total += c.frPB || 0;

        // Insurance: % of EXW price
        const insPB = m.inc_insurance ? (exwPrice * (c.sPct || 0) / 100) : 0;
        total += insPB;

        if (m.inc_thc_dest)    total += c.tdPB || 0;
        if (m.inc_fumig_dest)  total += c.fdPB || 0;
        if (m.inc_inland_dest) total += c.dePB || 0;

        // Duties: % of CIF (EXW + freight + insurance)
        if (m.inc_duties && c.aPct) {
            const cifBase = exwPrice + (m.inc_freight ? (c.frPB || 0) : 0) + insPB;
            total += cifBase * (c.aPct / 100);
        }

        return total;
    },

    /**
     * Full calculation for a single product line.
     */
    calcSingleProduct(product, exchangeRate, logCosts, incotermFlags) {
        const purchaseCost = this.calcPurchaseCost(product, exchangeRate);
        const packingCost = this.calcPackingCost(product);
        const grossLbs = this.calcGrossLbs(product);
        const exwPrice = purchaseCost + packingCost + (product.profit || 0);
        const logisticsPerBox = this.calcLogisticsPerBox(exwPrice, logCosts, incotermFlags);
        const finalPrice = exwPrice + logisticsPerBox;

        return {
            purchase_cost: Math.round(purchaseCost * 10000) / 10000,
            packing_cost: Math.round(packingCost * 10000) / 10000,
            exw_price: Math.round(exwPrice * 100) / 100,
            logistics_per_box: Math.round(logisticsPerBox * 10000) / 10000,
            final_price: Math.round(finalPrice * 100) / 100,
            gross_lbs: Math.round(grossLbs * 10) / 10,
        };
    },

    /**
     * Get boxes per pallet for a product name/weight from pallet configs.
     */
    getPalletBoxes(productName, netKg, palletConfigs) {
        const name = (productName || '').toUpperCase();
        const kg = netKg || 0;

        // Try to match from config
        if (palletConfigs && palletConfigs.length) {
            for (const cfg of palletConfigs) {
                if (name.includes(cfg.product_keyword.toUpperCase()) &&
                    Math.abs(kg - cfg.weight_kg) < 1) {
                    return cfg.boxes_per_pallet;
                }
            }
        }

        // Weight-based fallback
        if (Math.abs(kg - 18) < 1) return 66;
        if (Math.abs(kg - 16) < 1) return 60;
        if (Math.abs(kg - 10) < 1) return 100;
        if (Math.abs(kg - 13) < 1 || Math.abs(kg - 13.65) < 1) return 72;
        if (Math.abs(kg - 12) < 1) return 80;
        if (Math.abs(kg - 40) < 1) return 30;

        return 66; // default
    },
};
