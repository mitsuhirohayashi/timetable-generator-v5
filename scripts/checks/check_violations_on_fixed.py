#!/usr/bin/env python3
"""Grade5修正後の違反をチェック"""

import subprocess
import sys

# 固定されたファイルで違反チェックを実行
result = subprocess.run([
    sys.executable, 
    "scripts/analysis/check_violations.py",
    "--input", "data/output/output_grade5_sync_fixed.csv"
], capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)