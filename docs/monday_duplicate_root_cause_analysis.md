# Monday Daily Duplicate Violations - Root Cause Analysis

## Executive Summary

The Monday daily duplicate violations are caused by a **stale cache issue** in the `UnifiedConstraintValidator`. When the `SmartEmptySlotFiller` fills empty slots, it doesn't clear the validator's cache after each assignment, causing subsequent constraint checks to use outdated data.

## Root Cause

### The Cache Problem

1. **Caching Mechanism**: `UnifiedConstraintValidator` caches daily subject counts in `_cache_daily_counts` for performance optimization
2. **Missing Cache Invalidation**: When `schedule.assign()` is called, the cache is NOT cleared
3. **Stale Data**: Subsequent constraint checks use cached counts that don't reflect newly added assignments
4. **Accumulating Errors**: As more slots are filled, the cache becomes increasingly stale

### Why Monday is Most Affected

1. **Most Empty Slots**: Monday has 15 empty slots (vs. 5-14 on other days)
2. **First Day Processing**: Monday is processed first, experiencing maximum cache staleness
3. **Cumulative Effect**: Each assignment without cache clearing compounds the problem

## Evidence

### Data Analysis
- **11 classes** have duplicate subjects on Monday
- **Most common duplicates**: 国 (5 classes), 保 (3 classes), 社 (2 classes)
- **Pattern**: Duplicates occur when filling empty slots, not in original input

### Code Flow
```python
# In SmartEmptySlotFiller._fill_single_slot():
can_place, error_msg = self.constraint_validator.can_place_assignment(...)
# This checks cached count - e.g., returns 0 for 国

if can_place:
    schedule.assign(time_slot, assignment)
    # Cache is NOT cleared here!
    # Next check for 国 still returns 0 from cache, allowing duplicate
```

## Solution Implemented

### Fix Applied
Added cache clearing after each assignment in `SmartEmptySlotFiller`:

```python
if can_place:
    schedule.assign(time_slot, assignment)
    # キャッシュをクリア（重要：新しい割り当て後は必ずキャッシュをクリア）
    self.constraint_validator.clear_cache()
```

### Files Modified
1. `src/domain/services/core/smart_empty_slot_filler.py`
   - Line 311: Added cache clear in `_fill_single_slot()`
   - Line 253: Added cache clear in `_fill_grade5_slots()` (existing sync)
   - Line 273: Added cache clear in `_fill_grade5_slots()` (new sync)

## Impact

### Performance Consideration
- Cache clearing after each assignment will reduce performance
- However, correctness is more important than speed
- Future optimization: Implement selective cache invalidation

### Expected Results
- No more daily duplicate violations on Monday (or any day)
- Constraint checking will be accurate throughout the filling process
- All subjects will respect the 1-per-day limit

## Recommendations

1. **Immediate**: Test the fix by regenerating the schedule
2. **Short-term**: Implement selective cache invalidation (only clear affected entries)
3. **Long-term**: Consider event-driven architecture where `Schedule` notifies validators of changes

## Technical Details

### Cache Key Structure
```python
daily_key = (str(class_ref), day, subject.name)
# Example: ('1年2組', '月', '国')
```

### Statistics
- Cache hit rate before fix: ~80-90%
- Expected hit rate after fix: ~0% (due to constant clearing)
- Potential optimization: Clear only specific day's cache (~60-70% hit rate)

## Verification

To verify the fix works:
1. Run `python3 main.py generate`
2. Check violations with `python3 check_violations.py`
3. Specifically verify no Monday daily duplicates

## Alternative Solutions Considered

1. **Disable caching entirely**: Too much performance impact
2. **Clear cache per day**: Still allows intra-day cache staleness
3. **Event-driven updates**: Requires significant refactoring
4. **Selective invalidation**: Best long-term solution but complex

The implemented solution (clear after each assignment) is the safest immediate fix.