# Gym Usage Constraint Violation Analysis

## Issue Summary
On Wednesday 5th period (水曜5校時), three Grade 5 classes (1年5組, 2年5組, 3年5組) are all scheduled for PE simultaneously, violating the gym usage constraint that only allows 1 group at a time.

## Key Findings

### 1. Constraint Implementation
- The `GymUsageConstraint` class is correctly implemented
- The `check()` method properly prevents placing PE when a group is already using the gym
- The `_count_pe_groups()` method correctly groups exchange classes with their parent classes

### 2. Configuration
- The CSP config correctly lists PE ("保") in `excluded_sync_subjects`
- This means PE should NOT be synchronized across Grade 5 classes
- The config is properly loaded and used by the synchronization service

### 3. Synchronization Service
- The `SynchronizedGrade5Service` correctly checks if subjects are in `excluded_sync_subjects`
- PE should be skipped during Grade 5 synchronization
- Regular subject placement (`GreedySubjectPlacementService`) skips Grade 5 classes entirely

### 4. Actual Schedule
- All three Grade 5 classes have PE at Wednesday 5th period
- They all have the same teacher (野口), who is actually the art teacher, not PE teacher
- Each class only has 1 PE hour (but needs 2)

## Root Cause Analysis

The violation likely occurred due to one of these scenarios:

### Scenario 1: PE was placed before constraint checking was enabled
If PE was placed for Grade 5 classes early in the generation process (perhaps during initial setup or from an input file), before the constraint validator was fully initialized, the gym constraint wouldn't have been checked.

### Scenario 2: Manual synchronization override
There might be another synchronization process that runs after the main generation and synchronizes ALL Grade 5 subjects, ignoring the exclusion list.

### Scenario 3: Teacher assignment issue
The fact that all three classes have 野口 (art teacher) instead of their assigned PE teachers (財津 and 林) suggests there might be a teacher assignment bug that caused PE to be treated differently.

### Scenario 4: Initial schedule preservation
If the initial schedule had these PE assignments, they might have been preserved/locked and not checked against constraints.

## Recommendations

1. **Add debug logging** in the constraint check method to trace when and why PE assignments are made
2. **Verify constraint checking is active** throughout the entire generation process
3. **Check if initial schedules** are properly validated against constraints
4. **Ensure PE teacher assignments** are correct before placement
5. **Add a post-generation validation** that specifically checks for gym usage violations and attempts to fix them

## Technical Fix

The immediate fix would be to:
1. Move one or two of the Grade 5 PE classes to different time slots
2. Ensure they have their correct PE teachers assigned
3. Add the missing PE hours for each class (they each need 2 hours total)