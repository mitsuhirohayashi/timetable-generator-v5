#!/usr/bin/env python3
"""修正可能な教師重複を分析"""

import logging
from collections import defaultdict
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# テスト期間の定義
TEST_PERIODS = {
    ("月", 1), ("月", 2), ("月", 3),
    ("火", 1), ("火", 2), ("火", 3),
    ("水", 1), ("水", 2)
}

# 固定科目（移動不可）
FIXED_SUBJECTS = {'欠', 'YT', '学活', '総合', '道徳', '学総', '行', 'テスト'}

def analyze_fixable_conflicts(schedule, school):
    """修正可能な教師重複を分析"""
    all_conflicts = []
    fixable_conflicts = []
    unfixable_conflicts = []
    
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
                    
                    conflict = {
                        'time_slot': time_slot,
                        'teacher': teacher,
                        'assignments': assignments
                    }
                    
                    all_conflicts.append(conflict)
                    
                    # 固定科目を含むかチェック
                    has_fixed = any(a['subject'] in FIXED_SUBJECTS for a in assignments)
                    if has_fixed:
                        unfixable_conflicts.append(conflict)
                    else:
                        fixable_conflicts.append(conflict)
    
    return all_conflicts, fixable_conflicts, unfixable_conflicts

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
    
    schedule = schedule_repo.load(input_file, school)
    
    # 修正可能な教師重複を分析
    all_conflicts, fixable, unfixable = analyze_fixable_conflicts(schedule, school)
    
    logger.info(f"\n=== 教師重複違反の分析 ===")
    logger.info(f"総違反数: {len(all_conflicts)}件")
    logger.info(f"修正可能: {len(fixable)}件")
    logger.info(f"修正不可（固定科目）: {len(unfixable)}件")
    
    if fixable:
        logger.info(f"\n=== 修正可能な違反 ===")
        for conflict in fixable[:10]:  # 最初の10件
            logger.info(f"{conflict['time_slot']}: {conflict['teacher']}先生")
            for a in conflict['assignments']:
                logger.info(f"  - {a['class']}: {a['subject']}")
    
    if unfixable:
        logger.info(f"\n=== 修正不可能な違反（固定科目） ===")
        # 教師別に集計
        teacher_counts = defaultdict(int)
        for conflict in unfixable:
            teacher_counts[conflict['teacher']] += 1
        
        for teacher, count in sorted(teacher_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"{teacher}先生: {count}件")
    
    # 特殊な教師の確認
    special_teachers = ['欠課', 'YT担当', '特別活動']
    logger.info(f"\n=== 特殊な教師名の確認 ===")
    for conflict in all_conflicts:
        if any(special in conflict['teacher'] for special in special_teachers):
            logger.info(f"{conflict['teacher']}先生が検出されました")

if __name__ == "__main__":
    main()