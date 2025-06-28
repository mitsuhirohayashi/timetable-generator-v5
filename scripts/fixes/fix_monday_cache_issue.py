#!/usr/bin/env python3
"""Fix the Monday duplicate issue caused by stale cache in constraint validator."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def analyze_cache_issue():
    """Analyze the cache issue causing Monday duplicates."""
    
    print("Monday Duplicate Cache Issue Analysis")
    print("=" * 60)
    
    print("\nRoot Cause Identified:")
    print("-" * 40)
    print("1. SmartEmptySlotFiller uses UnifiedConstraintValidator to check constraints")
    print("2. UnifiedConstraintValidator caches daily subject counts for performance")
    print("3. When a new assignment is made via schedule.assign(), the cache is NOT cleared")
    print("4. Subsequent constraint checks use stale cache data, allowing duplicates")
    
    print("\nSpecific Issue Flow:")
    print("-" * 40)
    print("Example: 1年2組 on Monday")
    print("1. Initial state: 国語 at period 2")
    print("2. Empty slot at period 5")
    print("3. Validator checks if 国語 can be placed at period 5")
    print("4. Cached count says 1 (from initial check)")
    print("5. Max allowed is 1, so 1 < 1 is False... BUT")
    print("6. The cache wasn't updated after previous fills!")
    print("7. Real count might be 1, but cache still shows old value")
    
    print("\nWhy Monday has more issues:")
    print("-" * 40)
    print("1. Monday has the most empty slots (15 total)")
    print("2. More empty slots = more filling operations")
    print("3. More operations = more chance for cache staleness")
    print("4. The cache accumulates errors as filling progresses")
    
    print("\nSolution:")
    print("-" * 40)
    print("The SmartEmptySlotFiller needs to clear the validator's cache")
    print("after each successful assignment.")
    
    print("\nCode Fix Location:")
    print("-" * 40)
    print("File: src/domain/services/core/smart_empty_slot_filler.py")
    print("Line: 309 (after schedule.assign())")
    print("Add: self.constraint_validator.clear_cache()")
    
    return True


def create_patch():
    """Create a patch file for the fix."""
    
    patch_content = """
--- a/src/domain/services/core/smart_empty_slot_filler.py
+++ b/src/domain/services/core/smart_empty_slot_filler.py
@@ -307,6 +307,9 @@ class SmartEmptySlotFiller(LoggingMixin):
             if can_place:
                 # 割り当て実行
                 schedule.assign(time_slot, assignment)
+                # キャッシュをクリア（重要：新しい割り当て後は必ずキャッシュをクリア）
+                self.constraint_validator.clear_cache()
+                
                 self.logger.debug(
                     f"{time_slot} {class_ref}: {subject.name}({teacher.name})を割り当て（{strategy.name}戦略）"
                 )
"""
    
    with open('fix_monday_cache.patch', 'w') as f:
        f.write(patch_content)
    
    print("\nPatch file created: fix_monday_cache.patch")
    print("Apply with: patch -p1 < fix_monday_cache.patch")


if __name__ == '__main__':
    if analyze_cache_issue():
        create_patch()
        
        print("\n\nAlternative Quick Fix:")
        print("-" * 40)
        print("If you want to test without patching, you can disable caching entirely")
        print("by modifying UnifiedConstraintValidator._get_daily_subject_count_cached()")
        print("to always skip the cache lookup.")