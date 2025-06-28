#!/usr/bin/env python3
"""
Follow-up.csv情報の読み込みと適用を検証するテストスクリプト

Follow-up.csvから読み込まれた教師不在情報が正しく時間割に反映されているかを確認します。
"""

import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_manager import PathManager
from src.infrastructure.config.logging_config import LoggingConfig
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository


def check_followup_loading():
    """Follow-up情報の読み込み状況を確認"""
    print("=== Follow-up.csv読み込みテスト ===\n")
    
    # Configure logging
    LoggingConfig.setup_logging(log_level='INFO', simple_format=True)
    
    # Initialize
    path_manager = PathManager()
    
    # Step 1: Follow-up.csvを解析
    print("Step 1: Follow-up.csvを解析中...")
    parser = EnhancedFollowUpParser(path_manager.input_dir)
    result = parser.parse_file("Follow-up.csv")
    
    if result["parse_success"]:
        print("✅ Follow-up.csv解析成功\n")
        
        # 教師不在情報を表示
        if result["teacher_absences"]:
            print(f"教師不在情報: {len(result['teacher_absences'])}件")
            for absence in result["teacher_absences"]:
                periods_str = "終日" if not absence.periods else f"{','.join(map(str, absence.periods))}限"
                print(f"  - {absence.teacher_name}: {absence.day}曜{periods_str} ({absence.reason})")
            print()
        
        # 会議情報を表示
        if result["meetings"]:
            print(f"会議情報: {len(result['meetings'])}件")
            for meeting in result["meetings"]:
                print(f"  - {meeting.day}曜{meeting.period}限: {meeting.meeting_name}")
            print()
    else:
        print("❌ Follow-up.csv解析失敗\n")
        return
    
    # Step 2: 教師不在情報をTeacherAbsenceLoaderに反映
    print("Step 2: 教師不在情報をローダーに反映中...")
    absence_loader = TeacherAbsenceLoader()
    absence_loader.update_absences_from_parsed_data(result["teacher_absences"])
    
    # 不在情報を確認
    print("\n登録された教師不在:")
    for teacher, absences in absence_loader.teacher_absences.items():
        print(f"  {teacher}: {len(absences)}時間")
        for day, period in sorted(absences):
            print(f"    - {day}曜{period}限")
    
    # Step 3: 生成された時間割を読み込んで検証
    print("\nStep 3: 時間割での教師不在チェック...")
    output_path = path_manager.get_output_path("output.csv")
    
    if output_path.exists():
        # CSVを直接読み込んで教師情報を抽出
        import csv
        teacher_schedule = {}  # teacher -> [(day, period, class)]
        
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)  # ヘッダー行
            days_row = next(reader)  # 曜日行
            periods_row = next(reader)  # 時限行
            
            # 曜日と時限のマッピングを作成
            day_period_map = []
            for i in range(1, len(days_row)):
                if days_row[i] and periods_row[i] and periods_row[i].isdigit():
                    day_period_map.append((days_row[i], int(periods_row[i])))
            
            # 各クラスの時間割を読み込み
            for row in reader:
                if not row or not row[0]:
                    continue
                    
                class_name = row[0]
                for i, subject in enumerate(row[1:]):
                    if i < len(day_period_map) and subject:
                        day, period = day_period_map[i]
                        
                        # 科目から教師を推定（実際にはteacher_subject_mapping.csvを参照すべき）
                        # ここでは簡易的にチェック
                        teacher_subjects = {
                            "井上": ["数"],
                            "北": ["社"],
                            "財津": ["家", "保"],
                            "永山": ["保"],
                            "林田": ["英"],
                            "白石": ["理"],
                            "森山": ["数"],
                            "小野塚": ["国"],
                            "梶永": ["数"]
                        }
                        
                        for teacher, subjects in teacher_subjects.items():
                            if subject in subjects:
                                if teacher not in teacher_schedule:
                                    teacher_schedule[teacher] = []
                                teacher_schedule[teacher].append((day, period, class_name, subject))
        
        # 教師不在違反をチェック
        violations = []
        for teacher, schedule_items in teacher_schedule.items():
            if teacher in absence_loader.teacher_absences:
                for day, period, class_name, subject in schedule_items:
                    if (day, period) in absence_loader.teacher_absences[teacher]:
                        violations.append(f"{teacher}先生: {day}曜{period}限 {class_name} {subject} (不在時間に配置)")
        
        if violations:
            print(f"\n❌ 教師不在違反: {len(violations)}件")
            for v in violations:
                print(f"  - {v}")
        else:
            print("\n✅ 教師不在違反なし")
    else:
        print("⚠️ output.csvが見つかりません")
    
    # Summary
    print("\n=== 検証結果まとめ ===")
    print(f"1. Follow-up.csv読み込み: {'成功' if result['parse_success'] else '失敗'}")
    print(f"2. 教師不在情報: {len(result['teacher_absences'])}件")
    print(f"3. 会議情報: {len(result['meetings'])}件")
    print(f"4. 教師不在違反: {len(violations) if 'violations' in locals() else '未検証'}件")


if __name__ == "__main__":
    check_followup_loading()