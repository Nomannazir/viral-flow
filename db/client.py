import logging
from config import config

logger = logging.getLogger(__name__)

db = None

if config.supabase_url and config.supabase_key:
    try:
        from supabase import create_client
        db = create_client(config.supabase_url, config.supabase_key)
        logger.info("Supabase connected")
    except Exception as e:
        logger.warning(f"Supabase connection failed: {e}")
else:
    logger.info("Supabase not configured — running without database persistence")
