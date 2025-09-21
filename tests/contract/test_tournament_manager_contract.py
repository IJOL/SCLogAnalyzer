import unittest
from src.helpers.tournament.tournament_manager import TournamentManager

class TestTournamentManagerContract(unittest.TestCase):
    """Contract tests for TournamentManager - MUST FAIL initially"""

    def setUp(self):
        self.tournament_manager = TournamentManager()

    def test_create_tournament_contract(self):
        """Contract: create_tournament must return tournament_id when successful"""
        tournament_data = {
            "name": "Test Tournament",
            "participants": [],
            "teams": {},
            "created_by": "test_user"
        }

        result = self.tournament_manager.create_tournament(tournament_data)

        # Contract assertions
        self.assertIsNotNone(result)
        self.assertIn("tournament_id", result)
        self.assertIn("success", result)
        self.assertTrue(result["success"])

    def test_add_participant_contract(self):
        """Contract: add_participant must update tournament participants"""
        tournament_id = "test-tournament-id"
        participant_data = {
            "username": "test_participant",
            "team": "team_alpha"
        }

        result = self.tournament_manager.add_participant(tournament_id, participant_data)

        # Contract assertions
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

    def test_get_active_tournament_contract(self):
        """Contract: get_active_tournament must return current tournament or None"""
        result = self.tournament_manager.get_active_tournament()

        # Contract assertions - can be None or dict
        self.assertTrue(result is None or isinstance(result, dict))

    def test_tournament_status_validation(self):
        """Contract: tournament status must be valid enum value"""
        valid_statuses = ["created", "active", "paused", "completed"]

        for status in valid_statuses:
            result = self.tournament_manager.validate_status(status)
            self.assertTrue(result)

if __name__ == "__main__":
    unittest.main()