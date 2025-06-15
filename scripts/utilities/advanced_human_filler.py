#!/usr/bin/env python3
"""
人間の時間割担当者の高度な方法を完全に実装したプログラム
空欄埋め、日内重複解消、学年間調整を含む
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Set, NamedTuple
import logging
from dataclasses import dataclass
import copy

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.entities.school import School, ClassReference, Subject
from src.domain.entities.schedule import Schedule, TimeSlot
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class SlotInfo(NamedTuple):
    """時間枠の情報"""
    time_slot: TimeSlot
    class_ref: ClassReference
    assignment: Optional[Assignment]
    is_locked: bool
    is_forbidden: bool
    forbidden_subject: Optional[str]


@dataclass
class GradeBalance:
    """学年全体のバランス情報"""
    grade: int
    subject_totals: Dict[str, int]  # 教科名 -> 学年全体の時数
    class_hours: Dict[ClassReference, Dict[str, int]]  # クラス -> 教科 -> 時数
    
    def get_variance(self, subject: str) -> float:
        """教科の分散を計算"""
        hours = [self.class_hours[c].get(subject, 0) for c in self.class_hours]
        if not hours:
            return 0.0
        avg = sum(hours) / len(hours)
        return sum((h - avg) ** 2 for h in hours) / len(hours)


class AdvancedHumanTimetableFiller:
    """人間の高度な時間割作成方法を実装"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.school_repo = CSVSchoolRepository(data_dir)
        self.schedule_repo = CSVScheduleRepository(data_dir)
        self.protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        self.facility_subjects = {'保', '音', '美', '技', '家'}  # 特別教室を使う教科
        
    def analyze_grade_balance(self, school: School, schedule: Schedule, grade: int) -> GradeBalance:
        """学年全体のバランスを分析"""
        subject_totals = defaultdict(int)
        class_hours = {}
        
        for class_ref in school.get_all_classes():
            if class_ref.grade != grade:
                continue
            
            hours = defaultdict(int)
            for _, assignment in schedule.get_assignments_by_class(class_ref):
                if assignment and assignment.subject.name not in self.protected_subjects:
                    hours[assignment.subject.name] += 1
                    subject_totals[assignment.subject.name] += 1
            
            class_hours[class_ref] = dict(hours)
        
        return GradeBalance(
            grade=grade,
            subject_totals=dict(subject_totals),
            class_hours=class_hours
        )
    
    def find_imbalanced_subjects(self, grade_balance: GradeBalance) -> List[Tuple[str, float]]:
        """バランスの悪い教科を見つける"""
        imbalanced = []
        
        for subject in grade_balance.subject_totals:
            variance = grade_balance.get_variance(subject)
            if variance > 0.5:  # 閾値
                imbalanced.append((subject, variance))
        
        imbalanced.sort(key=lambda x: x[1], reverse=True)
        return imbalanced
    
    def analyze_slot_context(self, school: School, schedule: Schedule, 
                           time_slot: TimeSlot, class_ref: ClassReference) -> Dict:
        """時間枠の文脈を詳細に分析"""
        context = {
            'empty_slots_in_day': 0,
            'subjects_in_day': defaultdict(int),
            'facility_usage': defaultdict(int),
            'teacher_availability': {},
            'grade_pe_count': 0,
            'forbidden_info': None
        }
        
        # その日の情報を収集
        for period in range(1, 7):
            slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(slot, class_ref)
            
            if not assignment:
                context['empty_slots_in_day'] += 1
            else:
                context['subjects_in_day'][assignment.subject.name] += 1
            
            # 施設使用状況
            for other_class in school.get_all_classes():
                other_assignment = schedule.get_assignment(slot, other_class)
                if other_assignment and other_assignment.subject.name in self.facility_subjects:
                    context['facility_usage'][other_assignment.subject.name] += 1
            
            # 同学年の体育
            if period == time_slot.period:
                for other_class in school.get_all_classes():
                    if other_class.grade == class_ref.grade:
                        other_assignment = schedule.get_assignment(slot, other_class)
                        if other_assignment and other_assignment.subject.name == "保":
                            context['grade_pe_count'] += 1
        
        # 教員の利用可能性
        for subject in school.get_required_subjects(class_ref):
            if subject.name in self.protected_subjects:
                continue
            
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher:
                available = not school.is_teacher_unavailable(
                    time_slot.day, time_slot.period, teacher
                )
                
                # 他クラスでの使用チェック
                if available:
                    for other_class in school.get_all_classes():
                        if other_class != class_ref:
                            other_assignment = schedule.get_assignment(time_slot, other_class)
                            if other_assignment and other_assignment.teacher == teacher:
                                available = False
                                break
                
                context['teacher_availability'][subject.name] = available
        
        return context
    
    def calculate_placement_score(self, subject_name: str, context: Dict, 
                                balances: Dict, grade_balance: GradeBalance) -> float:
        """配置スコアを計算（人間の判断を模倣）"""
        score = 0.0
        
        # 基本スコア：不足度に応じて
        balance = balances.get(subject_name)
        if balance:
            score += abs(balance.difference) * 10 if balance.difference < 0 else -balance.difference * 5
        
        # 日内重複ペナルティ
        if subject_name in context['subjects_in_day']:
            score -= 100  # 重いペナルティ
        
        # 教員利用可能性
        if not context['teacher_availability'].get(subject_name, False):
            return -1000  # 配置不可
        
        # 施設制約
        if subject_name in self.facility_subjects:
            current_usage = context['facility_usage'].get(subject_name, 0)
            if subject_name == "保" and current_usage >= 1:
                return -1000  # 体育館制約
            elif current_usage >= 2:  # 他の特別教室
                score -= 50
        
        # 学年バランスボーナス
        variance = grade_balance.get_variance(subject_name)
        if variance > 1.0:
            # このクラスが少ない場合はボーナス
            class_hours = grade_balance.class_hours
            avg_hours = sum(class_hours[c].get(subject_name, 0) for c in class_hours) / len(class_hours)
            current_hours = balance.current_hours if balance else 0
            if current_hours < avg_hours:
                score += 20
        
        # 連続性考慮（同じ教科が近い時限にある方が良い場合）
        if subject_name in ["数", "国", "英"]:  # 主要教科
            for delta in [-1, 1]:
                adjacent_period = context.get('time_slot').period + delta
                if 1 <= adjacent_period <= 6:
                    adjacent_slot = TimeSlot(context.get('time_slot').day, adjacent_period)
                    # ここでは簡略化
        
        return score
    
    def try_swap_for_duplicate(self, school: School, schedule: Schedule,
                             class_ref: ClassReference, day: str, 
                             duplicate_subject: str) -> bool:
        """日内重複を解消するためのスワップを試みる"""
        # 重複している時限を特定
        duplicate_slots = []
        for period in range(1, 7):
            slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(slot, class_ref)
            if assignment and assignment.subject.name == duplicate_subject:
                if not schedule.is_locked(slot, class_ref):
                    duplicate_slots.append(slot)
        
        if len(duplicate_slots) < 2:
            return False
        
        # 最後の時限を移動対象とする
        slot_to_move = duplicate_slots[-1]
        
        # 他の曜日でスワップ可能な授業を探す
        for target_day in ["月", "火", "水", "木", "金"]:
            if target_day == day:
                continue
            
            # その曜日に重複がないかチェック
            has_duplicate = False
            for period in range(1, 7):
                check_slot = TimeSlot(target_day, period)
                assignment = schedule.get_assignment(check_slot, class_ref)
                if assignment and assignment.subject.name == duplicate_subject:
                    has_duplicate = True
                    break
            
            if has_duplicate:
                continue
            
            # スワップ候補を探す
            for target_period in range(1, 7):
                target_slot = TimeSlot(target_day, target_period)
                target_assignment = schedule.get_assignment(target_slot, class_ref)
                
                if not target_assignment or schedule.is_locked(target_slot, class_ref):
                    continue
                
                if target_assignment.subject.name in self.protected_subjects:
                    continue
                
                # スワップを実行してみる
                original_assignment = schedule.get_assignment(slot_to_move, class_ref)
                
                schedule.remove_assignment(slot_to_move, class_ref)
                schedule.remove_assignment(target_slot, class_ref)
                
                # 配置可能かチェック
                can_place1 = self._can_place_assignment(school, schedule, target_slot, original_assignment)
                can_place2 = self._can_place_assignment(school, schedule, slot_to_move, target_assignment)
                
                if can_place1 and can_place2:
                    schedule.assign(target_slot, original_assignment)
                    schedule.assign(slot_to_move, target_assignment)
                    logger.info(f"  スワップ成功: {slot_to_move}の{duplicate_subject} ↔ {target_slot}の{target_assignment.subject.name}")
                    return True
                else:
                    # 元に戻す
                    schedule.assign(slot_to_move, original_assignment)
                    schedule.assign(target_slot, target_assignment)
        
        return False
    
    def _can_place_assignment(self, school: School, schedule: Schedule,
                            time_slot: TimeSlot, assignment: Assignment) -> bool:
        """割り当てが可能かチェック"""
        if not assignment or not assignment.teacher:
            return False
        
        # 教員利用可能性
        if school.is_teacher_unavailable(time_slot.day, time_slot.period, assignment.teacher):
            return False
        
        # 教員重複
        for other_class in school.get_all_classes():
            if other_class != assignment.class_ref:
                other_assignment = schedule.get_assignment(time_slot, other_class)
                if other_assignment and other_assignment.teacher == assignment.teacher:
                    return False
        
        # 体育館制約
        if assignment.subject.name == "保":
            pe_count = 0
            for other_class in school.get_all_classes():
                other_assignment = schedule.get_assignment(time_slot, other_class)
                if other_assignment and other_assignment.subject.name == "保":
                    pe_count += 1
            if pe_count >= 1:
                return False
        
        return True
    
    def resolve_facility_conflict(self, school: School, schedule: Schedule,
                                time_slot: TimeSlot, facility_subject: str) -> bool:
        """施設競合を解決"""
        using_classes = []
        
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == facility_subject:
                using_classes.append((class_ref, assignment))
        
        if facility_subject == "保" and len(using_classes) > 1:
            # 体育館は1クラスのみ
            logger.info(f"  体育館競合を調整: {time_slot}")
            
            # 各クラスの保健体育時数を確認
            pe_hours = {}
            for class_ref, _ in using_classes:
                hours = sum(1 for _, a in schedule.get_assignments_by_class(class_ref)
                          if a and a.subject.name == "保")
                pe_hours[class_ref] = hours
            
            # 時数が多い順にソート
            sorted_classes = sorted(using_classes, key=lambda x: pe_hours[x[0]], reverse=True)
            
            # 2番目以降のクラスの授業を変更
            for class_ref, assignment in sorted_classes[1:]:
                if schedule.is_locked(time_slot, class_ref):
                    continue
                
                # 代替教科を探す
                balances = self._analyze_class_balance(school, schedule, class_ref)
                
                for alt_subject, balance in sorted(balances.items(), 
                                                  key=lambda x: x[1].difference):
                    if balance.difference >= 0:  # 不足していない教科はスキップ
                        continue
                    
                    if alt_subject in self.protected_subjects:
                        continue
                    
                    alt_teacher = school.get_assigned_teacher(Subject(alt_subject), class_ref)
                    if not alt_teacher:
                        continue
                    
                    alt_assignment = Assignment(class_ref, Subject(alt_subject), alt_teacher)
                    
                    if self._can_place_assignment(school, schedule, time_slot, alt_assignment):
                        schedule.remove_assignment(time_slot, class_ref)
                        schedule.assign(time_slot, alt_assignment)
                        logger.info(f"    {class_ref}の保を{alt_subject}に変更")
                        break
            
            return True
        
        return False
    
    def _analyze_class_balance(self, school: School, schedule: Schedule,
                             class_ref: ClassReference) -> Dict:
        """簡易版のクラスバランス分析"""
        from dataclasses import dataclass
        
        @dataclass
        class SubjectBalance:
            subject_name: str
            current_hours: int
            standard_hours: int
            difference: int
            grade_comparison: Dict
        
        balances = {}
        current_hours = defaultdict(int)
        
        for _, assignment in schedule.get_assignments_by_class(class_ref):
            if assignment and assignment.subject.name not in self.protected_subjects:
                current_hours[assignment.subject.name] += 1
        
        for subject in school.get_required_subjects(class_ref):
            if subject.name in self.protected_subjects:
                continue
            
            standard = school.get_standard_hours(class_ref, subject)
            current = current_hours.get(subject.name, 0)
            
            balances[subject.name] = SubjectBalance(
                subject_name=subject.name,
                current_hours=current,
                standard_hours=standard,
                difference=current - standard,
                grade_comparison={}
            )
        
        return balances
    
    def fill_with_human_method(self, input_file: str, output_file: str):
        """人間の方法で時間割を完成させる"""
        logger.info("=== 人間の高度な時間割作成方法を開始 ===\n")
        
        # データ読み込み
        school = self.school_repo.load_school_data("config/base_timetable.csv")
        schedule = self.schedule_repo.load_desired_schedule(input_file, school)
        
        iteration = 0
        max_iterations = 5
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"\n=== 反復 {iteration} ===")
            
            changes_made = False
            
            # 各曜日を処理
            for day in ["月", "火", "水", "木", "金"]:
                logger.info(f"\n{day}曜日の処理...")
                
                # 学年ごとのバランスを分析
                grade_balances = {}
                for grade in [1, 2, 3]:
                    grade_balances[grade] = self.analyze_grade_balance(school, schedule, grade)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 施設競合の解決
                    for facility in self.facility_subjects:
                        self.resolve_facility_conflict(school, schedule, time_slot, facility)
                    
                    # 各クラスの処理
                    for class_ref in school.get_all_classes():
                        # 空欄チェック
                        if not schedule.get_assignment(time_slot, class_ref):
                            if schedule.is_locked(time_slot, class_ref):
                                continue
                            
                            # 文脈分析
                            context = self.analyze_slot_context(school, schedule, time_slot, class_ref)
                            context['time_slot'] = time_slot
                            
                            # バランス分析
                            balances = self._analyze_class_balance(school, schedule, class_ref)
                            
                            # 配置する教科を選択
                            candidates = []
                            for subject_name, balance in balances.items():
                                if balance.difference < 0:  # 不足している
                                    score = self.calculate_placement_score(
                                        subject_name, context, balances, 
                                        grade_balances[class_ref.grade]
                                    )
                                    if score > -100:
                                        candidates.append((score, subject_name))
                            
                            candidates.sort(reverse=True)
                            
                            # 配置実行
                            for score, subject_name in candidates:
                                teacher = school.get_assigned_teacher(Subject(subject_name), class_ref)
                                if teacher:
                                    assignment = Assignment(class_ref, Subject(subject_name), teacher)
                                    if self._can_place_assignment(school, schedule, time_slot, assignment):
                                        schedule.assign(time_slot, assignment)
                                        logger.info(f"  {class_ref} {time_slot}: {subject_name}を配置")
                                        changes_made = True
                                        break
                
                # 日内重複の解消
                for class_ref in school.get_all_classes():
                    subjects_in_day = defaultdict(list)
                    
                    for period in range(1, 7):
                        slot = TimeSlot(day, period)
                        assignment = schedule.get_assignment(slot, class_ref)
                        if assignment and assignment.subject.name not in self.protected_subjects:
                            subjects_in_day[assignment.subject.name].append(slot)
                    
                    # 重複をチェック
                    for subject_name, slots in subjects_in_day.items():
                        if len(slots) > 1:
                            logger.info(f"\n{class_ref} {day}曜日: {subject_name}が{len(slots)}回")
                            if self.try_swap_for_duplicate(school, schedule, class_ref, day, subject_name):
                                changes_made = True
            
            if not changes_made:
                logger.info("\n変更なし - 処理完了")
                break
        
        # 結果を保存
        self.schedule_repo.save_schedule(schedule, output_file)
        
        # 最終統計を表示
        self._display_final_statistics(school, schedule)
    
    def _display_final_statistics(self, school: School, schedule: Schedule):
        """最終統計を表示"""
        logger.info("\n=== 最終統計 ===")
        
        # 空欄カウント
        empty_count = 0
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    if not schedule.get_assignment(TimeSlot(day, period), class_ref):
                        empty_count += 1
        
        logger.info(f"\n空欄数: {empty_count}")
        
        # 学年ごとの統計
        for grade in [1, 2, 3]:
            logger.info(f"\n【{grade}年生】")
            grade_balance = self.analyze_grade_balance(school, schedule, grade)
            
            # 教科ごとの合計とバランス
            for subject in sorted(grade_balance.subject_totals.keys()):
                total = grade_balance.subject_totals[subject]
                variance = grade_balance.get_variance(subject)
                
                class_info = []
                for class_ref in sorted(grade_balance.class_hours.keys(), 
                                      key=lambda c: c.class_number):
                    hours = grade_balance.class_hours[class_ref].get(subject, 0)
                    standard = school.get_standard_hours(class_ref, Subject(subject))
                    diff = hours - standard
                    diff_str = f"+{diff}" if diff > 0 else str(diff)
                    class_info.append(f"{class_ref.class_number}組:{hours}({diff_str})")
                
                logger.info(f"  {subject}: 合計{total}, 分散{variance:.2f} - {', '.join(class_info)}")


def main():
    """メイン処理"""
    data_dir = Path("data")
    filler = AdvancedHumanTimetableFiller(data_dir)
    
    input_file = "output/output.csv"
    output_file = "output/output_advanced_filled.csv"
    
    filler.fill_with_human_method(input_file, output_file)


if __name__ == "__main__":
    main()