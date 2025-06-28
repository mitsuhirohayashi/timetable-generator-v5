#!/usr/bin/env python3
"""
教師不在情報の詳細検証スクリプト

Follow-up.csvの教師不在情報と実際の時間割を詳細に照合します。
"""

import sys
from pathlib import Path
import csv
import logging
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_manager import PathManager
from src.infrastructure.config.logging_config import LoggingConfig
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader


def load_teacher_mapping(path_manager):
    """教師と科目のマッピングを読み込む"""
    mapping_path = path_manager.get_config_path("teacher_subject_mapping.csv")
    teacher_subject_map = defaultdict(list)
    
    if mapping_path.exists():
        with open(mapping_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                teacher = row.get('教員名', '').strip()
                subject = row.get('教科', '').strip()
                if teacher and subject:
                    if subject not in teacher_subject_map[teacher]:
                        teacher_subject_map[teacher].append(subject)
    
    return teacher_subject_map


def parse_timetable(output_path):
    """時間割CSVをパースして教師割り当てを抽出"""
    teacher_assignments = defaultdict(list)  # teacher -> [(day, period, class, subject)]
    
    with open(output_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        # ヘッダー行をスキップ
        next(reader)  # 基本時間割
        
        # 曜日と時限の行を読み込み
        days_row = next(reader)
        periods_row = next(reader)
        
        # 曜日と時限のマッピングを作成
        time_slots = []
        for i in range(1, len(days_row)):
            if days_row[i] and periods_row[i] and periods_row[i].isdigit():
                time_slots.append((days_row[i], int(periods_row[i])))
        
        # 各クラスの時間割を読み込み
        for row in reader:
            if not row or not row[0]:
                continue
            
            class_name = row[0]
            
            # 各時限の科目を処理
            for i, subject in enumerate(row[1:]):
                if i < len(time_slots) and subject and subject.strip():
                    day, period = time_slots[i]
                    # 科目と担当教師のマッピングは別途必要
                    # ここでは科目のみを記録
                    teacher_assignments['subjects'].append({
                        'day': day,
                        'period': period,
                        'class': class_name,
                        'subject': subject.strip()
                    })
    
    return teacher_assignments


def verify_absence_violations():
    """教師不在違反を詳細に検証"""
    print("=== 教師不在情報の詳細検証 ===\n")
    
    # Configure logging
    LoggingConfig.setup_logging(log_level='WARNING', simple_format=True)
    
    # Initialize
    path_manager = PathManager()
    
    # Step 1: Follow-up.csvから教師不在情報を読み込み
    print("Step 1: Follow-up.csvから教師不在情報を読み込み...")
    parser = EnhancedFollowUpParser(path_manager.input_dir)
    result = parser.parse_file("Follow-up.csv")
    
    if not result["parse_success"]:
        print("❌ Follow-up.csv解析失敗")
        return
    
    # 教師不在情報を整理
    teacher_absence_map = defaultdict(list)
    for absence in result["teacher_absences"]:
        teacher = absence.teacher_name
        day = absence.day
        periods = absence.periods if absence.periods else list(range(1, 7))
        for period in periods:
            teacher_absence_map[teacher].append((day, period))
    
    print(f"✅ 教師不在情報を{len(teacher_absence_map)}名分読み込みました\n")
    
    # Step 2: 教師と科目のマッピングを読み込み
    print("Step 2: 教師と科目のマッピングを読み込み...")
    teacher_subject_map = load_teacher_mapping(path_manager)
    print(f"✅ 教師-科目マッピングを{len(teacher_subject_map)}名分読み込みました\n")
    
    # Step 3: 時間割を読み込み
    print("Step 3: 時間割を読み込み...")
    output_path = path_manager.get_output_path("output.csv")
    
    if not output_path.exists():
        print("❌ output.csvが見つかりません")
        return
    
    assignments = parse_timetable(output_path)
    subject_assignments = assignments.get('subjects', [])
    print(f"✅ 時間割から{len(subject_assignments)}個の授業を読み込みました\n")
    
    # Step 4: 教師不在違反をチェック
    print("Step 4: 教師不在違反をチェック...")
    violations = []
    
    # 科目から教師を逆引き
    subject_to_teachers = defaultdict(list)
    for teacher, subjects in teacher_subject_map.items():
        for subject in subjects:
            subject_to_teachers[subject].append(teacher)
    
    # 各授業について教師不在をチェック
    for assignment in subject_assignments:
        day = assignment['day']
        period = assignment['period']
        class_name = assignment['class']
        subject = assignment['subject']
        
        # この科目を担当可能な教師を取得
        possible_teachers = subject_to_teachers.get(subject, [])
        
        # 各教師について不在チェック
        for teacher in possible_teachers:
            if teacher in teacher_absence_map:
                if (day, period) in teacher_absence_map[teacher]:
                    violations.append({
                        'teacher': teacher,
                        'day': day,
                        'period': period,
                        'class': class_name,
                        'subject': subject,
                        'reason': '教師不在時間に授業が配置されている'
                    })
    
    # 結果表示
    print("\n=== 検証結果 ===")
    if violations:
        print(f"❌ 教師不在違反: {len(violations)}件\n")
        for v in violations:
            print(f"  {v['teacher']}先生: {v['day']}曜{v['period']}限 {v['class']} {v['subject']}")
            print(f"    → {v['reason']}")
    else:
        print("✅ 教師不在違反は検出されませんでした")
    
    # 不在教師の授業状況を確認
    print("\n=== 不在教師の授業状況 ===")
    for teacher, absences in sorted(teacher_absence_map.items()):
        if teacher in teacher_subject_map:
            subjects = teacher_subject_map[teacher]
            print(f"\n{teacher}先生 (担当: {', '.join(subjects)})")
            print(f"  不在時間: {len(absences)}コマ")
            for day, period in sorted(absences)[:5]:  # 最初の5件のみ表示
                print(f"    - {day}曜{period}限")
            if len(absences) > 5:
                print(f"    ... 他{len(absences) - 5}コマ")


if __name__ == "__main__":
    verify_absence_violations()