#!/usr/bin/env python3
"""教師重複違反を修正"""

import logging
from collections import defaultdict
from typing import List, Dict, Optional, Tuple
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment
from src.domain.utils import parse_class_reference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# テスト期間の定義（教師の重複が許可される）
TEST_PERIODS = {
    ("月", 1), ("月", 2), ("月", 3),
    ("火", 1), ("火", 2), ("火", 3),
    ("水", 1), ("水", 2)
}

def analyze_teacher_conflicts(schedule, school):
    """教師重複を分析"""
    conflicts = []
    
    for day in ['月', '火', '水', '木', '金']:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # テスト期間はスキップ
            if (day, period) in TEST_PERIODS:
                continue
            
            teacher_assignments = defaultdict(list)
            
            # 全クラスの割り当てを確認
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_assignments[assignment.teacher.name].append({
                        'class': str(class_ref),
                        'subject': assignment.subject.name,
                        'assignment': assignment
                    })
            
            # 重複を検出
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [a for a in assignments if '5組' in a['class']]
                    if len(grade5_classes) == len(assignments) and len(grade5_classes) == 3:
                        continue
                    
                    conflicts.append({
                        'time_slot': time_slot,
                        'teacher': teacher,
                        'assignments': assignments
                    })
    
    return conflicts

def find_alternative_slots(schedule, school, class_name: str, subject_name: str, 
                         current_slot: TimeSlot, teacher_name: str) -> List[TimeSlot]:
    """代替スロットを探す"""
    alternatives = []
    subject = Subject(subject_name)
    
    for day in ['月', '火', '水', '木', '金']:
        # 同じ日に同じ科目がすでにある場合はスキップ
        has_same_subject = False
        for p in range(1, 7):
            ts = TimeSlot(day, p)
            if ts == current_slot:
                continue
            assignment = schedule.get_assignment(ts, class_name)
            if assignment and assignment.subject and assignment.subject.name == subject_name:
                has_same_subject = True
                break
        
        if has_same_subject:
            continue
        
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # テスト期間はスキップ
            if (day, period) in TEST_PERIODS:
                continue
            
            # 現在のスロットはスキップ
            if time_slot == current_slot:
                continue
            
            # スロットが空いているか確認
            class_ref = parse_class_reference(class_name)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject:
                continue
            
            # 教師が利用可能か確認
            teacher_available = True
            for c_ref in school.get_all_classes():
                if str(c_ref) == class_name:
                    continue
                other_assignment = schedule.get_assignment(time_slot, c_ref)
                if other_assignment and other_assignment.teacher and other_assignment.teacher.name == teacher_name:
                    teacher_available = False
                    break
            
            if teacher_available:
                alternatives.append(time_slot)
    
    return alternatives

def fix_teacher_conflicts(schedule, school):
    """教師重複を修正"""
    conflicts = analyze_teacher_conflicts(schedule, school)
    fixed_count = 0
    
    logger.info(f"=== 教師重複違反の修正開始 ===")
    logger.info(f"検出された違反: {len(conflicts)}件")
    
    for conflict in conflicts:
        time_slot = conflict['time_slot']
        teacher = conflict['teacher']
        assignments = conflict['assignments']
        
        logger.info(f"\n{time_slot}: {teacher}先生の重複を修正")
        logger.info(f"  重複クラス: {[a['class'] for a in assignments]}")
        
        # 最初のクラス以外を移動対象とする
        for i, assignment_info in enumerate(assignments[1:], 1):
            class_name = assignment_info['class']
            subject_name = assignment_info['subject']
            
            # 代替スロットを探す
            alternatives = find_alternative_slots(
                schedule, school, class_name, subject_name, time_slot, teacher
            )
            
            if alternatives:
                # 最適な代替スロットを選択（午前中優先）
                best_slot = min(alternatives, key=lambda s: (s.period >= 4, s.period))
                
                try:
                    # 現在の割り当てを削除
                    class_ref = parse_class_reference(class_name)
                    schedule.remove_assignment(time_slot, class_ref)
                    
                    # 新しいスロットに配置
                    new_assignment = Assignment(
                        class_ref=class_ref,
                        subject=Subject(subject_name),
                        teacher=assignment_info['assignment'].teacher
                    )
                    schedule.assign(best_slot, new_assignment)
                    
                    logger.info(f"  ✓ 修正成功: {class_name}の{subject_name}を{best_slot}に移動")
                    fixed_count += 1
                    break  # この時間の重複は解決
                    
                except Exception as e:
                    logger.error(f"  ✗ 修正失敗: {e}")
            else:
                logger.warning(f"  ⚠ {class_name}の{subject_name}の代替スロットが見つかりません")
    
    logger.info(f"\n=== 修正完了: {fixed_count}/{len(conflicts)}件 ===")
    return fixed_count

def verify_teacher_conflicts(schedule, school):
    """教師重複を検証"""
    conflicts = analyze_teacher_conflicts(schedule, school)
    
    if not conflicts:
        logger.info("✅ すべての教師重複が解決されました")
    else:
        logger.warning(f"❌ まだ{len(conflicts)}件の教師重複があります")
        for c in conflicts[:5]:
            logger.warning(f"  {c['time_slot']}: {c['teacher']}先生 - {[a['class'] for a in c['assignments']]}")

def main():
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository()
    school_repo = CSVSchoolRepository()
    
    # データ読み込み
    logger.info("データ読み込み中...")
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    
    # 交流学級同期修正済みファイルから読み込む
    from pathlib import Path
    input_file = "data/output/output_exchange_sync_fixed.csv"
    if not Path(input_file).exists():
        input_file = "data/output/output.csv"
        logger.info(f"交流学級修正済みファイルが見つからないため、{input_file}を使用")
    
    schedule = schedule_repo.load(input_file, school)
    
    # 教師重複の修正
    fixed = fix_teacher_conflicts(schedule, school)
    
    if fixed > 0:
        # 結果を保存
        output_file = "data/output/output_teacher_conflicts_fixed.csv"
        schedule_repo.save_schedule(schedule, output_file)
        logger.info(f"\n修正済み時間割を保存: {output_file}")
        
        # 検証
        logger.info("\n=== 修正後の検証 ===")
        verify_teacher_conflicts(schedule, school)

if __name__ == "__main__":
    main()