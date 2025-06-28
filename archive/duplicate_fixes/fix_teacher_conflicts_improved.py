#!/usr/bin/env python3
"""修正可能な教師重複のみを修正"""

import logging
from collections import defaultdict
from typing import List, Dict, Optional, Tuple
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment
from src.domain.utils import parse_class_reference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# テスト期間の定義
TEST_PERIODS = {
    ("月", 1), ("月", 2), ("月", 3),
    ("火", 1), ("火", 2), ("火", 3),
    ("水", 1), ("水", 2)
}

# 固定科目（移動不可）
FIXED_SUBJECTS = {'欠', 'YT', '学活', '総合', '道徳', '学総', '行', 'テスト', '技家'}

# 特殊な教師名（無視する）
SPECIAL_TEACHERS = {'欠課', 'YT担当', '学総担当', '特別活動'}

def analyze_fixable_teacher_conflicts(schedule, school):
    """修正可能な教師重複のみを分析"""
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
                    # 特殊な教師名はスキップ
                    if any(special in assignment.teacher.name for special in SPECIAL_TEACHERS):
                        continue
                        
                    teacher_assignments[assignment.teacher.name].append({
                        'class': str(class_ref),
                        'subject': assignment.subject.name if assignment.subject else '不明',
                        'assignment': assignment
                    })
            
            # 重複を検出
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [a for a in assignments if '5組' in a['class']]
                    if len(grade5_classes) == len(assignments) and len(grade5_classes) == 3:
                        continue
                    
                    # 固定科目を含む場合はスキップ
                    if any(a['subject'] in FIXED_SUBJECTS for a in assignments):
                        continue
                    
                    conflicts.append({
                        'time_slot': time_slot,
                        'teacher': teacher,
                        'assignments': assignments
                    })
    
    return conflicts

def find_empty_slots(schedule, school, class_name: str) -> List[TimeSlot]:
    """クラスの空きスロットを探す"""
    empty_slots = []
    class_ref = parse_class_reference(class_name)
    
    for day in ['月', '火', '水', '木', '金']:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # テスト期間はスキップ
            if (day, period) in TEST_PERIODS:
                continue
            
            # 6限の特殊ルール
            if period == 6:
                # 3年生以外の月曜6限は欠
                if day == '月' and not class_name.startswith('3年'):
                    continue
                # 火水金の6限はYT（3年生の月火水以外）
                if day in ['火', '水', '金']:
                    if not (class_name.startswith('3年') and day in ['火', '水']):
                        continue
            
            assignment = schedule.get_assignment(time_slot, class_ref)
            if not assignment or not assignment.subject:
                empty_slots.append(time_slot)
    
    return empty_slots

def check_daily_duplicate(schedule, class_name: str, day: str, subject_name: str) -> bool:
    """同じ日に同じ科目があるかチェック"""
    class_ref = parse_class_reference(class_name)
    
    for period in range(1, 7):
        time_slot = TimeSlot(day, period)
        assignment = schedule.get_assignment(time_slot, class_ref)
        if assignment and assignment.subject and assignment.subject.name == subject_name:
            return True
    return False

def fix_teacher_conflicts_smart(schedule, school):
    """教師重複を賢く修正"""
    conflicts = analyze_fixable_teacher_conflicts(schedule, school)
    fixed_count = 0
    swap_count = 0
    
    logger.info(f"=== 修正可能な教師重複の修正開始 ===")
    logger.info(f"検出された修正可能な違反: {len(conflicts)}件")
    
    for conflict in conflicts:
        time_slot = conflict['time_slot']
        teacher = conflict['teacher']
        assignments = conflict['assignments']
        
        logger.info(f"\n{time_slot}: {teacher}先生の重複を修正")
        class_list = [f"{a['class']}({a['subject']})" for a in assignments]
        logger.info(f"  重複クラス: {class_list}")
        
        # 5組を含む場合は、5組以外のクラスを移動対象とする
        grade5_assignments = [a for a in assignments if '5組' in a['class']]
        non_grade5_assignments = [a for a in assignments if '5組' not in a['class']]
        
        if grade5_assignments and non_grade5_assignments:
            # 5組以外を移動
            targets = non_grade5_assignments
        else:
            # 最初のクラス以外を移動対象とする
            targets = assignments[1:]
        
        for assignment_info in targets:
            class_name = assignment_info['class']
            subject_name = assignment_info['subject']
            
            # 空きスロットを探す
            empty_slots = find_empty_slots(schedule, school, class_name)
            
            # 日内重複を避けながら最適なスロットを選択
            valid_slots = []
            for slot in empty_slots:
                if not check_daily_duplicate(schedule, class_name, slot.day, subject_name):
                    # 教師が利用可能かチェック
                    teacher_available = True
                    for c_ref in school.get_all_classes():
                        if str(c_ref) == class_name:
                            continue
                        other_assignment = schedule.get_assignment(slot, c_ref)
                        if other_assignment and other_assignment.teacher and other_assignment.teacher.name == teacher:
                            teacher_available = False
                            break
                    
                    if teacher_available:
                        valid_slots.append(slot)
            
            if valid_slots:
                # 最適なスロットを選択（午前中優先）
                best_slot = min(valid_slots, key=lambda s: (s.period >= 4, s.period))
                
                try:
                    # 移動実行
                    class_ref = parse_class_reference(class_name)
                    schedule.remove_assignment(time_slot, class_ref)
                    
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
                # スワップを試みる
                logger.info(f"  空きスロットがないため、スワップを試みます")
                if try_swap(schedule, school, time_slot, class_name, subject_name, teacher):
                    swap_count += 1
                    fixed_count += 1
                    break
    
    logger.info(f"\n=== 修正完了: {fixed_count}/{len(conflicts)}件 ===")
    logger.info(f"  直接移動: {fixed_count - swap_count}件")
    logger.info(f"  スワップ: {swap_count}件")
    return fixed_count

def try_swap(schedule, school, conflict_slot: TimeSlot, class_name: str, 
             subject_name: str, teacher_name: str) -> bool:
    """授業のスワップを試みる"""
    class_ref = parse_class_reference(class_name)
    
    # スワップ候補を探す
    for day in ['月', '火', '水', '木', '金']:
        for period in range(1, 7):
            candidate_slot = TimeSlot(day, period)
            
            if candidate_slot == conflict_slot:
                continue
            
            # テスト期間や固定時間はスキップ
            if (day, period) in TEST_PERIODS:
                continue
            
            candidate_assignment = schedule.get_assignment(candidate_slot, class_ref)
            if not candidate_assignment or not candidate_assignment.subject:
                continue
            
            # 固定科目はスキップ
            if candidate_assignment.subject.name in FIXED_SUBJECTS:
                continue
            
            # 日内重複チェック
            if check_daily_duplicate(schedule, class_name, conflict_slot.day, 
                                   candidate_assignment.subject.name):
                continue
            
            # スワップ可能かチェック
            if can_swap(schedule, school, class_name, conflict_slot, candidate_slot, 
                       subject_name, candidate_assignment.subject.name, teacher_name):
                
                # スワップ実行
                logger.info(f"    スワップ: {conflict_slot}の{subject_name} ⇔ {candidate_slot}の{candidate_assignment.subject.name}")
                
                # 一時的に両方削除
                schedule.remove_assignment(conflict_slot, class_ref)
                schedule.remove_assignment(candidate_slot, class_ref)
                
                # 入れ替えて配置
                new_assignment1 = Assignment(
                    class_ref=class_ref,
                    subject=Subject(subject_name),
                    teacher=school.get_subject_teachers(Subject(subject_name))[0]
                )
                new_assignment2 = Assignment(
                    class_ref=class_ref,
                    subject=candidate_assignment.subject,
                    teacher=candidate_assignment.teacher
                )
                
                schedule.assign(candidate_slot, new_assignment1)
                schedule.assign(conflict_slot, new_assignment2)
                
                return True
    
    return False

def can_swap(schedule, school, class_name: str, slot1: TimeSlot, slot2: TimeSlot,
             subject1: str, subject2: str, teacher1: str) -> bool:
    """スワップが可能かチェック"""
    # 教師の可用性をチェック
    for c_ref in school.get_all_classes():
        if str(c_ref) == class_name:
            continue
        
        # slot2でteacher1が利用可能か
        assignment = schedule.get_assignment(slot2, c_ref)
        if assignment and assignment.teacher and assignment.teacher.name == teacher1:
            return False
    
    return True

def verify_teacher_conflicts(schedule, school):
    """修正可能な教師重複を検証"""
    conflicts = analyze_fixable_teacher_conflicts(schedule, school)
    
    if not conflicts:
        logger.info("✅ すべての修正可能な教師重複が解決されました")
    else:
        logger.warning(f"❌ まだ{len(conflicts)}件の修正可能な教師重複があります")
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
    fixed = fix_teacher_conflicts_smart(schedule, school)
    
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