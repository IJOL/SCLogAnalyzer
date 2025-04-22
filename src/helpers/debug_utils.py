#!/usr/bin/env python
"""
Debug utilities for SCLogAnalyzer, including performance tracing
and other development/debugging tools.
"""

import time
import functools
import logging
import os
from datetime import datetime

# Set up a dedicated logger for performance tracing
logger = logging.getLogger('performance_tracer')
logger.setLevel(logging.DEBUG)

# Create a file handler that logs to performance_trace.log
log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log_file = os.path.join(log_dir, 'performance_trace.log')
handler = logging.FileHandler(log_file)
handler.setLevel(logging.DEBUG)

# Create a formatter
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

# Dictionary to store performance metrics
performance_metrics = {}

def trace_performance(name=None):
    """
    Decorator to trace function execution time.
    
    Args:
        name: Optional custom name for the trace. If not provided, uses function name.
        
    Returns:
        Decorated function that logs execution time.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            trace_name = name or func.__name__
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Store metrics
                if trace_name in performance_metrics:
                    performance_metrics[trace_name]['count'] += 1
                    performance_metrics[trace_name]['total_time'] += execution_time
                    performance_metrics[trace_name]['max_time'] = max(execution_time, performance_metrics[trace_name]['max_time'])
                else:
                    performance_metrics[trace_name] = {
                        'count': 1, 
                        'total_time': execution_time,
                        'max_time': execution_time
                    }
                
                # Log the trace
                logger.debug(f"TRACE | {trace_name} | Duration: {execution_time:.6f}s")
                return result
            except Exception as e:
                end_time = time.time()
                execution_time = end_time - start_time
                logger.error(f"TRACE-ERROR | {trace_name} | Duration: {execution_time:.6f}s | Error: {str(e)}")
                raise
                
        return wrapper
    return decorator

def start_timer(name):
    """
    Start a timer for manual performance tracking.
    
    Args:
        name: Name of the timer
        
    Returns:
        Timer object that can be used with end_timer or stop_timer
    """
    timer = {'name': name, 'start': time.time()}
    logger.debug(f"START | {name}")
    return timer

def end_timer(timer):
    """
    End a timer and log the execution time.
    
    Args:
        timer: Timer object returned from start_timer
        
    Returns:
        Execution time in seconds
    """
    end_time = time.time()
    execution_time = end_time - timer['start']
    
    # Store metrics
    name = timer['name']
    if name in performance_metrics:
        performance_metrics[name]['count'] += 1
        performance_metrics[name]['total_time'] += execution_time
        performance_metrics[name]['max_time'] = max(execution_time, performance_metrics[name]['max_time'])
    else:
        performance_metrics[name] = {
            'count': 1, 
            'total_time': execution_time, 
            'max_time': execution_time
        }
    
    # Log the trace
    logger.debug(f"END | {name} | Duration: {execution_time:.6f}s")
    return execution_time

def get_performance_summary():
    """
    Get a summary of all performance metrics.
    
    Returns:
        String with summary of all performance metrics.
    """
    summary_lines = [
        "===== Performance Metrics Summary =====",
        f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Name                             | Count | Total Time (s) | Avg Time (s) | Max Time (s)",
        "----------------------------------|-------|---------------|--------------|-------------"
    ]
    
    for name, data in sorted(performance_metrics.items(), key=lambda x: x[1]['total_time'], reverse=True):
        avg_time = data['total_time'] / data['count']
        summary_lines.append(
            f"{name:<32} | {data['count']:5d} | {data['total_time']:13.6f} | {avg_time:12.6f} | {data['max_time']:11.6f}"
        )
    
    summary_lines.append("=" * 80)
    return "\n".join(summary_lines)

def log_performance_summary():
    """Log a summary of all performance metrics."""
    summary = get_performance_summary()
    logger.info("\n" + summary)
    return summary

def reset_performance_metrics():
    """Reset all performance metrics."""
    global performance_metrics
    performance_metrics = {}
    logger.debug("Performance metrics reset")