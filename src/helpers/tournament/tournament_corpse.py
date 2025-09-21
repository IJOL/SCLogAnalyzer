import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from helpers.core.message_bus import message_bus, MessageLevel

class TournamentCorpse:
    """Tournament corpse model with deduplication logic"""

    def __init__(self, corpse_data: Dict[str, Any]):
        """Initialize corpse from data dictionary"""
        self.id = corpse_data.get("id", str(uuid.uuid4()))
        self.tournament_id = corpse_data["tournament_id"]
        self.participant_name = corpse_data["participant_name"]
        self.corpse_hash = corpse_data.get("corpse_hash", self._generate_hash(corpse_data))
        self.detected_by = corpse_data["detected_by"]
        self.organizer_confirmed = corpse_data.get("organizer_confirmed", False)
        self.detected_at = corpse_data.get("detected_at", datetime.now().isoformat())
        self.location_data = corpse_data.get("location_data", {})

        self._validate()

    def _validate(self):
        """Validate corpse data"""
        if not self.tournament_id:
            raise ValueError("Tournament ID cannot be empty")

        if not self.participant_name or not self.participant_name.strip():
            raise ValueError("Participant name cannot be empty")

        if not self.detected_by or not self.detected_by.strip():
            raise ValueError("Detected by cannot be empty")

    def _generate_hash(self, corpse_data: Dict[str, Any]) -> str:
        """Generate unique hash for corpse deduplication"""
        hash_components = [
            self.tournament_id,
            self.participant_name,
            str(corpse_data.get("location_data", {})),
            str(corpse_data.get("timestamp", self.detected_at))
        ]

        hash_string = "|".join(hash_components)
        return hashlib.md5(hash_string.encode()).hexdigest()

    @staticmethod
    def generate_hash_from_data(tournament_id: str, participant_name: str,
                               location_data: Dict, timestamp: str = None) -> str:
        """Generate hash from raw data for duplicate checking"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        hash_components = [
            tournament_id,
            participant_name,
            str(location_data),
            str(timestamp)
        ]

        hash_string = "|".join(hash_components)
        return hashlib.md5(hash_string.encode()).hexdigest()

    def confirm_by_organizer(self, organizer_username: str) -> bool:
        """Mark corpse as confirmed by tournament organizer"""
        try:
            self.organizer_confirmed = True

            message_bus.emit("corpse_confirmed", {
                "tournament_id": self.tournament_id,
                "corpse_id": self.id,
                "participant_name": self.participant_name,
                "confirmed_by": organizer_username
            })

            message_bus.publish(f"Corpse of {self.participant_name} confirmed by organizer", MessageLevel.INFO)
            return True

        except Exception as e:
            message_bus.publish(f"Error confirming corpse: {str(e)}", MessageLevel.ERROR)
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert corpse to dictionary for storage"""
        return {
            "id": self.id,
            "tournament_id": self.tournament_id,
            "participant_name": self.participant_name,
            "corpse_hash": self.corpse_hash,
            "detected_by": self.detected_by,
            "organizer_confirmed": self.organizer_confirmed,
            "detected_at": self.detected_at,
            "location_data": self.location_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TournamentCorpse':
        """Create corpse from dictionary"""
        return cls(data)