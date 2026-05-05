import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE account_move
        ADD COLUMN IF NOT EXISTS fp_reference_exchange_rate NUMERIC
    """)
    _logger.info("Pre-migration 5.0.21: added fp_reference_exchange_rate column to account_move")
