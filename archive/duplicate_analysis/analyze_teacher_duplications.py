#!/usr/bin/env python3
"""教師重複の詳細分析

現在の時間割で発生している教師重複を詳細に分析し、
5組の合同授業を除外した真の違反を特定します。

バージョン:
- v1: 基本的な教師重複検出
- v2: テスト期間と固定科目を考慮した改善版（統合済み）

使用方法:
    python analyze_teacher_duplications.py [--include-test-periods] [--include-fixed-subjects]
"""
import sys
import os
import argparse
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.domain.services.constraint_validator import ConstraintValidator
from src.infrastructure.config.path_config import path_config
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from collections import defaultdict
import re

# テスト期間の定義（Follow-up.csvから読み取れない場合の手動定義）
TEST_PERIODS = {
    ("月", 1), ("月", 2), ("月", 3),
    ("火", 1), ("火", 2), ("火", 3),
    ("水", 1), ("水", 2)
}

# 固定科目の教師（実際の教師ではない）
FIXED_SUBJECT_TEACHERS = {
    "欠課先生", "欠担当", "欠",
    "YT担当先生", "YT担当", "YT",
    "学担当", "学活担当", "学",
    "道担当", "道徳担当", "道",
    "総担当", "総合担当", "総",
    "学総担当", "学年総合担当", "学総",
    "行担当", "行事担当", "行",
    "技家担当先生", "技家担当", "技家"
}

def is_test_period(day: str, period: int) -> bool:
    """指定された時間がテスト期間かどうか判定"""
    return (day, period) in TEST_PERIODS

def is_fixed_subject_teacher(teacher_name: str) -> bool:
    """固定科目の教師かどうか判定"""
    return teacher_name in FIXED_SUBJECT_TEACHERS

def extract_grade_from_class(class_name: str) -> int:
    """クラス名から学年を抽出"""
    match = re.match(r'(\d+)年', class_name)
    return int(match.group(1)) if match else 0

def main():
    parser = argparse.ArgumentParser(description='教師重複の詳細分析')
    parser.add_argument('--include-test-periods', action='store_true',
                        help='テスト期間の重複も含める')
    parser.add_argument('--include-fixed-subjects', action='store_true',
                        help='固定科目の教師も含める')
    args = parser.parse_args()
    
    print("=== 教師重複の詳細分析 ===")
    if not args.include_test_periods:
        print("（テスト期間の重複は除外）")
    if not args.include_fixed_subjects:
        print("（固定科目の教師は除外）")
    print()
    
    # データ読み込みサービスを使用
    data_loading_service = DataLoadingService()
    absence_loader = TeacherAbsenceLoader()
    
    # 学校データを読み込む
    school, use_enhanced_features = data_loading_service.load_school_data(path_config.data_dir)
    
    # 現在の時間割を読み込む
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    schedule = schedule_repo.load("output/output.csv", school)
    
    # 5組クラスのリスト
    grade5_classes = {"1年5組", "2年5組", "3年5組"}
    
    # 交流学級ペアの定義
    exchange_pairs = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    # 教師重複を検出
    days = ["月", "火", "水", "木", "金"]
    periods = [1, 2, 3, 4, 5, 6]
    
    total_duplications = 0
    true_duplications = 0
    grade5_joint_lessons = 0
    test_period_duplications = 0
    fixed_subject_duplications = 0
    exchange_class_duplications = 0
    
    print("【教師重複の詳細】")
    print("-" * 80)
    
    for day in days:
        for period in periods:
            # 各時間枠で教師ごとにクラスを収集
            teacher_classes = defaultdict(list)
            
            for class_name, class_obj in school.classes.items():
                slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(class_name, slot)
                
                if assignment and assignment.teacher_name:
                    teacher_classes[assignment.teacher_name].append({
                        'class': class_name,
                        'subject': assignment.subject,
                        'teacher': assignment.teacher_name
                    })
            
            # 複数クラスを担当している教師を検出
            for teacher, classes in teacher_classes.items():
                if len(classes) > 1:
                    total_duplications += 1
                    
                    # 固定科目の教師をチェック
                    if is_fixed_subject_teacher(teacher):
                        fixed_subject_duplications += 1
                        if args.include_fixed_subjects:
                            print(f"{day}曜{period}限: {teacher} が複数クラスを担当（固定科目）")
                            for c in classes:
                                print(f"  - {c['class']}: {c['subject']}")
                        continue
                    
                    # テスト期間をチェック
                    if is_test_period(day, period):
                        # 同一学年で同一科目かチェック
                        grades = [extract_grade_from_class(c['class']) for c in classes]
                        subjects = [c['subject'] for c in classes]
                        
                        if len(set(grades)) == 1 and len(set(subjects)) == 1:
                            test_period_duplications += 1
                            if args.include_test_periods:
                                print(f"{day}曜{period}限: {teacher} が{len(classes)}クラスを担当（テスト巡回）")
                                for c in classes:
                                    print(f"  - {c['class']}: {c['subject']}")
                            continue
                    
                    # 5組の合同授業をチェック
                    grade5_in_classes = [c for c in classes if c['class'] in grade5_classes]
                    if len(grade5_in_classes) == 3:
                        # 3つとも5組で同じ科目なら合同授業
                        subjects = [c['subject'] for c in grade5_in_classes]
                        if len(set(subjects)) == 1:
                            grade5_joint_lessons += 1
                            continue
                    
                    # 交流学級と親学級のペアをチェック
                    is_exchange_pair = False
                    for exchange, parent in exchange_pairs.items():
                        class_names = [c['class'] for c in classes]
                        if exchange in class_names and parent in class_names:
                            # 同じ科目であることを確認
                            exchange_subject = next(c['subject'] for c in classes if c['class'] == exchange)
                            parent_subject = next(c['subject'] for c in classes if c['class'] == parent)
                            if exchange_subject == parent_subject and exchange_subject == "保健体育":
                                exchange_class_duplications += 1
                                is_exchange_pair = True
                                break
                    
                    if is_exchange_pair:
                        continue
                    
                    # それ以外は真の重複
                    true_duplications += 1
                    print(f"{day}曜{period}限: {teacher} が{len(classes)}クラスを同時に担当")
                    for c in classes:
                        print(f"  - {c['class']}: {c['subject']}")
    
    print("\n" + "=" * 80)
    print("\n【分析結果】")
    print(f"総重複検出数: {total_duplications}件")
    print(f"├─ 5組合同授業: {grade5_joint_lessons}件（正常）")
    print(f"├─ テスト巡回: {test_period_duplications}件（正常）")
    print(f"├─ 固定科目: {fixed_subject_duplications}件（システム上の表示）")
    print(f"├─ 交流学級ペア: {exchange_class_duplications}件（正常）")
    print(f"└─ 真の違反: {true_duplications}件")
    
    if true_duplications == 0:
        print("\n✅ 教師重複の制約違反はありません！")
    else:
        print(f"\n❌ {true_duplications}件の教師重複違反が見つかりました。")
        print("   上記の詳細を確認して修正してください。")

if __name__ == "__main__":
    main()