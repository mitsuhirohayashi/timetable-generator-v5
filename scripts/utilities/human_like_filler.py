#!/usr/bin/env python3
"""
人間の時間割担当者の方法を模倣した空欄埋めプログラム
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Set
import logging
from dataclasses import dataclass

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.entities.school import School, ClassReference, Subject
from src.domain.entities.schedule import Schedule, TimeSlot
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


@dataclass
class SubjectBalance:
    """教科のバランス情報"""
    subject_name: str
    current_hours: int
    standard_hours: int
    difference: int  # 正: 多い, 負: 少ない
    grade_comparison: Dict[ClassReference, int]  # 同学年の他クラスとの比較


class HumanLikeTimetableFiller:
    """人間の時間割担当者の方法を模倣したクラス"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.school_repo = CSVSchoolRepository(data_dir)
        self.schedule_repo = CSVScheduleRepository(data_dir)
        self.protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        
    def analyze_class_hours(self, school: School, schedule: Schedule, class_ref: ClassReference) -> Dict[str, SubjectBalance]:
        """クラスの時数を分析"""
        balances = {}
        
        # 現在の時数をカウント
        current_hours = defaultdict(int)
        for _, assignment in schedule.get_assignments_by_class(class_ref):
            if assignment and assignment.subject.name not in self.protected_subjects:
                current_hours[assignment.subject.name] += 1
        
        # 必要な教科をチェック
        required_subjects = school.get_required_subjects(class_ref)
        
        for subject in required_subjects:
            if subject.name in self.protected_subjects:
                continue
                
            standard = school.get_standard_hours(class_ref, subject)
            current = current_hours.get(subject.name, 0)
            difference = current - standard
            
            # 同学年の他クラスとの比較
            grade_comparison = {}
            grade = class_ref.grade
            
            for other_class in school.get_all_classes():
                if other_class.grade == grade and other_class != class_ref:
                    other_hours = 0
                    for _, other_assignment in schedule.get_assignments_by_class(other_class):
                        if other_assignment and other_assignment.subject.name == subject.name:
                            other_hours += 1
                    grade_comparison[other_class] = current - other_hours
            
            balances[subject.name] = SubjectBalance(
                subject_name=subject.name,
                current_hours=current,
                standard_hours=standard,
                difference=difference,
                grade_comparison=grade_comparison
            )
        
        return balances
    
    def find_shortage_subjects(self, balances: Dict[str, SubjectBalance]) -> List[str]:
        """不足している教科を優先度順にリストアップ"""
        shortages = []
        
        for subject_name, balance in balances.items():
            if balance.difference < 0:
                # 学年内で特に少ない場合は優先度を上げる
                grade_deficit = sum(1 for diff in balance.grade_comparison.values() if diff < -1)
                priority = abs(balance.difference) * 10 + grade_deficit * 5
                shortages.append((priority, subject_name, balance))
        
        # 優先度順にソート
        shortages.sort(reverse=True)
        return [subject_name for _, subject_name, _ in shortages]
    
    def find_excess_subjects(self, balances: Dict[str, SubjectBalance]) -> List[str]:
        """過剰な教科をリストアップ"""
        excesses = []
        
        for subject_name, balance in balances.items():
            if balance.difference > 0:
                excesses.append((balance.difference, subject_name))
        
        excesses.sort(reverse=True)
        return [subject_name for _, subject_name in excesses]
    
    def can_place_subject(self, school: School, schedule: Schedule, 
                         class_ref: ClassReference, time_slot: TimeSlot, 
                         subject_name: str) -> Tuple[bool, Optional[str]]:
        """指定の教科を配置できるかチェック"""
        subject = Subject(subject_name)
        teacher = school.get_assigned_teacher(subject, class_ref)
        
        if not teacher:
            return False, "教員が割り当てられていない"
        
        # 教員の利用可能性チェック
        if school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher):
            return False, "教員が不在"
        
        # 教員の重複チェック
        for other_class in school.get_all_classes():
            if other_class != class_ref:
                other_assignment = schedule.get_assignment(time_slot, other_class)
                if other_assignment and other_assignment.teacher == teacher:
                    return False, f"教員が{other_class}で授業中"
        
        # 日内重複チェック
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            check_slot = TimeSlot(time_slot.day, period)
            existing = schedule.get_assignment(check_slot, class_ref)
            if existing and existing.subject.name == subject_name:
                return False, f"{time_slot.day}曜日に既に{subject_name}がある"
        
        # 体育館制約チェック（保健体育の場合）
        if subject_name == "保":
            pe_count = 0
            for other_class in school.get_all_classes():
                other_assignment = schedule.get_assignment(time_slot, other_class)
                if other_assignment and other_assignment.subject.name == "保":
                    pe_count += 1
            if pe_count >= 1:
                return False, "体育館が使用中"
        
        return True, None
    
    def find_swappable_slot(self, school: School, schedule: Schedule,
                           class_ref: ClassReference, from_slot: TimeSlot,
                           subject_to_move: str) -> Optional[Tuple[TimeSlot, str]]:
        """スワップ可能な時間枠を探す"""
        # 他の曜日で交換可能な授業を探す
        for day in ["月", "火", "水", "木", "金"]:
            if day == from_slot.day:
                continue
            
            for period in range(1, 7):
                target_slot = TimeSlot(day, period)
                target_assignment = schedule.get_assignment(target_slot, class_ref)
                
                if not target_assignment:
                    continue
                
                if schedule.is_locked(target_slot, class_ref):
                    continue
                
                target_subject = target_assignment.subject.name
                if target_subject in self.protected_subjects:
                    continue
                
                # 両方向のスワップが可能かチェック
                can_move_to_target, _ = self.can_place_subject(
                    school, schedule, class_ref, target_slot, subject_to_move
                )
                can_move_to_from, _ = self.can_place_subject(
                    school, schedule, class_ref, from_slot, target_subject
                )
                
                if can_move_to_target and can_move_to_from:
                    # 一時的に削除してチェック
                    schedule.remove_assignment(from_slot, class_ref)
                    schedule.remove_assignment(target_slot, class_ref)
                    
                    # 再チェック
                    can_place1, _ = self.can_place_subject(
                        school, schedule, class_ref, target_slot, subject_to_move
                    )
                    can_place2, _ = self.can_place_subject(
                        school, schedule, class_ref, from_slot, target_subject
                    )
                    
                    # 元に戻す
                    teacher1 = school.get_assigned_teacher(Subject(subject_to_move), class_ref)
                    teacher2 = school.get_assigned_teacher(Subject(target_subject), class_ref)
                    schedule.assign(from_slot, Assignment(class_ref, Subject(subject_to_move), teacher1))
                    schedule.assign(target_slot, Assignment(class_ref, Subject(target_subject), teacher2))
                    
                    if can_place1 and can_place2:
                        return (target_slot, target_subject)
        
        return None
    
    def adjust_for_gym_conflict(self, school: School, schedule: Schedule,
                               time_slot: TimeSlot) -> bool:
        """体育館の競合を調整"""
        # 体育の授業を持つクラスを探す
        pe_classes = []
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == "保":
                pe_classes.append(class_ref)
        
        if len(pe_classes) <= 1:
            return True
        
        logger.info(f"  体育館競合: {time_slot}に{len(pe_classes)}クラス")
        
        # 各クラスの保健体育の時数を確認
        pe_hours = {}
        for pe_class in pe_classes:
            hours = 0
            for _, assignment in schedule.get_assignments_by_class(pe_class):
                if assignment and assignment.subject.name == "保":
                    hours += 1
            pe_hours[pe_class] = hours
        
        # 時数が多いクラスから削除候補を選ぶ
        sorted_classes = sorted(pe_classes, key=lambda c: pe_hours[c], reverse=True)
        
        for class_to_adjust in sorted_classes[1:]:  # 最初の1クラスは残す
            # 代替教科を探す
            balances = self.analyze_class_hours(school, schedule, class_to_adjust)
            shortage_subjects = self.find_shortage_subjects(balances)
            
            for alt_subject in shortage_subjects:
                can_place, reason = self.can_place_subject(
                    school, schedule, class_to_adjust, time_slot, alt_subject
                )
                
                if can_place:
                    # 保健体育を削除して代替教科を配置
                    schedule.remove_assignment(time_slot, class_to_adjust)
                    teacher = school.get_assigned_teacher(Subject(alt_subject), class_to_adjust)
                    schedule.assign(time_slot, Assignment(
                        class_to_adjust, Subject(alt_subject), teacher
                    ))
                    logger.info(f"    {class_to_adjust}の保を{alt_subject}に変更")
                    break
        
        return True
    
    def fill_empty_slots(self, input_file: str, output_file: str):
        """人間の方法で空欄を埋める"""
        logger.info("人間の時間割作成方法で空欄を埋めます...")
        
        # データ読み込み
        school = self.school_repo.load_school_data("config/base_timetable.csv")
        schedule = self.schedule_repo.load_desired_schedule(input_file, school)
        
        filled_count = 0
        
        # 各曜日を順に処理
        for day in ["月", "火", "水", "木", "金"]:
            logger.info(f"\n{day}曜日の処理を開始...")
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各クラスの空欄をチェック
                for class_ref in school.get_all_classes():
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    if schedule.is_locked(time_slot, class_ref):
                        continue
                    
                    logger.info(f"\n{class_ref} {time_slot}の空欄を処理...")
                    
                    # 時数分析
                    balances = self.analyze_class_hours(school, schedule, class_ref)
                    shortage_subjects = self.find_shortage_subjects(balances)
                    
                    if not shortage_subjects:
                        logger.info("  不足教科なし")
                        continue
                    
                    # 配置可能な教科を探す
                    placed = False
                    for subject_name in shortage_subjects:
                        can_place, reason = self.can_place_subject(
                            school, schedule, class_ref, time_slot, subject_name
                        )
                        
                        if can_place:
                            # 配置実行
                            teacher = school.get_assigned_teacher(Subject(subject_name), class_ref)
                            schedule.assign(time_slot, Assignment(
                                class_ref, Subject(subject_name), teacher
                            ))
                            logger.info(f"  → {subject_name}を配置")
                            filled_count += 1
                            placed = True
                            break
                        else:
                            logger.debug(f"  {subject_name}: {reason}")
                    
                    if not placed:
                        logger.info("  → 配置できる教科なし")
                
                # 体育館競合の調整
                self.adjust_for_gym_conflict(school, schedule, time_slot)
        
        # 結果を保存
        self.schedule_repo.save_schedule(schedule, output_file)
        
        # 最終統計
        empty_count = 0
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty_count += 1
        
        logger.info(f"\n処理完了: {filled_count}個の空欄を埋めました")
        logger.info(f"残りの空欄: {empty_count}個")
        
        # 各クラスの最終時数を表示
        logger.info("\n=== 最終時数 ===")
        for grade in [1, 2, 3]:
            logger.info(f"\n{grade}年生:")
            for class_ref in school.get_all_classes():
                if class_ref.grade == grade:
                    balances = self.analyze_class_hours(school, schedule, class_ref)
                    shortage_info = []
                    excess_info = []
                    
                    for subject_name, balance in balances.items():
                        if balance.difference < 0:
                            shortage_info.append(f"{subject_name}({balance.difference})")
                        elif balance.difference > 0:
                            excess_info.append(f"{subject_name}(+{balance.difference})")
                    
                    info_parts = [f"{class_ref}:"]
                    if shortage_info:
                        info_parts.append(f"不足={','.join(shortage_info)}")
                    if excess_info:
                        info_parts.append(f"過剰={','.join(excess_info)}")
                    
                    logger.info("  " + " ".join(info_parts))


def main():
    """メイン処理"""
    data_dir = Path("data")
    filler = HumanLikeTimetableFiller(data_dir)
    
    input_file = "output/output.csv"
    output_file = "output/output_human_filled.csv"
    
    filler.fill_empty_slots(input_file, output_file)


if __name__ == "__main__":
    main()