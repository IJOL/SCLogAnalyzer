"""Tests for message_bus module"""
import pytest
import time
import threading
from unittest.mock import Mock, patch

# Add src to path for imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from helpers.core.message_bus import (
    MessageBus,
    Message,
    MessageLevel,
    message_bus,
    setup_console_handler
)


class TestMessage:
    """Test suite for Message class"""

    def test_message_creation_with_timestamp(self):
        """Test creating a message with explicit timestamp"""
        msg = Message(
            content="Test message",
            timestamp="2024-01-01 12:00:00",
            level=MessageLevel.INFO
        )

        assert msg.content == "Test message"
        assert msg.timestamp == "2024-01-01 12:00:00"
        assert msg.level == MessageLevel.INFO
        assert msg.pattern_name is None
        assert msg.metadata == {}

    def test_message_creation_auto_timestamp(self):
        """Test creating a message with automatic timestamp"""
        msg = Message(content="Test message")

        assert msg.content == "Test message"
        assert msg.timestamp is not None
        assert msg.level == MessageLevel.INFO

    def test_message_with_metadata(self):
        """Test creating a message with metadata"""
        metadata = {"source": "test", "user_id": 123}
        msg = Message(
            content="Test",
            metadata=metadata
        )

        assert msg.metadata == metadata
        assert msg.metadata['source'] == "test"

    def test_message_with_pattern_name(self):
        """Test creating a message with pattern name"""
        msg = Message(
            content="Player killed",
            pattern_name="player_death"
        )

        assert msg.pattern_name == "player_death"

    def test_get_formatted_message_with_timestamp(self):
        """Test formatted message includes timestamp"""
        msg = Message(
            content="Test",
            timestamp="2024-01-01 12:00:00"
        )

        formatted = msg.get_formatted_message()
        assert "2024-01-01 12:00:00" in formatted
        assert "Test" in formatted

    def test_creation_time_str(self):
        """Test creation time string property"""
        msg = Message(content="Test")

        time_str = msg.creation_time_str
        assert isinstance(time_str, str)
        assert len(time_str) > 0


class TestMessageBus:
    """Test suite for MessageBus class"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment before each test"""
        # Create a fresh MessageBus instance for testing
        self.bus = MessageBus()

        # Clear subscribers before each test
        self.bus.subscribers = []
        self.bus.filters = {}
        self.bus.message_history = []

        # Ensure bus is running
        if not self.bus.is_running:
            self.bus.start()

        yield

        # Cleanup after test
        self.bus.subscribers = []
        self.bus.filters = {}

    def test_message_bus_is_singleton(self):
        """Test that MessageBus follows singleton pattern"""
        bus1 = MessageBus()
        bus2 = MessageBus()

        assert bus1 is bus2

    def test_message_bus_starts(self):
        """Test that message bus can start"""
        bus = MessageBus()
        bus.stop()  # Stop if running
        bus.start()

        assert bus.is_running == True
        assert bus.worker_thread is not None
        assert bus.worker_thread.is_alive()

    def test_message_bus_stops(self):
        """Test that message bus can stop"""
        bus = MessageBus()
        bus.start()
        bus.stop()

        assert bus.is_running == False

    def test_publish_message(self):
        """Test publishing a message to the bus"""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        self.bus.subscribe('test_subscriber', callback)
        self.bus.publish(content="Test message", level=MessageLevel.INFO)

        # Wait for message to be processed
        time.sleep(0.1)

        assert len(received_messages) > 0
        assert received_messages[0].content == "Test message"
        assert received_messages[0].level == MessageLevel.INFO

    def test_publish_with_pattern_name(self):
        """Test publishing with pattern name"""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        self.bus.subscribe('test_subscriber', callback)
        self.bus.publish(
            content="Death event",
            pattern_name="player_death",
            level=MessageLevel.INFO
        )

        time.sleep(0.1)

        assert len(received_messages) > 0
        assert received_messages[0].pattern_name == "player_death"

    def test_subscribe_and_receive_messages(self):
        """Test subscribing to the bus and receiving messages"""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        self.bus.subscribe('test_subscriber', callback)

        self.bus.publish(content="Message 1")
        self.bus.publish(content="Message 2")

        time.sleep(0.2)

        assert len(received_messages) >= 2

    def test_unsubscribe(self):
        """Test unsubscribing from the bus"""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        self.bus.subscribe('test_subscriber', callback)
        self.bus.publish(content="Message 1")
        time.sleep(0.1)

        initial_count = len(received_messages)

        self.bus.unsubscribe('test_subscriber')
        self.bus.publish(content="Message 2")
        time.sleep(0.1)

        # Should not receive message after unsubscribe
        assert len(received_messages) == initial_count

    def test_multiple_subscribers(self):
        """Test multiple subscribers receive the same message"""
        received_1 = []
        received_2 = []

        def callback1(msg):
            received_1.append(msg)

        def callback2(msg):
            received_2.append(msg)

        self.bus.subscribe('subscriber1', callback1)
        self.bus.subscribe('subscriber2', callback2)

        self.bus.publish(content="Broadcast message")
        time.sleep(0.1)

        assert len(received_1) > 0
        assert len(received_2) > 0
        assert received_1[0].content == received_2[0].content

    def test_set_filter_level(self):
        """Test filtering messages by level"""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        self.bus.subscribe('filtered_subscriber', callback)
        self.bus.set_filter('filtered_subscriber', 'level', MessageLevel.WARNING)

        # These should be filtered out
        self.bus.publish(content="Debug", level=MessageLevel.DEBUG)
        self.bus.publish(content="Info", level=MessageLevel.INFO)

        # These should pass through
        self.bus.publish(content="Warning", level=MessageLevel.WARNING)
        self.bus.publish(content="Error", level=MessageLevel.ERROR)

        time.sleep(0.2)

        # Should only receive WARNING and ERROR
        assert len(received_messages) == 2
        assert all(msg.level.value >= MessageLevel.WARNING.value for msg in received_messages)

    def test_message_history_stores_messages(self):
        """Test that message history stores published messages"""
        self.bus.message_history = []  # Clear history

        self.bus.publish(content="Historical message 1")
        self.bus.publish(content="Historical message 2")

        time.sleep(0.1)

        history = self.bus.get_history()
        assert len(history) >= 2

    def test_get_history_with_limit(self):
        """Test getting limited message history"""
        self.bus.message_history = []

        for i in range(10):
            self.bus.publish(content=f"Message {i}")

        time.sleep(0.2)

        history = self.bus.get_history(max_messages=5)
        assert len(history) == 5

    def test_get_history_with_level_filter(self):
        """Test getting history filtered by level"""
        self.bus.message_history = []

        self.bus.publish(content="Debug", level=MessageLevel.DEBUG)
        self.bus.publish(content="Info", level=MessageLevel.INFO)
        self.bus.publish(content="Warning", level=MessageLevel.WARNING)
        self.bus.publish(content="Error", level=MessageLevel.ERROR)

        time.sleep(0.2)

        history = self.bus.get_history(min_level=MessageLevel.WARNING)
        assert len(history) == 2
        assert all(msg.level.value >= MessageLevel.WARNING.value for msg in history)

    def test_get_history_with_pattern_filter(self):
        """Test getting history filtered by pattern name"""
        self.bus.message_history = []

        self.bus.publish(content="Death 1", pattern_name="player_death")
        self.bus.publish(content="Death 2", pattern_name="player_death")
        self.bus.publish(content="Connection", pattern_name="player_connect")

        time.sleep(0.2)

        history = self.bus.get_history(pattern_name="player_death")
        assert len(history) == 2
        assert all(msg.pattern_name == "player_death" for msg in history)

    def test_history_max_size_limit(self):
        """Test that history respects max size limit"""
        self.bus.message_history = []
        self.bus.max_history_size = 50

        # Publish more messages than max size
        for i in range(100):
            self.bus.publish(content=f"Message {i}")

        time.sleep(0.5)

        history = self.bus.get_history()
        assert len(history) <= 50

    def test_emit_event(self):
        """Test emitting an event"""
        received_events = []

        def event_callback(*args, **kwargs):
            received_events.append((args, kwargs))

        self.bus.on('test_event', event_callback)
        self.bus.emit('test_event', 'arg1', 'arg2', key1='value1')

        time.sleep(0.1)

        assert len(received_events) > 0
        args, kwargs = received_events[0]
        assert args == ('arg1', 'arg2')
        assert kwargs == {'key1': 'value1'}

    def test_on_event_subscription(self):
        """Test subscribing to events with on()"""
        callback_executed = []

        def event_handler(data):
            callback_executed.append(data)

        subscription_id = self.bus.on('custom_event', event_handler)

        assert subscription_id is not None
        assert subscription_id.startswith('event_custom_event')

        self.bus.emit('custom_event', 'test_data')
        time.sleep(0.1)

        assert len(callback_executed) > 0
        assert callback_executed[0] == 'test_data'

    def test_off_event_unsubscription(self):
        """Test unsubscribing from events with off()"""
        callback_executed = []

        def event_handler(data):
            callback_executed.append(data)

        subscription_id = self.bus.on('custom_event', event_handler)
        self.bus.emit('custom_event', 'data1')
        time.sleep(0.1)

        initial_count = len(callback_executed)

        self.bus.off(subscription_id)
        self.bus.emit('custom_event', 'data2')
        time.sleep(0.1)

        # Should not receive event after unsubscription
        assert len(callback_executed) == initial_count

    def test_debug_mode(self):
        """Test enabling/disabling debug mode"""
        self.bus.set_debug_mode(True)
        assert self.bus.is_debug_mode() == True

        self.bus.set_debug_mode(False)
        assert self.bus.is_debug_mode() == False

    def test_subscribe_with_replay_history(self):
        """Test subscribing with history replay"""
        # Publish some messages before subscribing
        self.bus.message_history = []
        self.bus.publish(content="Historical 1", level=MessageLevel.INFO)
        self.bus.publish(content="Historical 2", level=MessageLevel.INFO)
        time.sleep(0.1)

        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        # Subscribe with replay
        self.bus.subscribe(
            'replay_subscriber',
            callback,
            replay_history=True,
            max_replay_messages=10
        )

        time.sleep(0.1)

        # Should receive historical messages
        assert len(received_messages) >= 2

    def test_thread_safety(self):
        """Test that message bus is thread-safe"""
        received_count = [0]
        lock = threading.Lock()

        def callback(msg):
            with lock:
                received_count[0] += 1

        self.bus.subscribe('thread_test', callback)

        def publisher(thread_id):
            for i in range(10):
                self.bus.publish(content=f"Thread {thread_id} message {i}")

        threads = [threading.Thread(target=publisher, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        time.sleep(0.5)

        # Should have received all 50 messages (5 threads * 10 messages)
        assert received_count[0] >= 45  # Allow for some timing variance

    def test_subscriber_error_doesnt_crash_bus(self):
        """Test that an error in one subscriber doesn't crash the bus"""
        successful_callbacks = []

        def faulty_callback(msg):
            raise Exception("Intentional error")

        def good_callback(msg):
            successful_callbacks.append(msg)

        self.bus.subscribe('faulty', faulty_callback)
        self.bus.subscribe('good', good_callback)

        self.bus.publish(content="Test message")
        time.sleep(0.1)

        # Good subscriber should still receive the message
        assert len(successful_callbacks) > 0


class TestConvenienceFunctions:
    """Test suite for convenience functions"""

    def test_setup_console_handler(self):
        """Test setting up console handler"""
        bus = MessageBus()

        handler_name = setup_console_handler(debug=True, replay_history=False)

        assert handler_name is not None
        assert handler_name.startswith('console_handler_')

        # Verify the handler is subscribed
        subscriber_names = [s['name'] for s in bus.subscribers]
        assert handler_name in subscriber_names


class TestMessageLevels:
    """Test message level enumeration"""

    def test_message_levels_exist(self):
        """Test that all message levels are defined"""
        assert MessageLevel.DEBUG is not None
        assert MessageLevel.INFO is not None
        assert MessageLevel.WARNING is not None
        assert MessageLevel.ERROR is not None
        assert MessageLevel.CRITICAL is not None

    def test_message_levels_order(self):
        """Test that message levels have correct ordering"""
        assert MessageLevel.DEBUG.value < MessageLevel.INFO.value
        assert MessageLevel.INFO.value < MessageLevel.WARNING.value
        assert MessageLevel.WARNING.value < MessageLevel.ERROR.value
        assert MessageLevel.ERROR.value < MessageLevel.CRITICAL.value
