import threading
import time
from typing import Optional
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager
from helpers.core.supabase_manager import supabase_manager

class TournamentSchemaManager:
    """Manages tournament database schema with lazy initialization"""

    _schema_initialized = False
    _schema_lock = threading.Lock()

    TOURNAMENT_SCHEMA_SQL = """
    -- Tournament main table
    CREATE TABLE IF NOT EXISTS tournaments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT NOT NULL UNIQUE,
        participants JSONB NOT NULL DEFAULT '[]'::jsonb,
        teams JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'created',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        created_by TEXT NOT NULL,
        activated_by TEXT,
        activated_from TIMESTAMP WITH TIME ZONE,
        activated_to TIMESTAMP WITH TIME ZONE,
        config JSONB DEFAULT '{}'::jsonb
    );

    -- Enable RLS on tournaments (policies are permissive by default)
    ALTER TABLE tournaments ENABLE ROW LEVEL SECURITY;

    -- Tournament corpse tracking with deduplication
    CREATE TABLE IF NOT EXISTS tournament_corpses (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
        participant_name TEXT NOT NULL,
        corpse_hash TEXT NOT NULL,
        detected_by TEXT NOT NULL,
        organizer_confirmed BOOLEAN DEFAULT FALSE,
        detected_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        location_data JSONB DEFAULT '{}'::jsonb,
        UNIQUE(tournament_id, corpse_hash)
    );

    -- Enable RLS on tournament_corpses (policies are permissive by default)
    ALTER TABLE tournament_corpses ENABLE ROW LEVEL SECURITY;

    -- Index for performance
    CREATE INDEX IF NOT EXISTS idx_tournament_corpses_tournament_id ON tournament_corpses(tournament_id);
    CREATE INDEX IF NOT EXISTS idx_tournament_corpses_hash ON tournament_corpses(corpse_hash);
    """

    COMBAT_TABLE_EXTENSIONS = """
    -- Extend existing combat tables with tournament_id
    ALTER TABLE sc_default ADD COLUMN IF NOT EXISTS tournament_id UUID NULL;
    ALTER TABLE ea_squadronbattle ADD COLUMN IF NOT EXISTS tournament_id UUID NULL;
    ALTER TABLE ea_freeflight ADD COLUMN IF NOT EXISTS tournament_id UUID NULL;
    ALTER TABLE ea_fpskillconfirmed ADD COLUMN IF NOT EXISTS tournament_id UUID NULL;
    ALTER TABLE ea_fpsgungame ADD COLUMN IF NOT EXISTS tournament_id UUID NULL;
    ALTER TABLE ea_tonkroyale_teambattle ADD COLUMN IF NOT EXISTS tournament_id UUID NULL;

    """

    @classmethod
    def initialize_schema(cls, data_provider) -> bool:
        """Initialize tournament schema if not already done"""
        with cls._schema_lock:
            # Check if tables already exist
            if supabase_manager._table_exists("tournaments") and supabase_manager._table_exists("tournament_corpses"):
                cls._schema_initialized = True
                return True

            if cls._schema_initialized:
                return True

            try:
                message_bus.publish(
                    content="Initializing tournament database schema...",
                    level=MessageLevel.INFO
                )

                # Execute tournament schema
                success = data_provider.execute_sql(cls.TOURNAMENT_SCHEMA_SQL)
                if not success:
                    message_bus.publish(
                        content="Failed to create tournament tables",
                        level=MessageLevel.ERROR
                    )
                    return False

                # Wait and verify tables were created (Supabase async)
                max_retries = 20
                retry_delay = 0.5  # 500ms (total max 10 seconds)
                tables_created = False

                for retry in range(max_retries):
                    if supabase_manager._table_exists("tournaments") and supabase_manager._table_exists("tournament_corpses"):
                        tables_created = True
                        break

                    if retry < max_retries - 1:  # Don't sleep on last retry
                        time.sleep(retry_delay)

                if not tables_created:
                    message_bus.publish(
                        content="Timeout waiting for tournament tables to be created",
                        level=MessageLevel.ERROR
                    )
                    return False

                # Execute combat table extensions
                success = data_provider.execute_sql(cls.COMBAT_TABLE_EXTENSIONS)
                if not success:
                    message_bus.publish(
                        content="Failed to extend combat tables",
                        level=MessageLevel.ERROR
                    )
                    return False

                cls._schema_initialized = True
                message_bus.publish(
                    content="Tournament database schema initialized successfully",
                    level=MessageLevel.INFO
                )
                return True

            except Exception as e:
                message_bus.publish(
                    content=f"Error initializing tournament schema: {str(e)}",
                    level=MessageLevel.ERROR
                )
                return False

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if schema is initialized"""
        return cls._schema_initialized