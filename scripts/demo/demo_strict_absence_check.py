#!/usr/bin/env python3
"""
厳格な教師不在チェックオプションのデモスクリプト
"""
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader


def demo_normal_mode():
    """通常モードでの読み込み"""
    print("\n" + "="*80)
    print("通常モード（教師不在チェックなし）")
    print("="*80)
    
    reader = CSVScheduleReader(strict_absence_check=False)
    input_path = project_root / "data" / "input" / "input.csv"
    
    schedule = reader.read(input_path)
    
    # 特定の配置をチェック
    from src.domain.value_objects.time_slot import TimeSlot, ClassReference
    
    checks = [
        ("1年2組", "月", 1, "北先生の社会（振休中）"),
        ("3年3組", "月", 6, "北先生のYT（振休中）"),
        ("1年6組", "木", 4, "財津先生の道徳（年休中）"),
    ]
    
    for class_name, day, period, desc in checks:
        # クラス参照を作成
        import re
        match = re.match(r'(\d+)年(\d+)組', class_name)
        if match:
            class_ref = ClassReference(int(match.group(1)), int(match.group(2)))
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            
            if assignment:
                teacher_name = assignment.teacher.name if assignment.teacher else "なし"
                print(f"✅ {time_slot} {class_name}: {assignment.subject.name} (教師: {teacher_name}) - {desc}")
            else:
                print(f"❌ {time_slot} {class_name}: 空き - {desc}")


def demo_strict_mode():
    """厳格モードでの読み込み"""
    print("\n" + "="*80)
    print("厳格モード（教師不在チェックあり）")
    print("="*80)
    
    # Follow-up.csvから教師不在情報を読み込み
    data_dir = project_root / "data"
    followup_parser = EnhancedFollowUpParser(data_dir / "input")
    followup_result = followup_parser.parse_file()
    
    # 教師不在情報を表示
    print("\n教師不在情報:")
    for absence in followup_result.get("teacher_absences", []):
        periods_str = "終日" if not absence.periods else f"{','.join(map(str, absence.periods))}時限"
        print(f"  - {absence.teacher_name}: {absence.day}曜{periods_str} ({absence.reason})")
    
    # TeacherAbsenceLoaderを更新（これが重要）
    absence_loader = TeacherAbsenceLoader()
    absence_loader.update_absences_from_parsed_data(followup_result.get("teacher_absences", []))
    
    # 厳格モードで読み込み
    reader = CSVScheduleReader(strict_absence_check=True)
    input_path = project_root / "data" / "input" / "input.csv"
    
    print("\n読み込み中...")
    schedule = reader.read(input_path)
    
    # 同じ配置をチェック
    from src.domain.value_objects.time_slot import TimeSlot, ClassReference
    
    checks = [
        ("1年2組", "月", 1, "北先生の社会（振休中）"),
        ("3年3組", "月", 6, "北先生のYT（振休中）"),
        ("1年6組", "木", 4, "財津先生の道徳（年休中）"),
    ]
    
    print("\n配置結果:")
    for class_name, day, period, desc in checks:
        # クラス参照を作成
        import re
        match = re.match(r'(\d+)年(\d+)組', class_name)
        if match:
            class_ref = ClassReference(int(match.group(1)), int(match.group(2)))
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            
            if assignment:
                teacher_name = assignment.teacher.name if assignment.teacher else "なし"
                print(f"✅ {time_slot} {class_name}: {assignment.subject.name} (教師: {teacher_name}) - {desc} [読み込まれた]")
            else:
                print(f"❌ {time_slot} {class_name}: 空き - {desc} [スキップされた]")


def main():
    """メイン処理"""
    print("教師不在厳格チェックオプションのデモ")
    print("="*80)
    
    # 通常モード
    demo_normal_mode()
    
    # 厳格モード
    demo_strict_mode()
    
    print("\n" + "="*80)
    print("まとめ:")
    print("- 通常モード: 教師不在でも読み込む（後で違反として検出）")
    print("- 厳格モード: 教師不在の授業は読み込み時にスキップ")
    print("\n使用方法:")
    print("  reader = CSVScheduleReader(strict_absence_check=True)")
    print("="*80)


if __name__ == "__main__":
    main()