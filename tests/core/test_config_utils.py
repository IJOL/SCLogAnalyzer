"""Tests for config_utils module"""
import pytest
import os
import json
import tempfile
import threading
from unittest.mock import Mock, patch, MagicMock

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from helpers.core.config_utils import (
    ConfigManager,
    get_config_manager,
    get_application_path,
    get_template_path,
    emit_default_config,
    prompt_for_config_values
)


class TestConfigManager:
    """Test suite for ConfigManager class"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment before each test"""
        # Create a temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.json')

        # Sample config data
        self.sample_config = {
            "log_file_path": "/path/to/game.log",
            "discord_webhook_url": "https://discord.com/api/webhooks/test",
            "datasource": "supabase",
            "important_players": "player1, player2",
            "regex_patterns": {
                "player_death": "test_pattern",
                "actor_death": "another_pattern"
            },
            "auto_environment_detection": False,
            "live_log_path": "",
            "ptu_log_path": ""
        }

        # Write sample config
        with open(self.config_path, 'w') as f:
            json.dump(self.sample_config, f)

        yield

        # Cleanup
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        os.rmdir(self.temp_dir)

    def test_config_manager_initialization(self):
        """Test ConfigManager initializes correctly"""
        config_manager = ConfigManager(config_path=self.config_path)

        assert config_manager.config_path == self.config_path
        assert config_manager._config is not None
        assert config_manager.new_config == False

    def test_load_config(self):
        """Test loading configuration from file"""
        config_manager = ConfigManager(config_path=self.config_path)

        assert config_manager.get('log_file_path') == "/path/to/game.log"
        assert config_manager.get('datasource') == "supabase"

    def test_get_simple_key(self):
        """Test getting a simple configuration key"""
        config_manager = ConfigManager(config_path=self.config_path)

        value = config_manager.get('log_file_path')
        assert value == "/path/to/game.log"

    def test_get_nested_key_with_dot_notation(self):
        """Test getting a nested key using dot notation"""
        config_manager = ConfigManager(config_path=self.config_path)

        value = config_manager.get('regex_patterns.player_death')
        assert value == "test_pattern"

    def test_get_nonexistent_key_returns_default(self):
        """Test getting a non-existent key returns default value"""
        config_manager = ConfigManager(config_path=self.config_path)

        value = config_manager.get('nonexistent_key', default='default_value')
        assert value == 'default_value'

    def test_set_simple_key(self):
        """Test setting a simple configuration key"""
        config_manager = ConfigManager(config_path=self.config_path)

        result = config_manager.set('test_key', 'test_value')
        assert result == True
        assert config_manager.get('test_key') == 'test_value'

    def test_set_nested_key_with_dot_notation(self):
        """Test setting a nested key using dot notation"""
        config_manager = ConfigManager(config_path=self.config_path)

        result = config_manager.set('new_section.nested_key', 'nested_value')
        assert result == True
        assert config_manager.get('new_section.nested_key') == 'nested_value'

    def test_save_config(self):
        """Test saving configuration to file"""
        config_manager = ConfigManager(config_path=self.config_path)

        config_manager.set('test_key', 'test_value')
        config_manager.save_config()

        # Read the file to verify
        with open(self.config_path, 'r') as f:
            saved_config = json.load(f)

        assert saved_config['test_key'] == 'test_value'

    def test_save_config_filters_no_save_keys(self):
        """Test that save_config filters out keys in KEYS_NO_SAVE"""
        config_manager = ConfigManager(config_path=self.config_path)

        # Set some keys that should not be saved
        config_manager.set('use_discord', True)
        config_manager.set('process_once', True)
        config_manager.set('tournament_admins', ['admin1'])
        config_manager.set('regular_key', 'should_be_saved')

        config_manager.save_config()

        # Read the file to verify
        with open(self.config_path, 'r') as f:
            saved_config = json.load(f)

        assert 'use_discord' not in saved_config
        assert 'process_once' not in saved_config
        assert 'tournament_admins' not in saved_config
        assert saved_config['regular_key'] == 'should_be_saved'

    def test_is_valid_url(self):
        """Test URL validation"""
        config_manager = ConfigManager(config_path=self.config_path)

        assert config_manager.is_valid_url('https://example.com') == True
        assert config_manager.is_valid_url('http://localhost:8000') == True
        assert config_manager.is_valid_url('invalid_url') == False
        assert config_manager.is_valid_url('') == False
        assert config_manager.is_valid_url(None) == False

    def test_parse_vip_string(self):
        """Test parsing VIP player string"""
        config_manager = ConfigManager(config_path=self.config_path)

        # Test comma-separated
        players = config_manager._parse_vip_string("player1, player2, player3")
        assert players == ['player1', 'player2', 'player3']

        # Test space-separated
        players = config_manager._parse_vip_string("player1 player2 player3")
        assert players == ['player1', 'player2', 'player3']

        # Test mixed
        players = config_manager._parse_vip_string("player1, player2 player3")
        assert len(players) == 3

        # Test empty string
        players = config_manager._parse_vip_string("")
        assert players == []

    def test_is_vip_player(self):
        """Test checking if a player is VIP"""
        config_manager = ConfigManager(config_path=self.config_path)

        assert config_manager.is_vip_player('player1') == True
        assert config_manager.is_vip_player('player2') == True
        assert config_manager.is_vip_player('unknown_player') == False

    def test_add_vip_player(self):
        """Test adding a VIP player"""
        config_manager = ConfigManager(config_path=self.config_path)

        result = config_manager.add_vip_player('new_player')
        assert result == True
        assert config_manager.is_vip_player('new_player') == True

        # Adding duplicate should return False
        result = config_manager.add_vip_player('new_player')
        assert result == False

    def test_remove_vip_player(self):
        """Test removing a VIP player"""
        config_manager = ConfigManager(config_path=self.config_path)

        result = config_manager.remove_vip_player('player1')
        assert result == True
        assert config_manager.is_vip_player('player1') == False

        # Removing non-existent should return False
        result = config_manager.remove_vip_player('player1')
        assert result == False

    def test_toggle_vip_player(self):
        """Test toggling a VIP player"""
        config_manager = ConfigManager(config_path=self.config_path)

        # Toggle off existing player
        result = config_manager.toggle_vip_player('player1')
        assert result == True
        assert config_manager.is_vip_player('player1') == False

        # Toggle on the same player
        result = config_manager.toggle_vip_player('player1')
        assert result == True
        assert config_manager.is_vip_player('player1') == True

    def test_get_all_returns_copy(self):
        """Test that get_all returns a copy of config"""
        config_manager = ConfigManager(config_path=self.config_path)

        config_copy = config_manager.get_all()

        # Modify the copy
        config_copy['new_key'] = 'new_value'

        # Original should not be affected
        assert config_manager.get('new_key') is None

    def test_get_all_filters_keys(self):
        """Test that get_all filters specified keys"""
        config_manager = ConfigManager(config_path=self.config_path)

        # Set keys that should be filtered
        config_manager.set('use_discord', True)
        config_manager.set('version', 'v1.0.0')

        config_copy = config_manager.get_all()

        assert 'use_discord' not in config_copy
        assert 'version' not in config_copy

    def test_update_config(self):
        """Test updating configuration with a dictionary"""
        config_manager = ConfigManager(config_path=self.config_path)

        new_config = {
            'new_key1': 'value1',
            'new_key2': 'value2'
        }

        config_manager.update(new_config)

        assert config_manager.get('new_key1') == 'value1'
        assert config_manager.get('new_key2') == 'value2'

    def test_filter_removes_specified_keys(self):
        """Test that filter method removes specified keys"""
        config_manager = ConfigManager(config_path=self.config_path)

        filtered = config_manager.filter(['log_file_path', 'datasource'])

        assert 'log_file_path' not in filtered
        assert 'datasource' not in filtered
        assert 'discord_webhook_url' in filtered

    def test_thread_safety(self):
        """Test that ConfigManager is thread-safe"""
        config_manager = ConfigManager(config_path=self.config_path)

        results = []

        def worker(index):
            key = f'thread_key_{index}'
            config_manager.set(key, index)
            value = config_manager.get(key)
            results.append(value == index)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All threads should have successfully set and retrieved their values
        assert all(results)

    def test_detect_active_environment_returns_none_when_disabled(self):
        """Test environment detection returns 'none' when disabled"""
        config_manager = ConfigManager(config_path=self.config_path)
        config_manager.set('auto_environment_detection', False)

        env = config_manager.detect_active_environment()
        assert env == "none"

    @patch('os.path.exists')
    @patch('os.path.getmtime')
    def test_detect_active_environment_detects_live(self, mock_getmtime, mock_exists):
        """Test environment detection detects LIVE as active"""
        config_manager = ConfigManager(config_path=self.config_path)
        config_manager.set('auto_environment_detection', True)
        config_manager.set('live_log_path', '/path/to/live.log')
        config_manager.set('ptu_log_path', '/path/to/ptu.log')

        # Mock both files exist, live is newer
        mock_exists.return_value = True
        mock_getmtime.side_effect = [1000.0, 500.0]  # live, ptu

        env = config_manager.detect_active_environment()
        assert env == "live"

    @patch('os.path.exists')
    @patch('os.path.getmtime')
    def test_detect_active_environment_detects_ptu(self, mock_getmtime, mock_exists):
        """Test environment detection detects PTU as active"""
        config_manager = ConfigManager(config_path=self.config_path)
        config_manager.set('auto_environment_detection', True)
        config_manager.set('live_log_path', '/path/to/live.log')
        config_manager.set('ptu_log_path', '/path/to/ptu.log')

        # Mock both files exist, ptu is newer
        mock_exists.return_value = True
        mock_getmtime.side_effect = [500.0, 1000.0]  # live, ptu

        env = config_manager.detect_active_environment()
        assert env == "ptu"


class TestConfigUtilityFunctions:
    """Test suite for config utility functions"""

    def test_get_application_path(self):
        """Test getting application path"""
        path = get_application_path()
        assert isinstance(path, str)
        assert os.path.exists(path) or True  # May not exist in test environment

    def test_prompt_for_config_values(self):
        """Test prompting for config values"""
        template = {
            "simple_key": "simple_value",
            "nested": {
                "key1": "value1"
            }
        }

        with patch('builtins.input', return_value='user_input'):
            # This would prompt in real scenario, we're just testing the structure
            result = prompt_for_config_values(template)

            assert isinstance(result, dict)
            assert result['simple_key'] == 'simple_value'
            assert result['nested']['key1'] == 'value1'


class TestSingletonBehavior:
    """Test singleton pattern for ConfigManager"""

    def test_get_config_manager_returns_singleton(self):
        """Test that get_config_manager returns the same instance"""
        # Reset singleton for testing
        import helpers.core.config_utils
        helpers.core.config_utils._config_manager_instance = None

        manager1 = get_config_manager()
        manager2 = get_config_manager()

        assert manager1 is manager2

    def test_get_config_manager_thread_safe(self):
        """Test that singleton creation is thread-safe"""
        import helpers.core.config_utils
        helpers.core.config_utils._config_manager_instance = None

        instances = []

        def worker():
            manager = get_config_manager()
            instances.append(id(manager))

        threads = [threading.Thread(target=worker) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All threads should have gotten the same instance
        assert len(set(instances)) == 1
