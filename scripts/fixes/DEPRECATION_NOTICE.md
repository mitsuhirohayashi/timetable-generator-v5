# Deprecation Notice - Fix Scripts

The following violation fix scripts have been **deprecated** and replaced by the unified violation fixer:

## Deprecated Scripts:
- `fix_all_violations.py` 
- `fix_all_violations_v2.py`
- `fix_all_violations_ultrathink.py`
- `comprehensive_fix_all_violations.py`

## Replacement:
Use `unified_violation_fixer.py` instead, which combines the best features from all deprecated scripts.

### Usage:
```bash
python3 scripts/fixes/unified_violation_fixer.py input.csv output.csv
```

### Key Improvements:
1. **Single source of truth** - One script to maintain instead of four
2. **Best algorithms** - Combines the most effective fixes from each version
3. **Cleaner code** - Simplified and well-documented implementation
4. **Better performance** - Optimized violation detection and fixing
5. **Comprehensive coverage** - Handles all violation types:
   - Exchange class synchronization
   - Jiritsu (自立) activity constraints
   - Gym usage conflicts
   - Daily duplicate subjects
   - Grade 5 synchronization
   - Empty slot filling

## Migration Timeline:
- **Immediate**: Start using `unified_violation_fixer.py` for new workflows
- **Next 30 days**: Update any scripts that depend on deprecated fixers
- **After 30 days**: Deprecated scripts will be moved to an archive directory

## For Script Maintainers:
If you have scripts that depend on the deprecated fixers, please update them to use the unified fixer. The API is similar but simplified:

```python
from unified_violation_fixer import UnifiedViolationFixer

fixer = UnifiedViolationFixer()
fixer.fix_all_violations('input.csv', 'output.csv')
```