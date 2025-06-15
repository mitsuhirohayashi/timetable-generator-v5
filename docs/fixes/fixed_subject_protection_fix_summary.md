# Fixed Subject Protection Fix Summary

## Problem
The timetable generation system was failing with the error:
```
ERROR: 希望時間割読み込みエラー: Cannot modify fixed subject slot: 火曜6校時 - 1年1組
```

This caused the system to generate a new schedule from scratch, losing all test period subject information from input.csv.

## Root Cause
The fixed subject protection mechanism was preventing the loading of input.csv data because:
1. The Schedule entity has a FixedSubjectProtectionPolicy that prevents modification of slots containing fixed subjects (YT, 欠, etc.)
2. When CSVScheduleRepository tried to load YT into Tuesday 6th period, it was blocked by the protection
3. Additional issues occurred during generation when trying to remove fixed subjects for teacher absence violations

## Solution
We implemented a multi-part fix:

### 1. CSV Loading Protection Control
Modified `CSVScheduleRepository.load_desired_schedule()` to temporarily disable fixed subject protection during initial load:
```python
# At the start of loading
schedule.disable_fixed_subject_protection()

# At the end (and in error handler)
schedule.enable_fixed_subject_protection()
```

### 2. Teacher Absence Violation Handling
Modified `ScheduleGenerationService._remove_teacher_absence_violations()` to skip fixed subjects:
```python
# Fixed subjects should not be removed even for teacher absence
fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事"}
if assignment.subject.name in fixed_subjects:
    continue
```

### 3. Fixed Subject Enforcement Protection
Modified `FixedSubjectProtectionPolicy.enforce_critical_slots()` to temporarily disable protection when enforcing required subjects:
```python
# Temporarily disable protection during enforcement
if protection_was_enabled:
    schedule.disable_fixed_subject_protection()
try:
    # Remove and reassign
finally:
    if protection_was_enabled:
        schedule.enable_fixed_subject_protection()
```

### 4. Exchange Class Synchronization
Modified `CSPOrchestrator._synchronize_exchange_classes_early()` to check for locked cells:
```python
# Skip locked cells during synchronization
if schedule.is_locked(time_slot, exchange_class):
    continue
```

## Result
After implementing these fixes:
- input.csv loads successfully with all test period subjects preserved
- Fixed subjects (YT, 欠) remain in their correct positions
- Test periods are properly protected
- The generation completes successfully with 538 assignments

## Files Modified
1. `/src/infrastructure/repositories/csv_repository.py` - Added protection control during CSV loading
2. `/src/application/services/schedule_generation_service.py` - Skip fixed subjects in teacher absence removal
3. `/src/domain/policies/fixed_subject_protection_policy.py` - Add protection control during enforcement
4. `/src/domain/services/csp_orchestrator.py` - Check locked cells before modification