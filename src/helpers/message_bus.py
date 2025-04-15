import threading
import time
import queue
from enum import Enum, auto
from typing import Dict, List, Callable, Optional, Any


class MessageLevel(Enum):
    """Enumeration of message priority levels"""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class Message:
    """
    A message object that encapsulates all message data.
    """
    def __init__(
        self, 
        content: str, 
        timestamp: Optional[str] = None, 
        level: MessageLevel = MessageLevel.INFO,
        pattern_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a message.
        
        Args:
            content: The message content
            timestamp: Optional timestamp (if None, current time will be used)
            level: Message priority level
            pattern_name: Optional name of the regex pattern that generated this message
            metadata: Additional metadata associated with the message
        """
        self.content = content
        self.timestamp = timestamp
        
        # If no timestamp provided, use current time
        if self.timestamp is None:
            self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            
        self.level = level
        self.pattern_name = pattern_name
        self.metadata = metadata or {}
        self.creation_time = time.time()
        
    def get_formatted_message(self) -> str:
        """
        Get the formatted message with timestamp.
        
        Returns:
            Formatted message string
        """
        if self.timestamp:
            return f"{self.timestamp} - {self.content}"
        else:
            return f"*{self.creation_time_str} - {self.content}"
            
    @property
    def creation_time_str(self) -> str:
        """Get the creation time as a formatted string."""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.creation_time))


class MessageBus:
    """
    Central message bus that handles routing of messages to subscribers.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """
        Singleton pattern to ensure only one MessageBus instance exists.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MessageBus, cls).__new__(cls)
                # Initialize instance variables
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self) -> None:
        """Initialize the message bus instance."""
        self.subscribers: List[Dict] = []
        self.message_queue = queue.Queue()
        self.is_running = False
        self.worker_thread = None
        self.message_history: List[Message] = []
        self.max_history_size = 1000  # Maximum number of messages to keep in history
        self.filters = {}  # Filters for conditional message processing
    
    def start(self) -> None:
        """
        Start the message bus processing thread.
        """
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._process_message_queue)
            self.worker_thread.daemon = True
            self.worker_thread.start()
    
    def stop(self) -> None:
        """
        Stop the message bus processing thread.
        """
        self.is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            # Add a None message to unblock the queue
            self.message_queue.put(None)
            self.worker_thread.join(timeout=1.0)
    
    def _process_message_queue(self) -> None:
        """
        Process messages from the queue and route them to subscribers.
        """
        while self.is_running:
            try:
                message = self.message_queue.get(timeout=0.5)
                
                # None message is a signal to stop
                if message is None:
                    break
                    
                # Store in history before routing
                self._add_to_history(message)
                
                # Send to all subscribers
                for subscriber in self.subscribers:
                    try:
                        # Apply any filters for this subscriber
                        if self._should_process_message(subscriber, message):
                            # Call the subscriber's callback function
                            subscriber['callback'](message)
                    except Exception as e:
                        # Don't let a subscriber error crash the bus
                        print(f"Error in subscriber {subscriber['name']}: {e}")
                
                # Mark task as done
                self.message_queue.task_done()
            except queue.Empty:
                # No messages, continue loop
                continue
            except Exception as e:
                print(f"Error processing message queue: {e}")
    
    def _should_process_message(self, subscriber: Dict, message: Message) -> bool:
        """
        Check if a message should be processed by a subscriber based on filters.
        
        Args:
            subscriber: The subscriber dictionary to check
            message: The message to check
            
        Returns:
            True if the message should be processed, False otherwise
        """
        # Get filters for this subscriber
        subscriber_filters = self.filters.get(subscriber['name'], {})
        
        # If no filters, process all messages
        if not subscriber_filters:
            return True
        
        # Check level filter if present
        if 'level' in subscriber_filters:
            min_level = subscriber_filters['level']
            if message.level.value < min_level.value:
                return False
        
        # Check pattern filter if present
        if 'patterns' in subscriber_filters:
            patterns = subscriber_filters['patterns']
            if patterns and message.pattern_name not in patterns:
                return False
        
        # Any other custom filters can be added here
        
        return True
    
    def _add_to_history(self, message: Message) -> None:
        """
        Add a message to the history, removing oldest if over max size.
        
        Args:
            message: The message to add to history
        """
        self.message_history.append(message)
        
        # Remove oldest messages if over max size
        while len(self.message_history) > self.max_history_size:
            self.message_history.pop(0)
    
    def publish(
        self,
        content: str,
        timestamp: Optional[str] = None,
        level: MessageLevel = MessageLevel.INFO,
        pattern_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Publish a message to the bus.
        
        Args:
            content: Message content
            timestamp: Optional timestamp
            level: Message priority level
            pattern_name: Optional regex pattern name
            metadata: Additional metadata
        """
        message = Message(
            content=content,
            timestamp=timestamp,
            level=level,
            pattern_name=pattern_name,
            metadata=metadata
        )
        self.message_queue.put(message)
    
    def subscribe(self, name: str, callback: Callable[[Message], None]) -> None:
        """
        Add a subscriber to the bus.
        
        Args:
            name: Name of the subscriber for identification and filtering
            callback: Function to call with each message
        """
        subscriber = {
            'name': name,
            'callback': callback
        }
        
        # Check if this subscriber name already exists
        for existing in self.subscribers:
            if existing['name'] == name:
                existing['callback'] = callback  # Update callback if name exists
                return
                
        self.subscribers.append(subscriber)
    
    def unsubscribe(self, name: str) -> None:
        """
        Remove a subscriber from the bus.
        
        Args:
            name: Name of the subscriber to remove
        """
        self.subscribers = [s for s in self.subscribers if s['name'] != name]
        
        # Also remove any filters for this subscriber
        if name in self.filters:
            del self.filters[name]
    
    def set_filter(
        self, 
        subscriber_name: str, 
        filter_type: str, 
        filter_value: Any
    ) -> None:
        """
        Set a filter for a specific subscriber.
        
        Args:
            subscriber_name: Name of the subscriber
            filter_type: Type of filter (e.g., 'level', 'patterns')
            filter_value: Value for the filter
        """
        if subscriber_name not in self.filters:
            self.filters[subscriber_name] = {}
        
        self.filters[subscriber_name][filter_type] = filter_value
    
    def clear_filter(self, subscriber_name: str, filter_type: Optional[str] = None) -> None:
        """
        Clear filters for a subscriber.
        
        Args:
            subscriber_name: Name of the subscriber
            filter_type: Type of filter to clear, or None to clear all
        """
        if subscriber_name in self.filters:
            if filter_type is None:
                # Clear all filters
                self.filters.pop(subscriber_name)
            elif filter_type in self.filters[subscriber_name]:
                # Clear specific filter
                self.filters[subscriber_name].pop(filter_type)
    
    def get_history(
        self, 
        max_messages: Optional[int] = None, 
        min_level: Optional[MessageLevel] = None,
        pattern_name: Optional[str] = None
    ) -> List[Message]:
        """
        Get message history with optional filtering.
        
        Args:
            max_messages: Maximum number of messages to return (most recent first)
            min_level: Minimum message level to include
            pattern_name: Filter by pattern name
            
        Returns:
            List of messages from history matching the criteria
        """
        # Start with all messages in reverse order (newest first)
        filtered_history = list(reversed(self.message_history))
        
        # Apply filters
        if min_level is not None:
            filtered_history = [m for m in filtered_history if m.level.value >= min_level.value]
            
        if pattern_name is not None:
            filtered_history = [m for m in filtered_history if m.pattern_name == pattern_name]
        
        # Apply max messages limit
        if max_messages is not None:
            filtered_history = filtered_history[:max_messages]
            
        return filtered_history
    
    def clear_history(self) -> None:
        """Clear the message history."""
        self.message_history.clear()


# Create a global message bus instance
message_bus = MessageBus()
# Start the message bus on import
message_bus.start()