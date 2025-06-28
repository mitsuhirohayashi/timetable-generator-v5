#!/usr/bin/env python3
"""
シンプルな教師割り当てチェックスクリプト

時間割から特定の教師の授業を抽出して、不在時間と照合します。
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_manager import PathManager
from src.infrastructure.config.logging_config import LoggingConfig
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.application.services.data_loading_service import DataLoadingService


def main():
    print("=== 教師割り当ての簡易チェック ===\n")
    
    # Configure logging
    LoggingConfig.setup_logging(log_level='WARNING', simple_format=True)
    
    # Initialize
    path_manager = PathManager()
    data_loader = DataLoadingService()
    
    # 学校データとスケジュールを読み込み
    print("データを読み込み中...")
    school, _ = data_loader.load_school_data(path_manager.data_dir)
    
    # 時間割を読み込み
    csv_repo = CSVScheduleRepository(path_manager.data_dir)
    schedule = csv_repo.load("output/output.csv", school)
    
    # Follow-up情報を読み込み
    parser = EnhancedFollowUpParser(path_manager.input_dir)
    followup_result = parser.parse_file("Follow-up.csv")
    
    # 重要な不在教師をピックアップ
    check_teachers = ["井上", "北", "白石", "財津", "林田"]
    
    print("\n=== 教師別授業配置状況 ===")
    
    for teacher_name in check_teachers:
        print(f"\n{teacher_name}先生:")
        
        # この教師の授業を収集
        teacher_assignments = []
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                from src.domain.value_objects.time_slot import TimeSlot
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                        teacher_assignments.append({
                            'day': day,
                            'period': period,
                            'class': f"{class_ref.grade}年{class_ref.class_number}組",
                            'subject': assignment.subject.name
                        })
        
        # 不在時間を取得
        absences = []
        for absence in followup_result["teacher_absences"]:
            if absence.teacher_name == teacher_name:
                day = absence.day
                periods = absence.periods if absence.periods else list(range(1, 7))
                for period in periods:
                    absences.append((day, period))
        
        # 結果表示
        print(f"  授業数: {len(teacher_assignments)}コマ")
        print(f"  不在時間: {len(absences)}コマ")
        
        # 不在時間に授業があるかチェック
        violations = []
        for assignment in teacher_assignments:
            if (assignment['day'], assignment['period']) in absences:
                violations.append(assignment)
        
        if violations:
            print(f"  ❌ 不在時間の授業: {len(violations)}件")
            for v in violations:
                print(f"    - {v['day']}曜{v['period']}限 {v['class']} {v['subject']}")
        else:
            print("  ✅ 不在時間に授業なし")
        
        # 授業の詳細（最初の5件）
        if teacher_assignments:
            print("  授業配置例:")
            for a in teacher_assignments[:5]:
                print(f"    - {a['day']}曜{a['period']}限 {a['class']} {a['subject']}")
            if len(teacher_assignments) > 5:
                print(f"    ... 他{len(teacher_assignments) - 5}コマ")


if __name__ == "__main__":
    main()