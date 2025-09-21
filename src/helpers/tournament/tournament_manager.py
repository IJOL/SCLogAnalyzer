import threading
from typing import Optional, Dict, Any, List
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager
from helpers.core.data_provider import get_data_provider
from helpers.tournament.tournament import Tournament, TournamentStatus
from helpers.tournament.tournament_schema import TournamentSchemaManager

class TournamentManager:
    """Manages tournament operations with thread-safe state management"""

    def __init__(self):
        self._lock = threading.RLock()
        self._active_tournament: Optional[Tournament] = None
        self._config_manager = get_config_manager(in_gui=True)
        self._data_provider = get_data_provider(self._config_manager)
        self._initialize_event_handlers()

    def _initialize_event_handlers(self):
        """Set up MessageBus event handlers"""
        message_bus.on("application_startup", self._on_application_startup)
        message_bus.on("tournament_status_changed", self._on_tournament_status_changed)

    def _on_application_startup(self, event_data):
        """Handle application startup - restore active tournament"""
        try:
            self._restore_active_tournament()
        except Exception as e:
            message_bus.publish(f"Error restoring tournament state: {str(e)}", MessageLevel.ERROR)

    def _on_tournament_status_changed(self, event_data):
        """Handle tournament status changes"""
        tournament_id = event_data.get("tournament_id")
        new_status = event_data.get("new_status")

        if new_status == "active":
            self._config_manager.set("tournament.current_active_tournament", tournament_id)
        elif new_status == "completed":
            self._config_manager.set("tournament.current_active_tournament", None)

    def create_tournament(self, tournament_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new tournament with database initialization"""
        with self._lock:
            try:
                # Initialize schema if needed
                if not TournamentSchemaManager.initialize_schema(self._data_provider):
                    return {"success": False, "error": "Failed to initialize database schema"}

                # Create tournament object
                tournament = Tournament(tournament_data)

                # Store in database
                success = self._data_provider.store_tournament(tournament.to_dict())
                if not success:
                    return {"success": False, "error": "Failed to store tournament in database"}

                message_bus.emit("tournament_created", {
                    "tournament_id": tournament.id,
                    "tournament_name": tournament.name,
                    "created_by": tournament.created_by
                })

                message_bus.publish(f"Created tournament: {tournament.name}", MessageLevel.INFO)

                return {
                    "success": True,
                    "tournament_id": tournament.id,
                    "tournament": tournament.to_dict()
                }

            except Exception as e:
                message_bus.publish(f"Error creating tournament: {str(e)}", MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def activate_tournament(self, tournament_id: str) -> Dict[str, Any]:
        """Activate tournament for event tagging"""
        with self._lock:
            try:
                tournament_data = self._data_provider.get_tournament(tournament_id)
                if not tournament_data:
                    return {"success": False, "error": "Tournament not found"}

                tournament = Tournament.from_dict(tournament_data)
                tournament.update_status("active")

                # Update database
                success = self._data_provider.update_tournament(tournament_id, tournament.to_dict())
                if not success:
                    return {"success": False, "error": "Failed to update tournament status"}

                self._active_tournament = tournament

                message_bus.emit("tournament_activated", {
                    "tournament_id": tournament_id,
                    "participants": tournament.participants
                })

                message_bus.publish(f"Activated tournament: {tournament.name}", MessageLevel.INFO)

                return {"success": True, "tournament": tournament.to_dict()}

            except Exception as e:
                message_bus.publish(f"Error activating tournament: {str(e)}", MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def add_participant(self, tournament_id: str, participant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add participant to tournament and team"""
        with self._lock:
            try:
                tournament_data = self._data_provider.get_tournament(tournament_id)
                if not tournament_data:
                    return {"success": False, "error": "Tournament not found"}

                tournament = Tournament.from_dict(tournament_data)

                username = participant_data["username"]
                team_name = participant_data["team"]

                success = tournament.add_participant(username, team_name)
                if not success:
                    return {"success": False, "error": "Failed to add participant"}

                # Update database
                update_success = self._data_provider.update_tournament(tournament_id, tournament.to_dict())
                if not update_success:
                    return {"success": False, "error": "Failed to update tournament in database"}

                # Update active tournament if this is it
                if self._active_tournament and self._active_tournament.id == tournament_id:
                    self._active_tournament = tournament

                message_bus.emit("participant_added", {
                    "tournament_id": tournament_id,
                    "username": username,
                    "team": team_name
                })

                return {"success": True, "tournament": tournament.to_dict()}

            except Exception as e:
                message_bus.publish(f"Error adding participant: {str(e)}", MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def get_active_tournament(self) -> Optional[Dict[str, Any]]:
        """Get currently active tournament"""
        with self._lock:
            if self._active_tournament:
                return self._active_tournament.to_dict()
            return None

    def is_tournament_participant(self, username: str) -> bool:
        """Check if user is participant in active tournament"""
        with self._lock:
            if not self._active_tournament:
                return False
            return self._active_tournament.is_participant(username)

    def get_participant_team(self, username: str) -> Optional[str]:
        """Get team for participant in active tournament"""
        with self._lock:
            if not self._active_tournament:
                return None
            return self._active_tournament.get_participant_team(username)

    def validate_status(self, status: str) -> bool:
        """Validate tournament status"""
        try:
            TournamentStatus(status)
            return True
        except ValueError:
            return False

    def _restore_active_tournament(self):
        """Restore active tournament from configuration"""
        try:
            tournament_id = self._config_manager.get("tournament.current_active_tournament")
            if not tournament_id:
                return

            tournament_data = self._data_provider.get_tournament(tournament_id)
            if tournament_data and tournament_data.get("status") == "active":
                self._active_tournament = Tournament.from_dict(tournament_data)
                message_bus.publish(f"Restored active tournament: {self._active_tournament.name}", MessageLevel.INFO)

        except Exception as e:
            message_bus.publish(f"Error restoring active tournament: {str(e)}", MessageLevel.ERROR)