import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from helpers.core.message_bus import message_bus, MessageLevel

class TournamentStatus(Enum):
    """Tournament status enumeration"""
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"

class Tournament:
    """Tournament model with validation and state management"""

    def __init__(self, tournament_data: Dict[str, Any]):
        """Initialize tournament from data dictionary"""
        self.id = tournament_data.get("id", str(uuid.uuid4()))
        self.name = tournament_data["name"]
        self.participants = tournament_data.get("participants", [])
        self.teams = tournament_data.get("teams", {})
        self.status = TournamentStatus(tournament_data.get("status", "created"))
        self.created_at = tournament_data.get("created_at", datetime.now().isoformat())
        self.created_by = tournament_data["created_by"]
        self.config = tournament_data.get("config", {})

        self._validate()

    def _validate(self):
        """Validate tournament data"""
        if not self.name or not self.name.strip():
            raise ValueError("Tournament name cannot be empty")

        if not self.created_by or not self.created_by.strip():
            raise ValueError("Tournament creator cannot be empty")

        if not isinstance(self.participants, list):
            raise ValueError("Participants must be a list")

        if not isinstance(self.teams, dict):
            raise ValueError("Teams must be a dictionary")

    def add_participant(self, username: str, team_name: str) -> bool:
        """Add participant to tournament and team"""
        try:
            if username in self.participants:
                message_bus.publish(
                    content=f"Participant {username} already in tournament",
                    level=MessageLevel.WARNING
                )
                return False

            self.participants.append(username)

            if team_name not in self.teams:
                self.teams[team_name] = []

            if username not in self.teams[team_name]:
                self.teams[team_name].append(username)

            message_bus.publish(
                content=f"Added {username} to team {team_name}",
                level=MessageLevel.INFO
            )
            return True

        except Exception as e:
            message_bus.publish(content=f"Error adding participant: {str(e)}", level=MessageLevel.ERROR)
            return False

    def remove_participant(self, username: str) -> bool:
        """Remove participant from tournament and all teams"""
        try:
            if username not in self.participants:
                return False

            self.participants.remove(username)

            # Remove from all teams
            for team_name, team_members in self.teams.items():
                if username in team_members:
                    team_members.remove(username)

            # Clean up empty teams
            self.teams = {name: members for name, members in self.teams.items() if members}

            message_bus.publish(content=f"Removed {username} from tournament", level=MessageLevel.INFO)
            return True

        except Exception as e:
            message_bus.publish(content=f"Error removing participant: {str(e)}", level=MessageLevel.ERROR)
            return False

    def is_participant(self, username: str) -> bool:
        """Check if user is tournament participant"""
        return username in self.participants

    def get_participant_team(self, username: str) -> Optional[str]:
        """Get team name for participant"""
        for team_name, members in self.teams.items():
            if username in members:
                return team_name
        return None

    def update_status(self, new_status: str) -> bool:
        """Update tournament status with validation"""
        try:
            old_status = self.status
            self.status = TournamentStatus(new_status)

            message_bus.emit("tournament_status_changed", {
                "tournament_id": self.id,
                "old_status": old_status.value,
                "new_status": new_status
            })

            return True

        except ValueError as e:
            message_bus.publish(content=f"Invalid tournament status: {new_status}", level=MessageLevel.ERROR)
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert tournament to dictionary for storage"""
        return {
            "id": self.id,
            "name": self.name,
            "participants": self.participants,
            "teams": self.teams,
            "status": self.status.value,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "config": self.config
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tournament':
        """Create tournament from dictionary"""
        return cls(data)