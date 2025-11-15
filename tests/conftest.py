"""Shared pytest fixtures and configuration"""
import pytest
import os
import sys
import json
import tempfile
from unittest.mock import Mock, MagicMock

# Add src to path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing"""
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, 'test_config.json')

    # Default test configuration
    test_config = {
        "log_file_path": "/path/to/test/game.log",
        "discord_webhook_url": "https://discord.com/api/webhooks/test",
        "technical_webhook_url": "https://discord.com/api/webhooks/tech",
        "datasource": "supabase",
        "important_players": "testplayer1, testplayer2",
        "regex_patterns": {
            "player_death": r"test_death_pattern",
            "actor_death": r"test_actor_pattern",
            "connection": r"test_connection_pattern"
        },
        "messages": {
            "player_death": "Player {killer} killed {victim}",
            "actor_death": "Actor killed"
        },
        "auto_environment_detection": False,
        "live_log_path": "",
        "ptu_log_path": "",
        "rate_limit_timeout": 300,
        "rate_limit_max_duplicates": 1,
        "process_once": False,
        "use_discord": True
    }

    with open(config_path, 'w') as f:
        json.dump(test_config, f, indent=4)

    yield config_path

    # Cleanup
    if os.path.exists(config_path):
        os.remove(config_path)
    os.rmdir(temp_dir)


@pytest.fixture
def sample_config_dict():
    """Return a sample configuration dictionary"""
    return {
        "log_file_path": "/path/to/game.log",
        "discord_webhook_url": "https://discord.com/api/webhooks/test",
        "datasource": "googlesheets",
        "important_players": "player1, player2, player3",
        "regex_patterns": {
            "player_death": r"killed\s+(\w+)",
            "vehicle_destruction": r"vehicle\s+destroyed"
        },
        "auto_environment_detection": False
    }


@pytest.fixture
def mock_config_manager(sample_config_dict):
    """Create a mock ConfigManager for testing"""
    mock_manager = Mock()
    mock_manager._config = sample_config_dict.copy()

    def get(key, default=None):
        keys = key.split('.')
        value = mock_manager._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(key, value):
        keys = key.split('.')
        config = mock_manager._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        return True

    mock_manager.get = Mock(side_effect=get)
    mock_manager.set = Mock(side_effect=set)
    mock_manager.save_config = Mock()
    mock_manager.get_all = Mock(return_value=sample_config_dict.copy())

    return mock_manager


@pytest.fixture
def mock_message_bus():
    """Create a mock MessageBus for testing"""
    mock_bus = Mock()
    mock_bus.publish = Mock()
    mock_bus.subscribe = Mock()
    mock_bus.unsubscribe = Mock()
    mock_bus.emit = Mock()
    mock_bus.on = Mock(return_value="subscription_id")
    mock_bus.off = Mock()
    mock_bus.get_history = Mock(return_value=[])
    mock_bus.is_debug_mode = Mock(return_value=False)
    mock_bus.set_debug_mode = Mock()

    return mock_bus


@pytest.fixture
def sample_log_lines():
    """Return sample log lines for testing log analysis"""
    return [
        '<2024-01-15T10:30:45.123Z> [Notice] <Actor Death> CActor::Kill: \'Victim123\' [12345] in zone \'Stanton\' killed by \'Killer456\' [67890] using \'KLWE_LaserRepeater_S1\' [Class unknown] with damage type \'Energy\'',
        '<2024-01-15T10:31:20.456Z> [Notice] <Vehicle Destroyed> Vehicle [890] destroyed in zone \'Stanton\' by \'Player789\'',
        '<2024-01-15T10:32:10.789Z> [Notice] <Connection> Player \'NewPlayer\' connected to shard \'shard-001\'',
        '<2024-01-15T10:33:05.012Z> [Notice] <Actor Death> CActor::Kill: \'NPC_Guard\' [11111] in zone \'ArcCorp\' killed by \'Hunter999\' [22222] using \'KSAR_BallisticRifle\' [Class unknown] with damage type \'Ballistic\''
    ]


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client"""
    mock_client = Mock()

    # Mock table operations
    mock_table = Mock()
    mock_table.insert = Mock(return_value=mock_table)
    mock_table.select = Mock(return_value=mock_table)
    mock_table.update = Mock(return_value=mock_table)
    mock_table.delete = Mock(return_value=mock_table)
    mock_table.eq = Mock(return_value=mock_table)
    mock_table.execute = Mock(return_value=Mock(data=[]))

    mock_client.table = Mock(return_value=mock_table)
    mock_client.auth = Mock()
    mock_client.storage = Mock()

    return mock_client


@pytest.fixture
def mock_data_provider():
    """Create a mock data provider"""
    mock_provider = Mock()
    mock_provider.is_connected = Mock(return_value=True)
    mock_provider.fetch_config = Mock(return_value={})
    mock_provider.upload_data = Mock(return_value=True)
    mock_provider.execute_query = Mock(return_value=[])

    return mock_provider


@pytest.fixture
def sample_death_event():
    """Return a sample death event dictionary"""
    return {
        'timestamp': '2024-01-15T10:30:45.123Z',
        'killer': 'Killer456',
        'victim': 'Victim123',
        'weapon': 'KLWE_LaserRepeater_S1',
        'damage_type': 'Energy',
        'zone': 'Stanton',
        'killer_geid': '67890',
        'victim_geid': '12345'
    }


@pytest.fixture
def sample_tournament_data():
    """Return sample tournament data"""
    return {
        'id': 'test-tournament-001',
        'name': 'Test Tournament',
        'status': 'active',
        'created_at': '2024-01-15T10:00:00Z',
        'participants': [
            {'name': 'Player1', 'team': 'TeamAlpha'},
            {'name': 'Player2', 'team': 'TeamBeta'}
        ],
        'teams': {
            'TeamAlpha': ['Player1'],
            'TeamBeta': ['Player2']
        }
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test to ensure isolation"""
    # This fixture runs automatically before each test
    import helpers.core.config_utils as config_utils_module
    import helpers.core.message_bus as message_bus_module

    # Store original singleton instances
    original_config_manager = getattr(config_utils_module, '_config_manager_instance', None)
    original_message_bus = getattr(message_bus_module, 'message_bus', None)

    # Reset to None before test
    if hasattr(config_utils_module, '_config_manager_instance'):
        config_utils_module._config_manager_instance = None

    yield

    # Restore original instances after test (optional, for safety)
    # This ensures that if any global state was set up initially, it's restored
    # However, for most tests we want fresh instances, so this is commented out
    # config_utils_module._config_manager_instance = original_config_manager


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing"""
    temp_dir = tempfile.mkdtemp()
    log_path = os.path.join(temp_dir, 'Game.log')

    # Create an empty log file
    with open(log_path, 'w') as f:
        f.write("")

    yield log_path

    # Cleanup
    if os.path.exists(log_path):
        os.remove(log_path)
    os.rmdir(temp_dir)


@pytest.fixture
def sample_regex_patterns():
    """Return sample regex patterns for testing"""
    return {
        "player_death": r"<(?P<timestamp>.*?)> \[Notice\] <Actor Death> CActor::Kill: '(?P<victim>\w+)' \[\d+\] in zone '(?P<zone>\w+)' killed by '(?P<killer>\w+)' \[\d+\] using '(?P<weapon>[\w_]+)' \[Class unknown\] with damage type '(?P<damage_type>\w+)'",
        "vehicle_destruction": r"<(?P<timestamp>.*?)> \[Notice\] <Vehicle Destroyed> Vehicle \[(?P<vehicle_id>\d+)\] destroyed in zone '(?P<zone>\w+)' by '(?P<destroyer>\w+)'",
        "connection": r"<(?P<timestamp>.*?)> \[Notice\] <Connection> Player '(?P<player>\w+)' connected to shard '(?P<shard>[\w-]+)'"
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "gui: marks tests that require GUI components"
    )


# Helper functions for tests
def assert_message_published(mock_bus, content_substring=None, level=None, call_count=None):
    """Helper to assert that a message was published to the message bus"""
    assert mock_bus.publish.called, "Message bus publish was not called"

    if call_count is not None:
        assert mock_bus.publish.call_count == call_count, \
            f"Expected {call_count} calls, got {mock_bus.publish.call_count}"

    if content_substring or level:
        calls = mock_bus.publish.call_args_list
        for call in calls:
            kwargs = call[1] if len(call) > 1 else {}

            if content_substring and content_substring in kwargs.get('content', ''):
                if level is None or kwargs.get('level') == level:
                    return True

        raise AssertionError(
            f"No message found with content '{content_substring}' "
            f"and level '{level}' in {len(calls)} calls"
        )


def create_mock_message(content, timestamp=None, level=None, pattern_name=None):
    """Helper to create a mock Message object"""
    from helpers.core.message_bus import Message, MessageLevel

    msg = Mock(spec=Message)
    msg.content = content
    msg.timestamp = timestamp or "2024-01-15T10:00:00Z"
    msg.level = level or MessageLevel.INFO
    msg.pattern_name = pattern_name
    msg.metadata = {}
    msg.get_formatted_message = Mock(return_value=f"{msg.timestamp} - {content}")

    return msg
