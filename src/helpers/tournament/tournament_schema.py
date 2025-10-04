import threading
from typing import Optional
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager

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

    -- Enable RLS on tournaments
    ALTER TABLE tournaments ENABLE ROW LEVEL SECURITY;

    -- RLS Policy: Allow all users to read all tournaments
    CREATE POLICY tournaments_select_policy ON tournaments
        FOR SELECT
        USING (true);

    -- RLS Policy: Allow authenticated users to insert tournaments
    CREATE POLICY tournaments_insert_policy ON tournaments
        FOR INSERT
        WITH CHECK (true);

    -- RLS Policy: Allow users to update tournaments
    CREATE POLICY tournaments_update_policy ON tournaments
        FOR UPDATE
        USING (true);

    -- RLS Policy: Allow users to delete tournaments
    CREATE POLICY tournaments_delete_policy ON tournaments
        FOR DELETE
        USING (true);

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

    -- Enable RLS on tournament_corpses
    ALTER TABLE tournament_corpses ENABLE ROW LEVEL SECURITY;

    -- RLS Policy: Allow all users to read corpses
    CREATE POLICY tournament_corpses_select_policy ON tournament_corpses
        FOR SELECT
        USING (true);

    -- RLS Policy: Allow authenticated users to insert corpses
    CREATE POLICY tournament_corpses_insert_policy ON tournament_corpses
        FOR INSERT
        WITH CHECK (true);

    -- RLS Policy: Allow all to update corpses
    CREATE POLICY tournament_corpses_update_policy ON tournament_corpses
        FOR UPDATE
        USING (true);

    -- RLS Policy: Allow all to delete corpses
    CREATE POLICY tournament_corpses_delete_policy ON tournament_corpses
        FOR DELETE
        USING (true);

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