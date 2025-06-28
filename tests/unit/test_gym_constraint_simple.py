#!/usr/bin/env python3
"""Test gym usage constraint configuration loading"""

import sys
import logging
sys.path.append('.')

from src.domain.constraints.gym_usage_constraint import GymUsageConstraintRefactored

# Set up logging to see debug messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# Create constraint and check loaded configuration
constraint = GymUsageConstraintRefactored()

print("\nLoaded joint PE groups:")
print("=" * 80)

for group_name, class_refs in constraint.joint_pe_groups.items():
    classes = sorted([str(c) for c in class_refs])
    print(f"{group_name}: {', '.join(classes)}")

print("\nTotal groups loaded:", len(constraint.joint_pe_groups))