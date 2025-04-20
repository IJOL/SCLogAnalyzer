#!/usr/bin/env python
"""
Event handling system for SC Log Analyzer.
Provides classes and utilities for event management across the application.
"""

class Event:
    """A simple event system to allow subscribers to listen for updates."""
    def __init__(self):
        self._subscribers = []

    def subscribe(self, callback):
        """Subscribe to the event."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback):
        """Unsubscribe from the event."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit(self, *args, **kwargs):
        """Emit the event to all subscribers."""
        for callback in self._subscribers:
            callback(*args, **kwargs)

    def clear(self):
        """Remove all subscribers."""
        self._subscribers = []