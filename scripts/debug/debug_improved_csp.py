#!/usr/bin/env python3
"""改善版CSPのデバッグ"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.application.services.schedule_generation_service import ScheduleGenerationService
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem

# サービス初期化
constraint_system = UnifiedConstraintSystem()
service = ScheduleGenerationService(constraint_system)

# パラメータチェック
print("=== パラメータチェック ===")
print(f"use_improved_csp=True, use_advanced_csp=False, use_ultrathink=False")

# 判定ロジックの確認
if False:  # use_ultrathink
    print("-> Ultrathinkが選択されます")
elif False:  # use_grade5_priority
    print("-> 5組優先配置が選択されます")
elif True:  # use_improved_csp
    print("-> 改良版CSPが選択されるべきです")
elif False:  # use_advanced_csp
    print("-> 高度なCSPが選択されます")
else:
    print("-> レガシーアルゴリズムが選択されます")

# 実際のロジック確認
print("\n=== 実際のロジック確認 ===")
print("schedule_generation_service.pyの条件分岐:")
print("if use_ultrathink: ...")
print("elif use_grade5_priority: ...")
print("elif use_improved_csp: ...")
print("elif use_advanced_csp: ...")
print("else: ...")

# 改善版CSP判定の確認
use_improved_csp = True
use_advanced_csp = False
use_ultrathink = False

print(f"\nuse_improved_csp={use_improved_csp}")
print(f"use_advanced_csp={use_advanced_csp}")
print(f"use_ultrathink={use_ultrathink}")

if use_ultrathink:
    print("結果: Ultrathinkが選択")
elif use_improved_csp:
    print("結果: 改良版CSPが選択（正しい）")
elif use_advanced_csp:
    print("結果: 高度なCSPが選択")
else:
    print("結果: レガシーが選択")