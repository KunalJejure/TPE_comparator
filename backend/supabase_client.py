"""Supabase Client — Initialises the connection to Supabase."""

import logging
from supabase import create_client, Client
from backend.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Initialise Supabase Client
supabase: Client = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialised successfully.")
    except Exception as e:
        logger.error("Failed to initialise Supabase client: %s", e)
else:
    logger.warning("Supabase credentials are missing. Check your .env file.")

def get_supabase() -> Client:
    """Helper function to get the supabase client instance."""
    return supabase
