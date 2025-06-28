#!/usr/bin/env python3
"""Trace when water column 2 changes happen during schedule generation."""

import sys
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('water2_trace.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Patch the Schedule.assign method to trace water 2 changes
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.time_slot import TimeSlot

original_assign = Schedule.assign
original_remove = Schedule.remove_assignment

def traced_assign(self, time_slot, assignment):
    """Traced version of Schedule.assign"""
    if time_slot.day == "水" and time_slot.period == 2:
        # Log the change
        logging.warning(f"[TRACE] Assigning to 水曜2限 - {assignment.class_ref.full_name}: {assignment.subject.name} (teacher: {assignment.teacher.name if assignment.teacher else 'None'})")
        
        # Check if locked
        if self.is_locked(time_slot, assignment.class_ref):
            logging.error(f"[TRACE] Cell is LOCKED but assignment attempted!")
        
        # Log stack trace to see where the call is coming from
        import traceback
        stack = traceback.extract_stack()
        for frame in stack[-10:-1]:  # Show last 10 frames except current
            if 'water2_trace' not in frame.filename:
                logging.debug(f"  Called from: {frame.filename}:{frame.lineno} in {frame.name}")
    
    # Call original method
    return original_assign(self, time_slot, assignment)

def traced_remove(self, time_slot, class_ref):
    """Traced version of Schedule.remove_assignment"""
    if time_slot.day == "水" and time_slot.period == 2:
        # Get current assignment before removal
        current = self.get_assignment(time_slot, class_ref)
        if current:
            logging.warning(f"[TRACE] Removing from 水曜2限 - {class_ref.full_name}: {current.subject.name}")
            
            # Check if locked
            if self.is_locked(time_slot, class_ref):
                logging.error(f"[TRACE] Cell is LOCKED but removal attempted!")
    
    # Call original method
    return original_remove(self, time_slot, class_ref)

# Apply patches
Schedule.assign = traced_assign
Schedule.remove_assignment = traced_remove

# Now run the generation
from src.presentation.cli.main import main
import sys

# Run with the same arguments
sys.argv = ['main.py', 'generate']
main()