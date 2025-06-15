# Timetable Generation Program Analysis

## Executive Summary
The program is incorrectly modifying fixed subjects and arbitrarily adding events (行事) where they shouldn't exist. The human-created timetable preserves the original structure while the program output shows significant deviations.

## Key Issues Identified

### 1. Fixed Subjects Being Modified

#### Monday Period 6 - "欠" (Absence) Changed to "行" (Event)
- **Input**: All classes have "欠" (absence) on Monday period 6
- **Program Output**: Changed to "行" (event) for all classes
- **Human Output**: Correctly maintains "欠" (absence)

This is a critical error - Monday period 6 should always be marked as absent/free period.

#### Integrated Studies (総合) Being Replaced
- **Input**: Classes like 2-1, 2-2, 2-3 have "学総" (integrated studies) scheduled
- **Program Output**: Many of these are replaced with "行" (event)
- **Human Output**: Preserves all "総合" slots correctly

### 2. Arbitrary Event (行事) Additions

The program is massively overusing "行" (event) as a subject:

#### Event Count Comparison
- **Input Data**: Minimal events (mostly special slots)
- **Program Output**: 176 instances of "行" across the timetable
- **Human Output**: Only necessary events preserved from input

The program appears to use "行" as a default filler when it can't assign other subjects.

### 3. Pattern Analysis

#### Fixed Subjects That Should Never Change:
1. **欠** (Absence) - Fixed free periods
2. **YT** - Fixed activity period
3. **道** (Moral Education) - Fixed moral education slots
4. **学** (Homeroom) - Fixed homeroom activities
5. **総合** (Integrated Studies) - Fixed project time

#### Human Scheduler Patterns:
1. Preserves all fixed subjects without modification
2. Only modifies regular academic subjects (国語, 数学, 理科, etc.)
3. Respects teacher availability and constraints
4. Maintains balanced subject distribution

#### Program Issues:
1. Treats fixed subjects as interchangeable
2. Uses "行" (event) as a catch-all solution
3. Doesn't distinguish between modifiable and non-modifiable slots
4. Violates the basic constraint of preserving special subjects

## Specific Examples

### Example 1: Class 1-1 Monday
- **Input**: 理,家,数,社,国,欠
- **Program**: 数,国,社,理,音,行 (changed 欠→行)
- **Human**: 理,家,数,社,国,欠 (preserved correctly)

### Example 2: Class 2-1 Saturday
- **Input**: 技,英,学総,学総,国,数
- **Program**: 数,理,行,保,国,理 (changed 学総→行)
- **Human**: 技,英,学総,学総,国,数 (preserved correctly)

## Root Causes

1. **Constraint Definition**: The program lacks proper constraints for fixed subjects
2. **Subject Classification**: No distinction between regular and special subjects
3. **Default Behavior**: Using "行" as a fallback instead of maintaining original
4. **Validation Logic**: Missing checks for protected time slots

## Recommendations

### 1. Add Fixed Subject Constraints
```python
FIXED_SUBJECTS = {'欠', 'YT', '道', '学', '総合', '行事'}
# These should never be changed during generation
```

### 2. Implement Subject Type Classification
```python
class SubjectType(Enum):
    ACADEMIC = "academic"      # 国,数,理,社,英,etc - can be rescheduled
    FIXED_SPECIAL = "fixed"    # 欠,YT,道,学,総合 - cannot be changed
    FLEXIBLE_SPECIAL = "flex"  # 音,美,体,技,家 - limited rescheduling
```

### 3. Modify Generation Logic
- Before assigning any subject, check if current slot has a fixed subject
- If fixed subject exists, preserve it
- Only modify slots with academic subjects
- Never use "行" as a filler - maintain original subject if no valid swap

### 4. Add Validation Rules
- Count of each fixed subject should remain constant
- Monday period 6 must always be "欠"
- YT periods must remain in their original slots
- 総合 (integrated studies) must not be replaced

## Conclusion

The program needs fundamental changes to respect fixed subjects and avoid arbitrary event additions. The human scheduler's approach of preserving special subjects while only optimizing regular academic subjects should be the model for improvement.