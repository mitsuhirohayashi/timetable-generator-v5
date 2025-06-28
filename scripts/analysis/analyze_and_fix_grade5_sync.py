#!/usr/bin/env python3
"""5組同期問題の分析と修正"""

import logging
from collections import defaultdict
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment
from src.domain.utils import parse_class_reference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_grade5_sync_violations(schedule, school):
    """5組の同期違反を分析"""
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    violations = []
    
    for day in ['月', '火', '水', '木', '金']:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # 各5組クラスの科目を取得
            subjects = {}
            for class_name in grade5_classes:
                class_ref = parse_class_reference(class_name)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    subjects[class_name] = assignment.subject.name
                else:
                    subjects[class_name] = "空き"
            
            # 全て同じでない場合は違反
            unique_subjects = set(subjects.values())
            if len(unique_subjects) > 1:
                violations.append({
                    'time': f"{day}曜{period}限",
                    'subjects': subjects,
                    'unique': unique_subjects
                })
    
    return violations

def fix_grade5_sync_violations(schedule, school):
    """5組の同期違反を修正"""
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    fixed_count = 0
    
    logger.info("=== 5組同期違反の修正開始 ===")
    
    violations = analyze_grade5_sync_violations(schedule, school)
    logger.info(f"検出された違反: {len(violations)}件")
    
    for violation in violations:
        time_str = violation['time']
        day = time_str[0]
        period = int(time_str[2])
        time_slot = TimeSlot(day, period)
        
        logger.info(f"\n{time_str}の違反を修正:")
        logger.info(f"  現在の状態: {violation['subjects']}")
        
        # 最も多い科目を選択（空き以外を優先）
        subject_counts = defaultdict(int)
        for subject in violation['subjects'].values():
            if subject != "空き":
                subject_counts[subject] += 1
        
        if not subject_counts:
            # 全て空きの場合はスキップ
            continue
            
        # 最も多い科目を選択
        best_subject = max(subject_counts.items(), key=lambda x: x[1])[0]
        logger.info(f"  統一する科目: {best_subject}")
        
        # その科目を教えられる教師を探す
        subject_obj = Subject(best_subject)
        available_teachers = list(school.get_subject_teachers(subject_obj))
        
        if not available_teachers:
            logger.warning(f"  {best_subject}を教えられる教師が見つかりません")
            continue
        
        # 金子み先生を優先
        teacher = None
        for t in available_teachers:
            if t.name == "金子み":
                teacher = t
                break
        if not teacher:
            teacher = available_teachers[0]
        
        # 全ての5組に同じ科目・教師を配置
        success = True
        for class_name in grade5_classes:
            class_ref = parse_class_reference(class_name)
            assignment = Assignment(
                class_ref=class_ref,
                subject=subject_obj,
                teacher=teacher
            )
            
            try:
                # 既存の割り当てを削除
                current = schedule.get_assignment(time_slot, class_ref)
                if current:
                    schedule.remove_assignment(time_slot, class_ref)
                
                # 新しい割り当てを配置
                schedule.assign(time_slot, assignment)
                
            except Exception as e:
                logger.error(f"    {class_name}への配置失敗: {e}")
                success = False
                break
        
        if success:
            fixed_count += 1
            logger.info(f"  ✓ 修正成功: 全5組を{best_subject}({teacher.name}先生)に統一")
        else:
            logger.error(f"  ✗ 修正失敗")
    
    logger.info(f"\n=== 修正完了: {fixed_count}/{len(violations)}件 ===")
    return fixed_count

def main():
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository()
    school_repo = CSVSchoolRepository()
    
    # データ読み込み
    logger.info("データ読み込み中...")
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    schedule = schedule_repo.load("data/output/output.csv", school)
    
    # 5組同期違反の分析
    violations = analyze_grade5_sync_violations(schedule, school)
    
    if violations:
        logger.info(f"\n=== 5組同期違反: {len(violations)}件 ===")
        for v in violations[:10]:  # 最初の10件のみ表示
            logger.info(f"{v['time']}: {v['subjects']}")
        
        # 修正実行
        fixed = fix_grade5_sync_violations(schedule, school)
        
        if fixed > 0:
            # 結果を保存
            output_file = "data/output/output_grade5_sync_fixed.csv"
            schedule_repo.save_schedule(schedule, output_file)
            logger.info(f"\n修正済み時間割を保存: {output_file}")
            
            # 再チェック
            remaining = analyze_grade5_sync_violations(schedule, school)
            logger.info(f"残存違反: {len(remaining)}件")
    else:
        logger.info("5組同期違反はありません")

if __name__ == "__main__":
    main()