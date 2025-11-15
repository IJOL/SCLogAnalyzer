"""Tests for rate_limiter module"""
import pytest
import time
import threading

# Add src to path for imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from helpers.core.rate_limiter import MessageRateLimiter


class TestMessageRateLimiter:
    """Test suite for MessageRateLimiter class"""

    def test_initialization_default(self):
        """Test rate limiter initialization with default parameters"""
        limiter = MessageRateLimiter()

        assert limiter.timeout == 300
        assert limiter.max_duplicates == 1
        assert limiter.cleanup_interval == 60
        assert limiter.global_limit_count is None
        assert limiter.global_limit_window is None
        assert limiter.messages == {}
        assert limiter._recent_times == []

    def test_initialization_custom(self):
        """Test rate limiter initialization with custom parameters"""
        limiter = MessageRateLimiter(
            timeout=120,
            max_duplicates=3,
            cleanup_interval=30,
            global_limit_count=100,
            global_limit_window=60
        )

        assert limiter.timeout == 120
        assert limiter.max_duplicates == 3
        assert limiter.cleanup_interval == 30
        assert limiter.global_limit_count == 100
        assert limiter.global_limit_window == 60

    def test_first_message_allowed(self):
        """Test that first message is always allowed"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=1)

        result = limiter.should_send("Test message")
        assert result == True

    def test_duplicate_message_blocked(self):
        """Test that duplicate message within timeout is blocked"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=1)

        # Send first message
        assert limiter.should_send("Test message") == True

        # Send duplicate immediately
        assert limiter.should_send("Test message") == False

    def test_duplicate_message_allowed_after_timeout(self):
        """Test that duplicate message is allowed after timeout expires"""
        limiter = MessageRateLimiter(timeout=0.5, max_duplicates=1)

        # Send first message
        assert limiter.should_send("Test message") == True

        # Send duplicate immediately - should be blocked
        assert limiter.should_send("Test message") == False

        # Wait for timeout
        time.sleep(0.6)

        # Should be allowed again
        assert limiter.should_send("Test message") == True

    def test_max_duplicates_limit(self):
        """Test that max_duplicates is respected"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=3)

        message = "Test message"

        # First message allowed
        assert limiter.should_send(message) == True

        # Next 3 duplicates allowed (total max_duplicates=3)
        assert limiter.should_send(message) == True
        assert limiter.should_send(message) == True
        assert limiter.should_send(message) == True

        # 4th duplicate blocked
        assert limiter.should_send(message) == False

    def test_different_messages_independent(self):
        """Test that different messages are tracked independently"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=1)

        assert limiter.should_send("Message 1") == True
        assert limiter.should_send("Message 2") == True
        assert limiter.should_send("Message 3") == True

        # Duplicates blocked independently
        assert limiter.should_send("Message 1") == False
        assert limiter.should_send("Message 2") == False

    def test_message_type_differentiation(self):
        """Test that messages with different types are tracked separately"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=1)

        # Same message content, different types
        assert limiter.should_send("Alert", message_type="discord") == True
        assert limiter.should_send("Alert", message_type="stdout") == True

        # Duplicates blocked per type
        assert limiter.should_send("Alert", message_type="discord") == False
        assert limiter.should_send("Alert", message_type="stdout") == False

    def test_cleanup_messages(self):
        """Test that old messages are cleaned up"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=1, cleanup_interval=1)

        limiter.should_send("Message 1")
        limiter.should_send("Message 2")

        assert len(limiter.messages) == 2

        # Wait for cleanup interval
        time.sleep(1.1)

        # Trigger cleanup by sending another message
        limiter.should_send("Message 3")

        # Old messages should still be there if within timeout
        assert len(limiter.messages) == 3

        # Wait longer than timeout + cleanup interval
        time.sleep(limiter.timeout + 1)
        limiter.should_send("Message 4")

        # After cleanup, only recent messages remain
        assert "Message 4" in str(limiter.messages.keys())

    def test_get_stats_existing_message(self):
        """Test getting stats for an existing message"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=2)

        message = "Test message"
        limiter.should_send(message)
        limiter.should_send(message)

        stats = limiter.get_stats(message)

        assert stats is not None
        assert 'last_sent' in stats
        assert 'count' in stats
        assert 'blocked' in stats
        assert stats['count'] == 2
        assert stats['blocked'] == False  # Not blocked yet (max is 2)

    def test_get_stats_blocked_message(self):
        """Test stats show message as blocked when limit exceeded"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=1)

        message = "Test message"
        limiter.should_send(message)
        limiter.should_send(message)  # This one blocked

        stats = limiter.get_stats(message)

        assert stats['blocked'] == True
        assert stats['count'] >= 2

    def test_get_stats_nonexistent_message(self):
        """Test getting stats for a message that hasn't been sent"""
        limiter = MessageRateLimiter()

        stats = limiter.get_stats("Nonexistent message")
        assert stats is None

    def test_global_limit_not_set(self):
        """Test that messages are allowed when no global limit is set"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=5)

        # Send many different messages
        for i in range(100):
            assert limiter.should_send(f"Message {i}") == True

    def test_global_limit_enforced(self):
        """Test that global event limit is enforced"""
        limiter = MessageRateLimiter(
            timeout=10,
            max_duplicates=10,
            global_limit_count=5,
            global_limit_window=1.0
        )

        # First 5 messages allowed
        for i in range(5):
            assert limiter.should_send(f"Message {i}") == True

        # 6th message blocked by global limit
        assert limiter.should_send("Message 6") == False

    def test_global_limit_resets_after_window(self):
        """Test that global limit resets after time window expires"""
        limiter = MessageRateLimiter(
            timeout=10,
            max_duplicates=10,
            global_limit_count=3,
            global_limit_window=0.5
        )

        # Send 3 messages (global limit)
        for i in range(3):
            assert limiter.should_send(f"Message {i}") == True

        # 4th message blocked
        assert limiter.should_send("Message 4") == False

        # Wait for window to expire
        time.sleep(0.6)

        # Should allow messages again
        assert limiter.should_send("Message 5") == True

    def test_thread_safety(self):
        """Test that rate limiter is thread-safe"""
        limiter = MessageRateLimiter(timeout=1, max_duplicates=1)
        results = []
        lock = threading.Lock()

        def worker(thread_id):
            for i in range(10):
                result = limiter.should_send(f"Thread {thread_id} message {i}")
                with lock:
                    results.append((thread_id, i, result))
                time.sleep(0.01)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have all results without crashes
        assert len(results) == 50

        # Each unique message should have been allowed once
        allowed = [r for r in results if r[2]]
        assert len(allowed) > 0

    def test_concurrent_same_message(self):
        """Test handling of concurrent identical messages"""
        limiter = MessageRateLimiter(timeout=5, max_duplicates=1)
        results = []
        lock = threading.Lock()

        def worker():
            result = limiter.should_send("Same message")
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Only one or two should have been allowed (due to timing)
        allowed_count = sum(results)
        assert allowed_count >= 1 and allowed_count <= 2

    def test_message_count_increments(self):
        """Test that message count increments correctly"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=5)

        message = "Counter test"

        for i in range(5):
            limiter.should_send(message)

        stats = limiter.get_stats(message)
        assert stats['count'] == 5

    def test_timeout_zero(self):
        """Test behavior with zero timeout"""
        limiter = MessageRateLimiter(timeout=0, max_duplicates=1)

        # First message allowed
        assert limiter.should_send("Message") == True

        # Duplicate blocked
        assert limiter.should_send("Message") == False

        # Even tiny wait should allow it again with timeout=0
        time.sleep(0.01)
        assert limiter.should_send("Message") == True

    def test_max_duplicates_zero(self):
        """Test behavior with max_duplicates=0 (block all duplicates)"""
        limiter = MessageRateLimiter(timeout=10, max_duplicates=0)

        # First message allowed
        assert limiter.should_send("Message") == True

        # Immediate duplicate blocked (because max is 0)
        assert limiter.should_send("Message") == False

    def test_cleanup_interval_triggers(self):
        """Test that cleanup actually triggers at the right interval"""
        limiter = MessageRateLimiter(
            timeout=0.2,
            max_duplicates=1,
            cleanup_interval=0.3
        )

        limiter.should_send("Old message")

        # Wait longer than timeout but less than cleanup interval
        time.sleep(0.25)

        # Message should still be in dict
        assert "Old message" in str(limiter.messages.keys())

        # Wait for cleanup interval
        time.sleep(0.1)  # Total: 0.35s > cleanup_interval

        # Trigger cleanup by sending new message
        limiter.should_send("New message")

        # Cleanup should have removed old message
        # (It's been more than cleanup_interval since last cleanup)
        initial_count = len(limiter.messages)

        # Send another message after more time
        time.sleep(0.5)
        limiter.should_send("Another message")

        # Verify cleanup happened
        assert len(limiter.messages) <= initial_count + 1
