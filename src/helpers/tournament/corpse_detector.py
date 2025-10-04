import threading
from typing import Dict, Any, Optional
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.data_provider import get_data_provider
from helpers.core.config_utils import get_config_manager
from helpers.tournament.tournament_corpse import TournamentCorpse
from helpers.tournament.tournament_manager import TournamentManager

class CorpseDetector:
    """Handles corpse detection and deduplication for tournaments"""

    def __init__(self):
        self._lock = threading.RLock()
        self._config_manager = get_config_manager(in_gui=True)
        self._data_provider = get_data_provider(self._config_manager)
        self._tournament_manager = None  # Lazy initialization to avoid circular imports
        self._initialize_event_handlers()

    def _initialize_event_handlers(self):
        """Set up MessageBus event handlers"""
        message_bus.on("corpse_detected", self._on_corpse_detected)
        message_bus.on("tournament_activated", self._on_tournament_activated)

    def _get_tournament_manager(self) -> TournamentManager:
        """Lazy initialization of tournament manager"""
        if self._tournament_manager is None:
            self._tournament_manager = TournamentManager()
        return self._tournament_manager

    def _on_corpse_detected(self, event_data):
        """Handle corpse detection events from existing system"""
        try:
            if not self._config_manager.get("tournament.corpse_detection_enabled", True):
                return

            participant_name = event_data.get("participant_name")
            detected_by = event_data.get("detected_by")
            location_data = event_data.get("location_data", {})

            if not participant_name or not detected_by:
                return

            tournament_manager = self._get_tournament_manager()
            active_tournament = tournament_manager.get_active_tournament()

            if not active_tournament:
                return

            # Check if this is a tournament participant
            if not tournament_manager.is_tournament_participant(participant_name):
                return

            # Process tournament corpse
            self.process_tournament_corpse(
                tournament_id=active_tournament["id"],
                participant_name=participant_name,
                detected_by=detected_by,
                location_data=location_data
            )

        except Exception as e:
            message_bus.publish(content=f"Error processing corpse detection: {str(e)}", level=MessageLevel.ERROR)

    def _on_tournament_activated(self, event_data):
        """Handle tournament activation"""
        tournament_id = event_data.get("tournament_id")
        participants = event_data.get("participants", [])

        message_bus.publish(content=f"Corpse detection active for {len(participants)} tournament participants", level=MessageLevel.INFO)

    def process_tournament_corpse(self, tournament_id: str, participant_name: str,
                                detected_by: str, location_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process corpse detection for tournament participant"""
        with self._lock:
            try:
                # Generate hash for deduplication
                corpse_hash = TournamentCorpse.generate_hash_from_data(
                    tournament_id, participant_name, location_data
                )

                # Check for duplicates
                if self.is_duplicate(tournament_id, corpse_hash):
                    message_bus.publish(content=f"Duplicate corpse detected for {participant_name} - skipping", level=MessageLevel.DEBUG)
                    return {"success": True, "duplicate": True}

                # Create corpse record
                corpse_data = {
                    "tournament_id": tournament_id,
                    "participant_name": participant_name,
                    "detected_by": detected_by,
                    "corpse_hash": corpse_hash,
                    "location_data": location_data,
                    "organizer_confirmed": False
                }

                corpse = TournamentCorpse(corpse_data)

                # Store in database
                success = self.store_corpse(corpse.to_dict())
                if not success:
                    return {"success": False, "error": "Failed to store corpse in database"}

                # Emit events for real-time updates
                message_bus.emit("tournament_corpse_detected", {
                    "tournament_id": tournament_id,
                    "corpse_id": corpse.id,
                    "participant_name": participant_name,
                    "detected_by": detected_by,
                    "corpse_hash": corpse_hash
                })

                message_bus.publish(content=f"Tournament corpse detected: {participant_name} by {detected_by}", level=MessageLevel.INFO)

                return {"success": True, "corpse_id": corpse.id, "duplicate": False}

            except Exception as e:
                message_bus.publish(content=f"Error processing tournament corpse: {str(e)}", level=MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def generate_corpse_hash(self, corpse_data: Dict[str, Any]) -> str:
        """Generate hash for corpse deduplication"""
        return TournamentCorpse.generate_hash_from_data(
            corpse_data.get("tournament_id"),
            corpse_data.get("participant_name"),
            corpse_data.get("location_data", {}),
            corpse_data.get("timestamp")
        )

    def is_duplicate(self, tournament_id: str, corpse_hash: str) -> bool:
        """Check if corpse is duplicate"""
        try:
            return self._data_provider.corpse_exists(tournament_id, corpse_hash)
        except Exception as e:
            message_bus.publish(content=f"Error checking corpse duplicate: {str(e)}", level=MessageLevel.ERROR)
            return False

    def store_corpse(self, corpse_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store corpse in database"""
        try:
            success = self._data_provider.store_tournament_corpse(corpse_data)
            return {"success": success}
        except Exception as e:
            message_bus.publish(content=f"Error storing corpse: {str(e)}", level=MessageLevel.ERROR)
            return {"success": False, "error": str(e)}

    def confirm_corpse(self, corpse_id: str, organizer_username: str) -> Dict[str, Any]:
        """Mark corpse as confirmed by organizer"""
        try:
            corpse_data = self._data_provider.get_tournament_corpse(corpse_id)
            if not corpse_data:
                return {"success": False, "error": "Corpse not found"}

            corpse = TournamentCorpse.from_dict(corpse_data)
            success = corpse.confirm_by_organizer(organizer_username)

            if success:
                update_success = self._data_provider.update_tournament_corpse(corpse_id, corpse.to_dict())
                return {"success": update_success}

            return {"success": False, "error": "Failed to confirm corpse"}

        except Exception as e:
            message_bus.publish(content=f"Error confirming corpse: {str(e)}", level=MessageLevel.ERROR)
            return {"success": False, "error": str(e)}