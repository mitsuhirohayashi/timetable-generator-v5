#!/usr/bin/env python3
"""改善版CSPフラグのテスト"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# generate_schedule.pyのRequestを直接確認
from src.application.use_cases.request_models import GenerateScheduleRequest

# リクエスト作成
request = GenerateScheduleRequest(
    base_timetable_file="config/base_timetable.csv",
    desired_timetable_file="input/input.csv",
    followup_prompt_file="input/Follow-up.csv",
    output_file="output/output.csv",
    data_directory="data",
    max_iterations=10,
    use_advanced_csp=False,
    use_improved_csp=True,
    use_ultrathink=False
)

print("=== GenerateScheduleRequest ===")
print(f"use_improved_csp: {request.use_improved_csp}")
print(f"use_advanced_csp: {request.use_advanced_csp}")
print(f"use_ultrathink: {request.use_ultrathink}")

# schedule_generation_use_case.pyのRequestも確認
from src.application.use_cases.schedule_generation_use_case import ScheduleGenerationRequest
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem

# ダミーデータ
class DummySchool:
    pass

class DummySchedule:
    pass

constraint_system = UnifiedConstraintSystem()

# リクエスト作成
gen_request = ScheduleGenerationRequest(
    school=DummySchool(),
    initial_schedule=DummySchedule(),
    constraint_system=constraint_system,
    use_improved_csp=True,
    use_advanced_csp=False,
    use_ultrathink=False
)

print("\n=== ScheduleGenerationRequest ===")
print(f"use_improved_csp: {gen_request.use_improved_csp}")
print(f"use_advanced_csp: {gen_request.use_advanced_csp}")
print(f"use_ultrathink: {gen_request.use_ultrathink}")