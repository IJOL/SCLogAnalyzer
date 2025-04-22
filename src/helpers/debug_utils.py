#!/usr/bin/env python
"""
Debug utilities for the SC Log Analyzer.
Provides tools for debugging and tracing function execution.
"""
import logging
import os
import sys
import time
import functools
import inspect
from typing import Any, Callable, Dict, Optional, TypeVar
import io

# Global constant to control tracing
# Set this to True to enable function call tracing
ENABLE_FUNCTION_TRACING = True

# Configure a dedicated logger for tracing that's separate from the main application logs
_trace_logger = logging.getLogger('function_tracer')
_trace_logger.setLevel(logging.DEBUG)

# Set this to False to completely disable file handler creation
_ENABLE_FILE_LOGGING = True

if _ENABLE_FILE_LOGGING:
    # Determine the log file path
    if getattr(sys, 'frozen', False):
        # Running in a bundled application
        app_dir = os.path.dirname(sys.executable)
    else:
        # Running in development mode
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Create trace log file in the application directory
    _trace_log_file = os.path.join(app_dir, 'function_trace.log')
    
    # Configure file handler with UTF-8 encoding to support Unicode characters like → (U+2192)
    _file_handler = logging.FileHandler(_trace_log_file, mode='a', encoding='utf-8')
    _file_handler.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s'))
    _trace_logger.addHandler(_file_handler)

# Function return type
F = TypeVar('F', bound=Callable[..., Any])

def trace(func: F) -> F:
    """
    Decorator to trace function calls, arguments, and return values.
    Only logs if ENABLE_FUNCTION_TRACING is set to True.
    
    Args:
        func: The function to trace
        
    Returns:
        The wrapped function with tracing
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # If tracing is disabled, just call the function directly
        if not ENABLE_FUNCTION_TRACING:
            return func(*args, **kwargs)
        
        # Get function info
        module_name = func.__module__
        func_name = func.__qualname__  # Gets class.method for methods
        
                # Format arguments
        arg_str = _format_arguments(func, args, kwargs)
        
        # Log function entry
        _trace_logger.debug(f"ENTER | {module_name}.{func_name} | Args: {arg_str}")
        
        start_time = time.time()
        try:
            # Call the function
            result = func(*args, **kwargs)
            
            # Calculate execution time
            duration = time.time() - start_time
            
            # Format the result (limiting potential large outputs)
            result_str = _format_result(result)
            
            # Log function exit with result
            _trace_logger.debug(f"EXIT  | {module_name}.{func_name} | Duration: {duration:.6f}s | Result: {result_str}")
            
            return result
        except Exception as e:
            # Calculate execution time even for exceptions
            duration = time.time() - start_time
            
            # Log the exception
            _trace_logger.error(f"ERROR | {module_name}.{func_name} | Duration: {duration:.6f}s | Exception: {e.__class__.__name__}: {str(e)}")
            
            # Re-raise the exception
            raise
    
    return wrapper  # type: ignore

def _format_arguments(func: Callable, args: tuple, kwargs: Dict[str, Any]) -> str:
    """
    Format function arguments for logging.
    
    Args:
        func: The function being traced
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        String representation of arguments
    """
    # Try to get the function's signature
    try:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        # Format positional args with their parameter names when possible
        args_list = []
        for i, arg in enumerate(args):
            if i < len(param_names):
                # Skip 'self' or 'cls' for instance/class methods
                if i == 0 and param_names[i] in ('self', 'cls'):
                    args_list.append(f"{param_names[i]}=<{arg.__class__.__name__}>")
                else:
                    args_list.append(f"{param_names[i]}={_truncate_value(arg)}")
            else:
                # Fallback for varargs
                args_list.append(_truncate_value(arg))
        
        # Format keyword args
        kwargs_list = [f"{k}={_truncate_value(v)}" for k, v in kwargs.items()]
        
        # Combine all arguments
        return ', '.join(args_list + kwargs_list)
    except (ValueError, TypeError):
        # Fallback if signature extraction fails
        args_str = ', '.join([_truncate_value(arg) for arg in args])
        kwargs_str = ', '.join([f"{k}={_truncate_value(v)}" for k, v in kwargs.items()])
        parts = [p for p in [args_str, kwargs_str] if p]
        return ', '.join(parts)

def _format_result(result: Any) -> str:
    """
    Format function result for logging.
    
    Args:
        result: The return value to format
        
    Returns:
        String representation of result
    """
    return _truncate_value(result)

def _truncate_value(value: Any) -> str:
    """
    Truncate large values for logging.
    
    Args:
        value: Any value to truncate
        
    Returns:
        String representation of value, truncated if too large
    """
    try:
        # Special handling for common types
        if value is None:
            return 'None'
        elif isinstance(value, (bool, int, float)):
            return str(value)
        elif isinstance(value, str):
            if len(value) > 100:
                return f'"{value[:97]}..."'
            return f'"{value}"'
        elif isinstance(value, (list, tuple)):
            if len(value) > 5:
                return f"{value.__class__.__name__}[{len(value)} items]"
            return str([_truncate_value(item) for item in value])
        elif isinstance(value, dict):
            if len(value) > 5:
                return f"dict[{len(value)} items]"
            return str({k: _truncate_value(v) for k, v in list(value.items())[:5]})
        elif hasattr(value, '__class__'):
            return f"<{value.__class__.__name__} at {hex(id(value))}>"
        else:
            return str(value)
    except Exception:
        return f"<Error formatting value of type {type(value).__name__}>"

def set_function_tracing(enabled: bool) -> None:
    """
    Enable or disable function tracing globally.
    
    Args:
        enabled: True to enable tracing, False to disable
    """
    global ENABLE_FUNCTION_TRACING
    ENABLE_FUNCTION_TRACING = enabled
    _trace_logger.info(f"Function tracing {'enabled' if enabled else 'disabled'}")

def get_function_tracing_status() -> bool:
    """
    Get the current status of function tracing.
    
    Returns:
        True if function tracing is enabled, False otherwise
    """
    return ENABLE_FUNCTION_TRACING