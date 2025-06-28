# Duplicate Code Analysis Report

## Executive Summary

After analyzing the codebase, I've identified significant code duplication across multiple files, particularly in the scripts/ directory. The most critical duplications involve:

1. **Schedule manipulation utilities** - Same functions implemented in 16+ files
2. **CSV reading/writing patterns** - Repeated in 83+ files
3. **Constraint checking logic** - Duplicated across various fix scripts
4. **Teacher mapping loading** - Repeated in 20+ files
5. **Time slot handling** - Common patterns across many scripts

## Most Significant Duplications

### 1. Schedule Utility Functions (CRITICAL)

**Duplicated in 16+ files:**
```python
def get_cell(df, day, period):
    """Get column index for day/period"""
    # Same implementation repeated

def get_class_row(df, class_name):
    """Get row index for class"""
    # Same implementation repeated

def is_fixed_subject(subject):
    """Check if subject is fixed"""
    # Same implementation repeated
```

**Files affected:**
- scripts/fixes/systematic_swap_optimizer.py
- scripts/fixes/fix_meeting_conflicts.py
- scripts/archive/comprehensive_fixes/*.py (multiple files)
- scripts/archive/tuesday_fixes/*.py (multiple files)

**Solution:** These are already consolidated in `src/domain/utils/schedule_utils.py` but many scripts don't use it.

### 2. CSV Reading Pattern (HIGH)

**Duplicated pattern:**
```python
# Read CSV without headers
df = pd.read_csv("path/to/file.csv", header=None)
days = df.iloc[0, 1:].tolist()
periods = df.iloc[1, 1:].tolist()
```

**Files affected:** 83+ files across the codebase

**Solution:** Use the existing CSVRepository or create a simple CSV utility class.

### 3. Teacher Mapping Loading (HIGH)

**Duplicated pattern:**
```python
def load_teacher_mapping():
    mapping_df = pd.read_csv("data/config/teacher_subject_mapping.csv")
    mapping = {}
    for _, row in mapping_df.iterrows():
        # Same parsing logic repeated
    return mapping
```

**Files affected:** 20+ files

**Solution:** Already exists in infrastructure layer but not consistently used.

### 4. Constraint Checking Patterns (MEDIUM)

**Common patterns:**
- Daily duplicate checking
- Teacher conflict checking
- Fixed subject validation
- Exchange class synchronization checks

**Files affected:** Most fix scripts in scripts/fixes/

**Solution:** These should use the domain constraint classes instead of reimplementing.

### 5. Exchange Class and Grade 5 Handling (MEDIUM)

**Duplicated patterns:**
```python
# Exchange class pairs
exchange_pairs = [
    ("1年6組", "1年1組"),
    ("1年7組", "1年2組"),
    # etc...
]

# Grade 5 classes
grade5_classes = ["1年5組", "2年5組", "3年5組"]
```

**Solution:** Already in ScheduleUtils but not consistently used.

## Recommendations

### 1. Immediate Actions (High Priority)

1. **Create a ScriptUtils module** that imports from existing utilities:
   ```python
   # scripts/common/utils.py
   from src.domain.utils.schedule_utils import ScheduleUtils
   from src.infrastructure.repositories.csv_repository import CSVRepository
   
   # Re-export for easy access
   get_cell = ScheduleUtils.get_cell
   get_class_row = ScheduleUtils.get_class_row
   # etc.
   ```

2. **Refactor all fix scripts** to use the common utilities:
   - Replace inline implementations with imports
   - Remove duplicate function definitions
   - Estimated impact: 16+ files, ~1000+ lines of duplicate code removed

### 2. Medium-term Actions

1. **Consolidate CSV operations**:
   - All scripts should use CSVRepository or a simplified wrapper
   - Create a standard pattern for reading/writing schedules

2. **Standardize constraint checking**:
   - Scripts should import and use domain constraint classes
   - Avoid reimplementing constraint logic in scripts

3. **Create script templates**:
   - Standard template for fix scripts
   - Standard template for analysis scripts
   - Include proper imports and patterns

### 3. Long-term Actions

1. **Move common fix operations to services**:
   - Many fix scripts do similar operations
   - Could be consolidated into ScheduleFixerService methods

2. **Archive or remove redundant scripts**:
   - Many scripts in archive/ have similar functionality
   - Consider keeping only the most recent/best implementation

## Impact Analysis

- **Lines of code that could be removed**: 2000-3000 lines
- **Number of files affected**: 50-60 files
- **Maintenance improvement**: Significant - single source of truth for utilities
- **Bug risk reduction**: High - fixes would be applied consistently
- **Development speed**: Faster - reusable components ready to use

## Implementation Priority

1. **Week 1**: Create ScriptUtils, refactor top 10 most-used fix scripts
2. **Week 2**: Refactor remaining fix scripts, standardize CSV operations
3. **Week 3**: Archive redundant scripts, create templates
4. **Week 4**: Document patterns, create developer guide

## Example Refactoring

**Before:**
```python
# scripts/fixes/some_fix.py
def get_cell(df, day, period):
    # 10 lines of duplicate code

def get_class_row(df, class_name):
    # 5 lines of duplicate code

# Main logic using these functions
```

**After:**
```python
# scripts/fixes/some_fix.py
from scripts.common.utils import get_cell, get_class_row

# Main logic using imported functions
```

This refactoring would make the codebase much more maintainable and reduce the risk of inconsistent behavior across different scripts.