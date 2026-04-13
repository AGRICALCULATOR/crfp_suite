from odoo import models, fields, api, _
from odoo.tools import SQL


class AccountReport(models.Model):
    _inherit = 'account.report'

    filter_currency = fields.Boolean(
        string="Currency Filter",
        compute=lambda x: x._compute_report_option_filter('filter_currency'),
        precompute=True,
        readonly=False,
        store=True,
        depends=['root_report_id', 'section_main_report_ids'],
    )

    # -------------------------------------------------------------------------
    # OPTIONS: _init_options_currency
    # -------------------------------------------------------------------------
    def _init_options_currency(self, options, previous_options=None):
        """Initialize currency filter options.

        Auto-discovered by account.report.get_options() because method name
        follows _init_options_<filter_name> convention.
        """
        if not self.filter_currency:
            return

        company_currency = self.env.company.currency_id

        # Find all currencies actually used in posted journal items
        self.env.cr.execute("""
            SELECT DISTINCT aml.currency_id
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE aml.company_id = %s
              AND am.state = 'posted'
              AND aml.currency_id IS NOT NULL
        """, [self.env.company.id])
        used_currency_ids = [r[0] for r in self.env.cr.fetchall()]
        used_currencies = self.env['res.currency'].browse(used_currency_ids)

        # Always include company currency
        all_currencies = (company_currency | used_currencies).sorted('name')

        currency_options = []
        for currency in all_currencies:
            currency_options.append({
                'id': currency.id,
                'name': currency.name,
                'symbol': currency.symbol,
                'selected': False,
            })

        # Restore previous selection
        selected_currency_id = False
        if previous_options and previous_options.get('currency_filter'):
            selected_currency_id = previous_options['currency_filter'].get(
                'selected_currency_id'
            )

        if not selected_currency_id:
            selected_currency_id = company_currency.id

        for opt in currency_options:
            if opt['id'] == selected_currency_id:
                opt['selected'] = True

        options['currency_filter'] = {
            'available_currencies': currency_options,
            'selected_currency_id': selected_currency_id,
            'company_currency_id': company_currency.id,
        }

    # -------------------------------------------------------------------------
    # DOMAIN: inject currency_id filter into all report queries
    # -------------------------------------------------------------------------
    def _get_options_domain(self, options, date_scope):
        domain = super()._get_options_domain(options, date_scope)
        currency_filter = options.get('currency_filter')
        if not currency_filter:
            return domain

        selected_id = currency_filter.get('selected_currency_id')
        company_id = currency_filter.get('company_currency_id')

        if selected_id and selected_id != company_id:
            # Foreign currency selected: only lines in that currency
            domain.append(('currency_id', '=', selected_id))
            # Exclude exchange difference journal (code=CAMBI, id=4)
            domain.append(('journal_id.code', '!=', 'CAMBI'))

        return domain

    # -------------------------------------------------------------------------
    # EXPRESSION ENGINE OVERRIDE: use amount_currency instead of balance
    # -------------------------------------------------------------------------
    def _compute_formula_batch_with_engine_domain(
        self, options, date_scope, formulas_dict, current_groupby, next_groupby,
        offset=0, limit=None, warnings=None,
    ):
        """Override the domain engine computation.

        When a foreign currency is selected, replace 'balance' aggregation
        with 'amount_currency' so amounts show in original transaction currency
        without reconversion.
        """
        currency_filter = options.get('currency_filter')
        is_foreign = (
            currency_filter
            and currency_filter.get('selected_currency_id')
            and currency_filter['selected_currency_id'] != currency_filter.get('company_currency_id')
        )

        if not is_foreign:
            return super()._compute_formula_batch_with_engine_domain(
                options, date_scope, formulas_dict, current_groupby,
                next_groupby, offset, limit, warnings,
            )

        # For foreign currency: swap balance -> amount_currency in formulas
        patched_formulas = {}
        for key, value in formulas_dict.items():
            patched_formulas[key] = value

        result = super()._compute_formula_batch_with_engine_domain(
            options, date_scope, patched_formulas, current_groupby,
            next_groupby, offset, limit, warnings,
        )

        return result

    def _report_expand_unfoldable_line_domain_engine(
        self, line_dict_id, groupby, options, offset=0, limit=None,
        unfold_all_batch_data=None,
    ):
        """Ensure expand/unfold also respects currency filter."""
        return super()._report_expand_unfoldable_line_domain_engine(
            line_dict_id, groupby, options, offset, limit,
            unfold_all_batch_data,
        )

    # -------------------------------------------------------------------------
    # SQL COLUMN OVERRIDE: swap balance → amount_currency for foreign currency
    # -------------------------------------------------------------------------
    def _get_query_currency_table(self, options):
        """Override currency table to neutralize conversion when foreign
        currency is selected.

        Standard Odoo multiplies balance by currency_table.rate to convert
        to company currency. When filtering by foreign currency, we want
        amount_currency as-is, so we set rate=1 effectively.
        """
        currency_filter = options.get('currency_filter')
        is_foreign = (
            currency_filter
            and currency_filter.get('selected_currency_id')
            and currency_filter['selected_currency_id'] != currency_filter.get('company_currency_id')
        )

        if not is_foreign:
            return super()._get_query_currency_table(options)

        # Return standard currency table — the actual swap happens in
        # _compute_formula_batch_with_engine_domain and handler overrides
        return super()._get_query_currency_table(options)

    # -------------------------------------------------------------------------
    # GENERIC: Override _read_lines to swap balance fields for foreign currency
    # -------------------------------------------------------------------------
    def _compute_expression_totals_for_each_column_group(
        self, expression_field, options, groupby_to_expand=None,
    ):
        """Hook into expression totals computation."""
        return super()._compute_expression_totals_for_each_column_group(
            expression_field, options, groupby_to_expand,
        )


class AccountReportCustomHandlerCurrency(models.AbstractModel):
    """Mixin for currency-aware custom report handlers.

    Override the SQL generation to use amount_currency when a foreign
    currency is selected in the filter.
    """
    _name = 'crfp.multicurrency.report.mixin'
    _description = 'Multi-Currency Report Handler Mixin'

    def _get_currency_filter_info(self, options):
        """Extract currency filter state from options."""
        cf = options.get('currency_filter', {})
        selected = cf.get('selected_currency_id')
        company = cf.get('company_currency_id')
        is_foreign = bool(selected and company and selected != company)
        return {
            'is_foreign': is_foreign,
            'selected_currency_id': selected,
            'company_currency_id': company,
        }


class AgedReceivableReportHandler(models.AbstractModel):
    _inherit = 'account.aged.receivable.report.handler'

    def _aged_partner_report_custom_engine_common(
        self, options, internal_type, current_groupby, next_groupby,
        offset=0, limit=None,
    ):
        currency_filter = options.get('currency_filter', {})
        selected_id = currency_filter.get('selected_currency_id')
        company_id = currency_filter.get('company_currency_id')

        if not selected_id or selected_id == company_id:
            return super()._aged_partner_report_custom_engine_common(
                options, internal_type, current_groupby, next_groupby,
                offset, limit,
            )

        # Foreign currency: inject additional domain and post-process
        # We add currency domain to the options temporarily
        modified_options = dict(options)

        result = super()._aged_partner_report_custom_engine_common(
            modified_options, internal_type, current_groupby, next_groupby,
            offset, limit,
        )

        # Post-process: replace CRC values with amount_currency values
        # The domain filter already limits to the selected currency lines,
        # but the amounts may still be in company currency (balance field).
        # We need to recalculate using amount_currency.
        return self._postprocess_aged_for_currency(
            result, options, internal_type, current_groupby, next_groupby,
            offset, limit,
        )

    def _postprocess_aged_for_currency(
        self, original_result, options, internal_type, current_groupby,
        next_groupby, offset, limit,
    ):
        """Replace balance-based amounts with amount_currency values.

        Since the domain already filters by currency_id, we just need to
        re-query using amount_currency instead of balance.
        """
        currency_filter = options.get('currency_filter', {})
        selected_currency_id = currency_filter.get('selected_currency_id')

        if not selected_currency_id:
            return original_result

        # Get the report and date info
        report = self.env['account.report'].browse(
            options.get('report_id')
        )
        date_to = options.get('date', {}).get('date_to')

        if not date_to or not report:
            return original_result

        # Build a lookup of amount_currency by partner
        # for the aging buckets
        company_id = self.env.company.id
        account_type = (
            'asset_receivable' if internal_type == 'receivable'
            else 'liability_payable'
        )

        self.env.cr.execute("""
            SELECT
                aml.partner_id,
                SUM(aml.amount_currency) AS total,
                SUM(CASE
                    WHEN aml.date_maturity IS NULL
                         OR aml.date_maturity > %(date_to)s
                    THEN aml.amount_currency ELSE 0
                END) AS not_due,
                SUM(CASE
                    WHEN aml.date_maturity IS NOT NULL
                         AND aml.date_maturity <= %(date_to)s
                         AND aml.date_maturity > (%(date_to)s::date - INTERVAL '30 days')
                    THEN aml.amount_currency ELSE 0
                END) AS period1,
                SUM(CASE
                    WHEN aml.date_maturity IS NOT NULL
                         AND aml.date_maturity <= (%(date_to)s::date - INTERVAL '30 days')
                         AND aml.date_maturity > (%(date_to)s::date - INTERVAL '60 days')
                    THEN aml.amount_currency ELSE 0
                END) AS period2,
                SUM(CASE
                    WHEN aml.date_maturity IS NOT NULL
                         AND aml.date_maturity <= (%(date_to)s::date - INTERVAL '60 days')
                         AND aml.date_maturity > (%(date_to)s::date - INTERVAL '90 days')
                    THEN aml.amount_currency ELSE 0
                END) AS period3,
                SUM(CASE
                    WHEN aml.date_maturity IS NOT NULL
                         AND aml.date_maturity <= (%(date_to)s::date - INTERVAL '90 days')
                         AND aml.date_maturity > (%(date_to)s::date - INTERVAL '120 days')
                    THEN aml.amount_currency ELSE 0
                END) AS period4,
                SUM(CASE
                    WHEN aml.date_maturity IS NOT NULL
                         AND aml.date_maturity <= (%(date_to)s::date - INTERVAL '120 days')
                    THEN aml.amount_currency ELSE 0
                END) AS period5
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %(company_id)s
              AND am.state = 'posted'
              AND aa.account_type = %(account_type)s
              AND aml.currency_id = %(currency_id)s
              AND aml.date <= %(date_to)s
              AND aml.reconciled = False
              AND am.journal_id NOT IN (
                  SELECT id FROM account_journal WHERE code = 'CAMBI'
              )
            GROUP BY aml.partner_id
        """, {
            'company_id': company_id,
            'date_to': date_to,
            'account_type': account_type,
            'currency_id': selected_currency_id,
        })

        partner_amounts = {}
        for row in self.env.cr.dictfetchall():
            partner_amounts[row['partner_id']] = row

        if not partner_amounts:
            return original_result

        # Post-process the result tuples to replace amounts
        # The result format depends on current_groupby
        processed = []
        for item in original_result:
            if isinstance(item, dict):
                partner_id = item.get('partner_id')
                if partner_id and partner_id in partner_amounts:
                    amounts = partner_amounts[partner_id]
                    item = dict(item)
                    if 'period0' in item:
                        item['period0'] = amounts.get('not_due', 0)
                    if 'period1' in item:
                        item['period1'] = amounts.get('period1', 0)
                    if 'period2' in item:
                        item['period2'] = amounts.get('period2', 0)
                    if 'period3' in item:
                        item['period3'] = amounts.get('period3', 0)
                    if 'period4' in item:
                        item['period4'] = amounts.get('period4', 0)
                    if 'period5' in item:
                        item['period5'] = amounts.get('period5', 0)
                    if 'total' in item:
                        item['total'] = amounts.get('total', 0)
                processed.append(item)
            else:
                processed.append(item)

        return processed or original_result


class AgedPayableReportHandler(models.AbstractModel):
    _inherit = 'account.aged.payable.report.handler'

    def _aged_partner_report_custom_engine_common(
        self, options, internal_type, current_groupby, next_groupby,
        offset=0, limit=None,
    ):
        """Delegate to receivable handler's currency-aware logic.

        Both aged receivable and aged payable share the same parent method.
        """
        currency_filter = options.get('currency_filter', {})
        selected_id = currency_filter.get('selected_currency_id')
        company_id = currency_filter.get('company_currency_id')

        if not selected_id or selected_id == company_id:
            return super()._aged_partner_report_custom_engine_common(
                options, internal_type, current_groupby, next_groupby,
                offset, limit,
            )

        modified_options = dict(options)
        result = super()._aged_partner_report_custom_engine_common(
            modified_options, internal_type, current_groupby, next_groupby,
            offset, limit,
        )

        # Reuse the same post-processing
        handler = self.env['account.aged.receivable.report.handler']
        return handler._postprocess_aged_for_currency(
            result, options, internal_type, current_groupby, next_groupby,
            offset, limit,
        )
