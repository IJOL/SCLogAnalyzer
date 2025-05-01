import threading
import time
import queue
from enum import Enum, auto
from typing import Dict, List, Callable, Optional, Any
import sys
import logging

# Configure logger for components that don't use message bus
default_logger = logging.getLogger("default")
default_handler = logging.StreamHandler(sys.stdout)
default_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
default_logger.addHandler(default_handler)
default_logger.setLevel(logging.INFO)

class RedirectText:
    """Class to redirect stdout to the message bus."""
    def __init__(self, stdout=None):
        self.stdout = stdout  # Store the original stdout if needed

    def write(self, string):
        """Publish the string to the message bus."""
        if string and string.strip():  # Skip empty strings
            try:
                # Use the module-level import of message_bus
                message_bus.publish(
                    content=string,
                    level=MessageLevel.INFO,
                    metadata={'from_stdout': True}
                )
            except Exception as e:
                # Fallback to direct writing if message_bus isn't available
                if self.stdout:
                    self.stdout.write(string)

    def flush(self):
        pass


class MessageLevel(Enum):
    """Enumeration of message priority levels"""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

# Map MessageLevel to standard logging levels
level_to_logging = {
    MessageLevel.DEBUG: logging.DEBUG,
    MessageLevel.INFO: logging.INFO,
    MessageLevel.WARNING: logging.WARNING,
    MessageLevel.ERROR: logging.ERROR,
    MessageLevel.CRITICAL: logging.CRITICAL
}


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
        self.debug_mode = False  # Debug mode flag for peeking at messages
        self.redirect_stdout = sys.stdout  # Store original stdout
        sys.stdout = RedirectText()  # Redirect stdout to the message bus

    def set_debug_mode(self, enabled: bool) -> None:
        """
        Enable or disable debug mode.
        When debug mode is enabled, all messages will also be printed to stdout.
        
        Args:
            enabled: True to enable debug mode, False to disable
        """
        self.debug_mode = enabled
        print(f"Message bus debug mode {'enabled' if enabled else 'disabled'}")
    
    def is_debug_mode(self) -> bool:
        """
        Check if debug mode is enabled.
        
        Returns:
            True if debug mode is enabled, False otherwise
        """
        return self.debug_mode
    
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
                
                # Debug mode: print message to stdout with level indicator
                if self.debug_mode:
                    level_indicators = {
                        MessageLevel.DEBUG: "[DEBUG]",
                        MessageLevel.INFO: "[INFO]",
                        MessageLevel.WARNING: "[WARN]",
                        MessageLevel.ERROR: "[ERROR]",
                        MessageLevel.CRITICAL: "[CRIT]"
                    }
                    level_str = level_indicators.get(message.level, "[INFO]")
                    pattern_str = f"[{message.pattern_name}]" if message.pattern_name else ""
                    (f"{level_str}{pattern_str} {message.get_formatted_message()}")
                    self.redirect_stdout.write(
                        f"{level_str} {message.get_formatted_message()}\n"
                    )
                
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
    
    def subscribe(self, name: str, callback: Callable[[Message], None], 
                   replay_history: bool = False, 
                   max_replay_messages: Optional[int] = 100,
                   min_replay_level: Optional[MessageLevel] = None) -> None:
        """
        Add a subscriber to the bus.
        
        Args:
            name: Name of the subscriber for identification and filtering
            callback: Function to call with each message
            replay_history: Whether to replay historical messages to the new subscriber
            max_replay_messages: Maximum number of historical messages to replay (newest first)
            min_replay_level: Minimum message level to include in replay
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
        
        # Replay history if requested
        if replay_history and self.message_history:
            # Get filtered history for replay
            historical_messages = self.get_history(
                max_messages=max_replay_messages,
                min_level=min_replay_level
            )
            
            # Log that we're replaying messages
            print(f"Replaying {len(historical_messages)} messages to new subscriber '{name}'")
            
            # Send historical messages to the new subscriber
            for message in historical_messages:
                try:
                    # Apply any filters for this subscriber
                    if self._should_process_message(subscriber, message):
                        # Call the subscriber's callback function
                        callback(message)
                except Exception as e:
                    # Don't let a subscriber error crash the bus
                    print(f"Error replaying message to subscriber {name}: {e}")
    
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

    def emit(self, event_name, *args, **kwargs):
        """
        Emit an event through the message bus.
        
        Args:
            event_name: Name of the event
            *args, **kwargs: Parameters to pass to event handlers
        """
        metadata = {
            'is_event': True,
            'event_name': event_name,
            'args': args,
            'kwargs': kwargs
        }
        
        # Use different logging behavior based on debug mode
        if self.debug_mode:
            # In debug mode, format and include parameter information at DEBUG level
            param_info = []
            
            # Format positional arguments
            if args:
                param_info.append(f"args: {repr(args)}")
                
            # Format keyword arguments
            if kwargs:
                # Format each kwarg for better readability
                kwarg_items = [f"{k}={repr(v)}" for k, v in kwargs.items()]
                param_info.append(f"kwargs: {{{', '.join(kwarg_items)}}}")
                
            # Create detailed content for debug logging
            detailed_content = f"Event: {event_name}"
            if param_info:
                detailed_content += f" with {', '.join(param_info)}"
                
            # Publish with detailed content at DEBUG level
            self.publish(
                content=detailed_content,
                level=MessageLevel.DEBUG,
                metadata=metadata
            )
        else:
            # Normal mode - just use event name at INFO level
            self.publish(
                content=f"Event: {event_name}",
                level=MessageLevel.INFO,
                metadata=metadata
            )

    def on(self, event_name, callback):
        """
        Subscribe to an event.
        
        Args:
            event_name: Name of the event to subscribe to
            callback: Function to call when the event occurs
            
        Returns:
            Subscription ID that can be used for unsubscribing
        """
        subscription_id = f"event_{event_name}_{int(time.time())}_{id(callback)}"
        
        # Create wrapper to extract and pass arguments
        def event_callback_wrapper(message):
            if (message.metadata.get('is_event', False) and 
                message.metadata.get('event_name') == event_name):
                args = message.metadata.get('args', ())
                kwargs = message.metadata.get('kwargs', {})
                callback(*args, **kwargs)
        
        # Subscribe the wrapper to receive messages
        self.subscribe(
            name=subscription_id,
            callback=event_callback_wrapper
        )
        
        return subscription_id

    def off(self, subscription_id):
        """
        Unsubscribe from an event.
        
        Args:
            subscription_id: Subscription ID returned by on()
        """
        self.unsubscribe(subscription_id)


# Create a global message bus instance
message_bus = MessageBus()
# Start the message bus on import
message_bus.start()

def setup_console_handler(debug=False, replay_history=True):
    """
    Set up a console handler that outputs message bus messages to the console.
    This is useful for command-line scripts that use the message bus.
    
    Args:
        debug (bool): Whether to show debug-level messages. If False, only INFO and above will be shown.
        replay_history (bool): Whether to replay the message history to the new subscriber.
    """
    # Define a simple handler that prints messages to the console
    def console_handler(message):
        level_indicators = {
            MessageLevel.DEBUG: "\033[36m[DEBUG]\033[0m",  # Cyan
            MessageLevel.INFO: "\033[32m[INFO]\033[0m",   # Green
            MessageLevel.WARNING: "\033[33m[WARN]\033[0m",  # Yellow
            MessageLevel.ERROR: "\033[31m[ERROR]\033[0m",  # Red
            MessageLevel.CRITICAL: "\033[35m[CRIT]\033[0m"  # Magenta
        }
        
        # Get the appropriate level indicator
        level_str = level_indicators.get(message.level, "\033[32m[INFO]\033[0m")
        
        # Print the formatted message to the console
        print(f"{level_str} {message.get_formatted_message()}")
    
    # Create a unique handler name based on current time to avoid conflicts
    handler_name = f"console_handler_{int(time.time())}"
    
    # Set the minimum level filter based on the debug parameter
    min_level = MessageLevel.DEBUG if debug else MessageLevel.INFO
    
    # Subscribe to the message bus with history replay if requested
    message_bus.subscribe(
        name=handler_name,
        callback=console_handler,
        replay_history=replay_history,
        max_replay_messages=100,
        min_replay_level=min_level
    )
    
    # Set the minimum level filter
    message_bus.set_filter(handler_name, 'level', min_level)
    
    # Configure the default logger to also use similar formatting for consistency
    # This ensures messages through both paths (message bus and direct logging) look similar
    log_format = '%(asctime)s - %(message)s'
    if debug:
        default_logger.setLevel(logging.DEBUG)
    else:
        default_logger.setLevel(logging.INFO)
    
    # Clear existing handlers and add a new one with matching format
    default_logger.handlers.clear()
    default_handler = logging.StreamHandler(sys.stdout)
    default_handler.setFormatter(logging.Formatter(log_format))
    default_logger.addHandler(default_handler)
    
    # Return the handler name so it can be unsubscribed later if needed
    return handler_name

def log_message(content, level="INFO", pattern_name=None, metadata=None):
    """
    Send a message through the message bus or fallback to logging if not available.
    This is a convenience function to be used by components that want to decouple
    from direct message_bus usage.
    
    Args:
        content: The message content
        level: Message level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        pattern_name: Optional regex pattern name
        metadata: Additional metadata
    """
    try:
        # Map string level to MessageLevel enum
        level_map = {
            "DEBUG": MessageLevel.DEBUG,
            "INFO": MessageLevel.INFO,
            "WARNING": MessageLevel.WARNING,
            "ERROR": MessageLevel.ERROR,
            "CRITICAL": MessageLevel.CRITICAL
        }
        msg_level = level_map.get(level.upper(), MessageLevel.INFO)
        
        # Try to send message to bus
        message_bus.publish(
            content=content,
            level=msg_level,
            pattern_name=pattern_name,
            metadata=metadata
        )
    except Exception as e:
        # Fallback to standard logging if message bus not available
        log_level = logging.INFO
        if isinstance(level, str):
            log_level = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL
            }.get(level.upper(), logging.INFO)
        
        # Add pattern name to message if provided
        full_message = f"[{pattern_name}] {content}" if pattern_name else content
        default_logger.log(log_level, full_message)