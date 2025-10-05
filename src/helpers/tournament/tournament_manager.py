import threading
from datetime import datetime
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
            message_bus.publish(content=f"Error restoring tournament state: {str(e)}", level=MessageLevel.ERROR)

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

                message_bus.publish(content=f"Created tournament: {tournament.name}", level=MessageLevel.INFO)

                return {
                    "success": True,
                    "tournament_id": tournament.id,
                    "tournament": tournament.to_dict()
                }

            except Exception as e:
                message_bus.publish(content=f"Error creating tournament: {str(e)}", level=MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def activate_tournament(self, tournament_id: str, activated_by: str = None) -> Dict[str, Any]:
        """Activate tournament for event tagging"""
        with self._lock:
            try:
                tournament_data = self._data_provider.get_tournament(tournament_id)
                if not tournament_data:
                    return {"success": False, "error": "Tournament not found"}

                tournament = Tournament.from_dict(tournament_data)
                tournament.update_status("active")

                # Set activation metadata
                if activated_by:
                    tournament.activated_by = activated_by
                    tournament.activated_from = datetime.now().isoformat()

                # Update database
                tournament_dict = tournament.to_dict()
                success = self._data_provider.update_tournament(tournament_id, tournament_dict)
                if not success:
                    return {"success": False, "error": "Failed to update tournament status"}

                self._active_tournament = tournament

                message_bus.emit("tournament_activated", {
                    "tournament_id": tournament_id,
                    "teams": tournament.teams
                })

                # Notify other users via RealtimeBridge using the correct pattern
                message_bus.emit("realtime_event", {
                    "event_type": "tournament_activated",
                    "tournament_id": tournament_id,
                    "tournament_name": tournament.name,
                    "team_composition": tournament.teams,  # Dict with team_name: [player_list]
                    "tournament_type": tournament.config.get("tournament_type", "sc_default") if tournament.config else "sc_default"
                })

                message_bus.publish(content=f"Activated tournament: {tournament.name}", level=MessageLevel.INFO)

                return {"success": True, "tournament": tournament.to_dict()}

            except Exception as e:
                message_bus.publish(content=f"Error activating tournament: {str(e)}", level=MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def pause_tournament(self, tournament_id: str) -> Dict[str, Any]:
        """Pause an active tournament"""
        with self._lock:
            try:
                tournament_data = self._data_provider.get_tournament(tournament_id)
                if not tournament_data:
                    return {"success": False, "error": "Tournament not found"}

                tournament = Tournament.from_dict(tournament_data)
                
                # Validate tournament can be paused
                if tournament.status != TournamentStatus.ACTIVE:
                    return {"success": False, "error": f"Cannot pause tournament with status: {tournament.status.value}"}

                # Update tournament status
                tournament.update_status("paused")

                # Update database
                success = self._data_provider.update_tournament(tournament_id, tournament.to_dict())
                if not success:
                    return {"success": False, "error": "Failed to update tournament status"}

                # Update active tournament if this is it
                if self._active_tournament and self._active_tournament.id == tournament_id:
                    self._active_tournament = tournament

                message_bus.emit("tournament_paused", {
                    "tournament_id": tournament_id,
                    "tournament_name": tournament.name
                })

                message_bus.publish(content=f"Paused tournament: {tournament.name}", level=MessageLevel.INFO)

                return {"success": True, "tournament": tournament.to_dict()}

            except Exception as e:
                message_bus.publish(content=f"Error pausing tournament: {str(e)}", level=MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def resume_tournament(self, tournament_id: str) -> Dict[str, Any]:
        """Resume a paused tournament"""
        with self._lock:
            try:
                tournament_data = self._data_provider.get_tournament(tournament_id)
                if not tournament_data:
                    return {"success": False, "error": "Tournament not found"}

                tournament = Tournament.from_dict(tournament_data)
                
                # Validate tournament can be resumed
                if tournament.status != TournamentStatus.PAUSED:
                    return {"success": False, "error": f"Cannot resume tournament with status: {tournament.status.value}"}

                # Update tournament status
                tournament.update_status("active")

                # Update database
                success = self._data_provider.update_tournament(tournament_id, tournament.to_dict())
                if not success:
                    return {"success": False, "error": "Failed to update tournament status"}

                # Update active tournament if this is it
                if self._active_tournament and self._active_tournament.id == tournament_id:
                    self._active_tournament = tournament

                message_bus.emit("tournament_resumed", {
                    "tournament_id": tournament_id,
                    "tournament_name": tournament.name
                })

                message_bus.publish(content=f"Resumed tournament: {tournament.name}", level=MessageLevel.INFO)

                return {"success": True, "tournament": tournament.to_dict()}

            except Exception as e:
                message_bus.publish(content=f"Error resuming tournament: {str(e)}", level=MessageLevel.ERROR)
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
                message_bus.publish(content=f"Error adding participant: {str(e)}", level=MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def get_active_tournament(self) -> Optional[Dict[str, Any]]:
        """Get currently active tournament"""
        with self._lock:
            if self._active_tournament:
                return self._active_tournament.to_dict()
            return None

    def get_all_tournaments(self) -> List[Dict[str, Any]]:
        """Get all tournaments from database"""
        try:
            return self._data_provider.get_all_tournaments()
        except Exception as e:
            message_bus.publish(content=f"Error loading all tournaments: {str(e)}", level=MessageLevel.ERROR)
            return []

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
                message_bus.publish(content=f"Restored active tournament: {self._active_tournament.name}", level=MessageLevel.INFO)

        except Exception as e:
            message_bus.publish(content=f"Error restoring active tournament: {str(e)}", level=MessageLevel.ERROR)

    def complete_tournament(self, tournament_id: str) -> Dict[str, Any]:
        """Complete tournament with statistics finalization"""
        with self._lock:
            try:
                # Get tournament data
                tournament_data = self._data_provider.get_tournament(tournament_id)
                if not tournament_data:
                    return {"success": False, "error": "Tournament not found"}

                tournament = Tournament.from_dict(tournament_data)

                # Validate tournament can be completed
                if tournament.status not in [TournamentStatus.ACTIVE, TournamentStatus.PAUSED]:
                    return {"success": False, "error": f"Cannot complete tournament with status: {tournament.status.value}"}

                # Calculate final statistics
                final_statistics = self._calculate_final_statistics(tournament)

                # Update tournament with completion data
                tournament.update_status("completed")

                # Set completion timestamp
                tournament.activated_to = datetime.now().isoformat()

                # Store completion statistics in config
                config = tournament.config.copy()
                config["completion_statistics"] = final_statistics
                config["completed_at"] = tournament.activated_to
                tournament.config = config

                # Update database
                success = self._data_provider.update_tournament(tournament_id, tournament.to_dict())
                if not success:
                    return {"success": False, "error": "Failed to update tournament in database"}

                # Clear active tournament if this was it
                if self._active_tournament and self._active_tournament.id == tournament_id:
                    self._active_tournament = None

                # Emit completion events
                message_bus.emit("tournament_completed", {
                    "tournament_id": tournament_id,
                    "tournament_name": tournament.name,
                    "final_statistics": final_statistics,
                    "participants": tournament.participants
                })

                # Notify other users via RealtimeBridge
                message_bus.emit("realtime_event", {
                    "event_type": "tournament_completed",
                    "tournament_id": tournament_id,
                    "tournament_name": tournament.name,
                    "team_composition": tournament.teams,
                    "final_statistics": final_statistics
                })

                message_bus.publish(content=f"Completed tournament: {tournament.name}", level=MessageLevel.INFO)

                return {
                    "success": True,
                    "tournament": tournament.to_dict(),
                    "final_statistics": final_statistics
                }

            except Exception as e:
                message_bus.publish(content=f"Error completing tournament: {str(e)}", level=MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def _calculate_final_statistics(self, tournament: Tournament) -> Dict[str, Any]:
        """Calculate final tournament statistics"""
        try:
            # Calculate tournament duration
            duration_info = "Unknown"
            try:
                created_at = tournament.created_at
                completed_at = datetime.now().isoformat()
                if created_at and completed_at:
                    start_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                    duration_seconds = (end_time - start_time).total_seconds()
                    hours = int(duration_seconds // 3600)
                    minutes = int((duration_seconds % 3600) // 60)
                    duration_info = f"{hours}h {minutes}m"
            except Exception as e:
                message_bus.publish(content=f"Error calculating duration: {str(e)}", level=MessageLevel.WARNING)

            statistics = {
                "tournament_summary": {
                    "total_participants": len(tournament.participants),
                    "total_teams": len(tournament.teams),
                    "duration": duration_info,
                    "tournament_type": tournament.config.get("tournament_type", "sc_default"),
                    "completed_at": datetime.now().isoformat()
                },
                "team_standings": [],
                "individual_standings": [],
                "top_performers": {}
            }

            # Calculate team and individual statistics
            participant_stats = {}
            team_stats = {}

            # Initialize team stats
            for team_name, team_members in tournament.teams.items():
                team_stats[team_name] = {
                    "team_name": team_name,
                    "members": team_members,
                    "total_kills": 0,
                    "total_deaths": 0,
                    "kd_ratio": 0.0
                }

            # Get combat statistics for each participant
            tournament_type = tournament.config.get("tournament_type", "sc_default")

            for participant in tournament.participants:
                try:
                    # Get player combat history
                    combat_history = self._data_provider.get_player_combat_history(
                        table_name=tournament_type,
                        username=participant,
                        tournament_id=tournament.id
                    )

                    # Calculate individual stats
                    kills = len([e for e in combat_history if e.get("event_type") == "kill"])
                    deaths = len([e for e in combat_history if e.get("event_type") == "death"])
                    kd_ratio = kills / max(deaths, 1)

                    participant_stats[participant] = {
                        "username": participant,
                        "team": tournament.get_participant_team(participant),
                        "kills": kills,
                        "deaths": deaths,
                        "kd_ratio": round(kd_ratio, 2),
                        "total_events": len(combat_history)
                    }

                    # Add to team stats
                    team_name = tournament.get_participant_team(participant)
                    if team_name and team_name in team_stats:
                        team_stats[team_name]["total_kills"] += kills
                        team_stats[team_name]["total_deaths"] += deaths

                except Exception as e:
                    message_bus.publish(content=f"Error calculating stats for {participant}: {str(e)}", level=MessageLevel.WARNING)
                    # Set default stats if calculation fails
                    participant_stats[participant] = {
                        "username": participant,
                        "team": tournament.get_participant_team(participant),
                        "kills": 0,
                        "deaths": 0,
                        "kd_ratio": 0.0,
                        "total_events": 0
                    }

            # Calculate team KD ratios
            for team_name, team_data in team_stats.items():
                if team_data["total_deaths"] > 0:
                    team_data["kd_ratio"] = round(team_data["total_kills"] / team_data["total_deaths"], 2)
                else:
                    team_data["kd_ratio"] = team_data["total_kills"]

            # Sort standings
            statistics["individual_standings"] = sorted(
                participant_stats.values(),
                key=lambda x: (x["kills"], x["kd_ratio"]),
                reverse=True
            )

            statistics["team_standings"] = sorted(
                team_stats.values(),
                key=lambda x: (x["total_kills"], x["kd_ratio"]),
                reverse=True
            )

            # Determine top performers
            if statistics["individual_standings"]:
                statistics["top_performers"] = {
                    "most_kills": statistics["individual_standings"][0],
                    "best_kd_ratio": max(participant_stats.values(), key=lambda x: x["kd_ratio"]),
                    "winning_team": statistics["team_standings"][0] if statistics["team_standings"] else None
                }

            return statistics

        except Exception as e:
            message_bus.publish(content=f"Error calculating final statistics: {str(e)}", level=MessageLevel.ERROR)
            return {
                "error": "Failed to calculate statistics",
                "tournament_summary": {
                    "total_participants": len(tournament.participants),
                    "total_teams": len(tournament.teams),
                    "completed_at": datetime.now().isoformat()
                }
            }

    def archive_tournament(self, tournament_id: str) -> Dict[str, Any]:
        """Archive completed tournament for long-term storage"""
        with self._lock:
            try:
                tournament_data = self._data_provider.get_tournament(tournament_id)
                if not tournament_data:
                    return {"success": False, "error": "Tournament not found"}

                tournament = Tournament.from_dict(tournament_data)

                # Only archive completed tournaments
                if tournament.status != TournamentStatus.COMPLETED:
                    return {"success": False, "error": f"Cannot archive tournament with status: {tournament.status.value}"}

                # Mark tournament as archived
                config = tournament.config.copy()
                config["archived"] = True
                config["archived_at"] = datetime.now().isoformat()
                tournament.config = config

                # Update database
                success = self._data_provider.update_tournament(tournament_id, tournament.to_dict())
                if not success:
                    return {"success": False, "error": "Failed to archive tournament in database"}

                message_bus.emit("tournament_archived", {
                    "tournament_id": tournament_id,
                    "tournament_name": tournament.name
                })

                message_bus.publish(content=f"Archived tournament: {tournament.name}", level=MessageLevel.INFO)

                return {"success": True, "tournament": tournament.to_dict()}

            except Exception as e:
                message_bus.publish(content=f"Error archiving tournament: {str(e)}", level=MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def cleanup_old_tournaments(self, days_threshold: int = 90) -> Dict[str, Any]:
        """Clean up old completed tournaments based on age threshold"""
        try:
            from datetime import timedelta

            all_tournaments = self._data_provider.get_all_tournaments()
            cleanup_count = 0
            errors = []

            cutoff_date = datetime.now() - timedelta(days=days_threshold)

            for tournament_data in all_tournaments:
                try:
                    # Only process completed tournaments
                    if tournament_data.get("status") != "completed":
                        continue

                    # Check if tournament is old enough for cleanup
                    created_at = tournament_data.get("created_at")
                    if not created_at:
                        continue

                    tournament_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

                    if tournament_date < cutoff_date:
                        # Check if already archived
                        config = tournament_data.get("config", {})
                        if not config.get("archived", False):
                            # Archive the tournament instead of deleting
                            result = self.archive_tournament(tournament_data["id"])
                            if result.get("success"):
                                cleanup_count += 1
                            else:
                                errors.append(f"Failed to archive {tournament_data.get('name', 'unknown')}: {result.get('error')}")

                except Exception as e:
                    errors.append(f"Error processing tournament {tournament_data.get('id', 'unknown')}: {str(e)}")

            message_bus.publish(content=f"Tournament cleanup completed: {cleanup_count} archived", level=MessageLevel.INFO)

            return {
                "success": True,
                "archived_count": cleanup_count,
                "errors": errors,
                "threshold_days": days_threshold
            }

        except Exception as e:
            message_bus.publish(content=f"Error during tournament cleanup: {str(e)}", level=MessageLevel.ERROR)
            return {"success": False, "error": str(e)}

    def get_archived_tournaments(self) -> List[Dict[str, Any]]:
        """Get all archived tournaments"""
        try:
            all_tournaments = self._data_provider.get_all_tournaments()
            archived = []

            for tournament_data in all_tournaments:
                config = tournament_data.get("config", {})
                if config.get("archived", False):
                    archived.append(tournament_data)

            return archived

        except Exception as e:
            message_bus.publish(content=f"Error loading archived tournaments: {str(e)}", level=MessageLevel.ERROR)
            return []

    def delete_tournament(self, tournament_id: str, force: bool = False) -> Dict[str, Any]:
        """Delete tournament (requires force flag for safety)"""
        with self._lock:
            try:
                if not force:
                    return {"success": False, "error": "Tournament deletion requires force=True flag for safety"}

                tournament_data = self._data_provider.get_tournament(tournament_id)
                if not tournament_data:
                    return {"success": False, "error": "Tournament not found"}

                tournament = Tournament.from_dict(tournament_data)

                # Prevent deletion of active tournaments
                if tournament.status == TournamentStatus.ACTIVE:
                    return {"success": False, "error": "Cannot delete active tournament"}

                # Clear active tournament if this is it
                if self._active_tournament and self._active_tournament.id == tournament_id:
                    self._active_tournament = None

                # Delete from database
                success = self._data_provider.delete_tournament(tournament_id)
                if not success:
                    return {"success": False, "error": "Failed to delete tournament from database"}

                message_bus.emit("tournament_deleted", {
                    "tournament_id": tournament_id,
                    "tournament_name": tournament.name
                })

                message_bus.publish(content=f"Deleted tournament: {tournament.name}", level=MessageLevel.WARNING)

                return {"success": True, "tournament_id": tournament_id}

            except Exception as e:
                message_bus.publish(content=f"Error deleting tournament: {str(e)}", level=MessageLevel.ERROR)
                return {"success": False, "error": str(e)}

    def get_tournament_corpses(self, tournament_id: str) -> List[Dict[str, Any]]:
        """Get all corpses for a tournament"""
        try:
            return self._data_provider.get_tournament_corpses(tournament_id)
        except Exception as e:
            message_bus.publish(content=f"Error getting tournament corpses: {str(e)}", level=MessageLevel.ERROR)
            return []

    def delete_corpse_record(self, corpse_id: str) -> Dict[str, Any]:
        """Delete a corpse record from tournament"""
        try:
            success = self._data_provider.delete_tournament_corpse(corpse_id)
            if success:
                message_bus.emit("corpse_record_deleted", {
                    "corpse_id": corpse_id
                })
                message_bus.publish(content="Registro de baja eliminado", level=MessageLevel.INFO)
                return {"success": True}
            else:
                return {"success": False, "error": "Failed to delete corpse record"}
        except Exception as e:
            message_bus.publish(content=f"Error deleting corpse record: {str(e)}", level=MessageLevel.ERROR)
            return {"success": False, "error": str(e)}

    def delete_combat_event(self, table_name: str, event_id: str) -> Dict[str, Any]:
        """Remove combat event from tournament by setting tournament_id to NULL"""
        try:
            # Use existing API method to set tournament_id to None (NULL)
            success = self._data_provider.tag_combat_event_with_tournament(table_name, event_id, None)
            if success:
                message_bus.emit("combat_event_deleted", {
                    "table_name": table_name,
                    "event_id": event_id
                })
                message_bus.publish(content="Evento de combate desvinculado del torneo", level=MessageLevel.INFO)
                return {"success": True}
            else:
                return {"success": False, "error": "Failed to unlink combat event"}
        except Exception as e:
            message_bus.publish(content=f"Error unlinking combat event: {str(e)}", level=MessageLevel.ERROR)
            return {"success": False, "error": str(e)}

    def recalculate_tournament_statistics(self, tournament_id: str) -> Dict[str, Any]:
        """Recalculate tournament statistics after data changes"""
        try:
            tournament_data = self._data_provider.get_tournament(tournament_id)
            if not tournament_data:
                return {"success": False, "error": "Tournament not found"}

            tournament = Tournament.from_dict(tournament_data)
            
            # Recalculate statistics using the same method as completion
            updated_statistics = self._calculate_final_statistics(tournament)
            
            # Update tournament config with new statistics
            config = tournament.config.copy()
            config["current_statistics"] = updated_statistics
            config["last_recalculated"] = datetime.now().isoformat()
            tournament.config = config

            # Update database
            success = self._data_provider.update_tournament(tournament_id, tournament.to_dict())
            if success:
                message_bus.emit("tournament_statistics_updated", {
                    "tournament_id": tournament_id,
                    "statistics": updated_statistics
                })
                message_bus.publish(content="Estadísticas del torneo recalculadas", level=MessageLevel.INFO)
                return {"success": True, "statistics": updated_statistics}
            else:
                return {"success": False, "error": "Failed to update tournament statistics"}
                
        except Exception as e:
            message_bus.publish(content=f"Error recalculating tournament statistics: {str(e)}", level=MessageLevel.ERROR)
            return {"success": False, "error": str(e)}