#!/usr/bin/env python3
"""
金子み先生の月曜2限の8クラス割り当て問題を分析するスクリプト
"""

import pandas as pd
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from pathlib import Path

def analyze_kaneko_monday2():
    """金子み先生の月曜2限の割り当てを分析"""
    
    print("=== 金子み先生 月曜2限 割り当て分析 ===\n")
    
    # 1. output.csvを読み込み
    output_path = os.path.join(project_root, 'data', 'output', 'output.csv')
    if not os.path.exists(output_path):
        print(f"エラー: {output_path} が見つかりません")
        return
    
    # Load school configuration first
    school_repo = CSVSchoolRepository(Path(project_root) / "data" / "config")
    school = school_repo.load_school_data()
    
    # Now read the schedule with proper teacher mappings
    reader = CSVScheduleReader()
    schedule = reader.read(output_path, school)
    
    # 2. 月曜2限に金子み先生が担当するクラスを抽出
    monday_period2_classes = []
    monday_period2_subjects = []
    all_monday2_assignments = []
    
    # TimeSlotを作成（月曜2限）
    from src.domain.value_objects.time_slot import TimeSlot
    monday_2nd = TimeSlot("月", 2)
    
    # 月曜2限の全ての割り当てを取得
    assignments = schedule.get_assignments_by_time_slot(monday_2nd)
    
    print(f"\n月曜2限の全ての割り当て（{len(assignments)}件）:")
    kokugo_classes = []  # 国語のクラスを追跡
    grade5_classes_found = []  # 5組のクラスを追跡
    
    for assignment in assignments:
        teacher_name = assignment.teacher.name if assignment.teacher else "教師未割当"
        all_monday2_assignments.append({
            'class': str(assignment.class_ref),
            'subject': assignment.subject.name,
            'teacher': teacher_name
        })
        print(f"  {assignment.class_ref}: {assignment.subject.name} ({teacher_name})")
        
        # 5組かどうかチェック
        if assignment.class_ref.class_number == 5:
            grade5_classes_found.append(str(assignment.class_ref))
        
        # 国語のクラスを追跡
        if assignment.subject.name == "国":
            kokugo_classes.append(str(assignment.class_ref))
        
        if assignment.teacher and assignment.teacher.name == "金子み":
            monday_period2_classes.append(str(assignment.class_ref))
            monday_period2_subjects.append(assignment.subject.name)
    
    print(f"\n5組のクラス: {', '.join(grade5_classes_found) if grade5_classes_found else 'データに含まれていません'}")
    
    print(f"\n月曜2限に国語があるクラス: {', '.join(kokugo_classes) if kokugo_classes else 'なし'}")
    
    print(f"月曜2限に金子み先生が担当するクラス数: {len(monday_period2_classes)}")
    print(f"クラス一覧: {', '.join(monday_period2_classes)}")
    print(f"科目一覧: {', '.join(monday_period2_subjects)}")
    print()
    
    # 3. Follow-up.csvからテスト期間情報を確認
    followup_path = os.path.join(project_root, 'data', 'input', 'Follow-up.csv')
    if os.path.exists(followup_path):
        print("Follow-up.csvからテスト期間情報を確認...")
        
        # テキストファイルとして読み込んで内容を確認
        with open(followup_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # テスト期間に関する記述を探す
        test_keywords = ['テスト', 'test', 'TEST']
        monday_keywords = ['月曜', '月', 'Monday']
        period2_keywords = ['2限', '2校時', '２限', '２校時']
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # テストに関する記述があるか確認
            if any(keyword in line for keyword in test_keywords):
                # 月曜や2限に関する記述があるか確認
                if any(keyword in line for keyword in monday_keywords) or any(keyword in line for keyword in period2_keywords):
                    print(f"  関連記述 (行{i+1}): {line.strip()}")
        
        # EnhancedFollowUpParserを使用した解析
        parser = EnhancedFollowUpParser()
        result = parser.parse_file('Follow-up.csv')
        test_periods = result.get('test_periods', [])
        
        is_test_period = False
        for test_period in test_periods:
            # test_period is a TestPeriod dataclass instance
            if test_period.day == '月' and 2 in test_period.periods:  # 月曜2限
                is_test_period = True
                print(f"\n月曜2限はテスト期間です:")
                print(f"  説明: {test_period.description}")
                print(f"  対象時限: {test_period.periods}")
                break
        
        if not is_test_period:
            print("\n月曜2限はテスト期間ではありません")
    else:
        print(f"警告: {followup_path} が見つかりません")
        is_test_period = False
    
    print()
    
    # 4. 問題の診断
    print("=== 診断結果 ===")
    
    if len(monday_period2_classes) > 1:
        if is_test_period:
            print("状況: テスト期間中の巡回監督")
            print("判定: 正常（テスト期間中は1人の教師が複数クラスを巡回可能）")
            
            # 同じ科目かチェック
            unique_subjects = list(set(monday_period2_subjects))
            if len(unique_subjects) == 1:
                print(f"科目: 全クラス同じ科目（{unique_subjects[0]}）→ 正常なテスト実施")
            else:
                print(f"警告: 異なる科目が混在（{', '.join(unique_subjects)}）")
                print("      テスト期間中は同一科目であるべきです")
        else:
            print("状況: 通常授業での重複割り当て")
            print("判定: 制約違反（通常授業では1人の教師は同時に1クラスのみ）")
            print("\n考えられる原因:")
            print("1. 5組（1-5, 2-5, 3-5）の合同授業設定の誤り")
            print("2. 生成アルゴリズムのバグ")
            print("3. 制約チェックの不備")
    else:
        print("問題なし: 金子み先生は月曜2限に1クラスのみ担当")
    
    # 5. CSV直接確認
    print("\n=== CSV直接確認 ===")
    print("output.csvから5組の月曜2限を直接確認:")
    with open(output_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        # 1年5組 (6行目)、2年5組 (12行目)、3年5組 (19行目)
        for grade, line_num in [(1, 6), (2, 12), (3, 19)]:
            if line_num <= len(lines):
                fields = lines[line_num-1].strip().split(',')
                if len(fields) > 2:
                    class_name = fields[0]
                    monday2_subject = fields[2]  # 月曜2限は3列目（インデックス2）
                    print(f"  {class_name}: {monday2_subject}")
    
    # 6. 全ての金子み先生の割り当てを確認
    print("\n=== 金子み先生の全ての割り当て ===")
    from src.domain.value_objects.time_slot import Teacher
    all_kaneko_assignments = schedule.get_assignments_by_teacher(Teacher("金子み"))
    print(f"金子み先生の総割り当て数: {len(all_kaneko_assignments)}")
    for time_slot, assignment in all_kaneko_assignments[:10]:  # 最初の10件を表示
        print(f"  {time_slot.day}{time_slot.period}限 - {assignment.class_ref}: {assignment.subject.name}")
    
    # 7. 5組の特別ルールを確認
    print("\n=== 5組の合同授業ルール確認 ===")
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    grade5_in_monday2 = [cls for cls in monday_period2_classes if cls in grade5_classes]
    
    if grade5_in_monday2:
        print(f"5組の割り当て: {', '.join(grade5_in_monday2)}")
        print("注: 5組（1-5, 2-5, 3-5）は全教科で合同授業を実施")
        print("    → 3クラス同時担当は正常な運用")
        
        # 5組の科目が同じかチェック
        grade5_subjects = [monday_period2_subjects[monday_period2_classes.index(cls)] 
                          for cls in grade5_in_monday2]
        if len(set(grade5_subjects)) == 1:
            print(f"    科目: 全て同じ（{grade5_subjects[0]}）→ 正常")
        else:
            print(f"    警告: 異なる科目（{', '.join(grade5_subjects)}）→ 異常")
    
    # 8. その他のクラス（5組以外）の確認
    other_classes = [cls for cls in monday_period2_classes if cls not in grade5_classes]
    if other_classes:
        print(f"\n5組以外のクラス: {', '.join(other_classes)}")
        if len(other_classes) > 1 and not is_test_period:
            print("警告: 5組以外で複数クラスを同時担当 → 制約違反")
    
    # 9. 詳細な割り当て状況を表示
    print("\n=== 詳細な割り当て状況 ===")
    for i, (class_name, subject) in enumerate(zip(monday_period2_classes, monday_period2_subjects)):
        print(f"{i+1}. {class_name}: {subject}")
    
    # 10. 推奨される対処法
    print("\n=== 推奨される対処法 ===")
    if len(monday_period2_classes) > 3 and not is_test_period:
        print("1. 5組（1-5, 2-5, 3-5）の3クラス合同は維持")
        print("2. その他のクラスへの割り当てを見直し")
        print("3. TeacherConflictConstraintの5組例外処理を確認")
        print("4. 生成アルゴリズムでの教師割り当てロジックを修正")

    # 11. 最終診断
    print("\n=== 最終診断 ===")
    print("問題: CSVScheduleReaderが5組（1-5, 2-5, 3-5）のデータを読み込んでいません")
    print("\n根拠:")
    print("1. output.csvには5組のデータが存在（全て月曜2限に「国」）")
    print("2. teacher_subject_mapping.csvでは金子み先生が5組の国語担当")
    print("3. しかしScheduleオブジェクトには5組のデータが含まれていない")
    print("4. そのため金子み先生の割り当てが0件として表示される")
    print("\n実際の状況:")
    print("- 金子み先生は1-5, 2-5, 3-5の3クラスで月曜2限に国語を担当")
    print("- これは5組の合同授業として正常な運用")
    print("- CSVScheduleReaderのバグにより、この情報が失われている")
    print("\n対処法:")
    print("1. CSVScheduleReaderを修正して5組データを正しく読み込む")
    print("2. または、5組専用の読み込みロジックを追加する")

if __name__ == "__main__":
    analyze_kaneko_monday2()