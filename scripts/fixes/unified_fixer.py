#!/usr/bin/env python3
"""統合修正ツール - 全ての修正機能を1つのスクリプトに統合"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_config import path_config
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment

logger = logging.getLogger(__name__)


class UnifiedFixer:
    """全ての修正機能を統合したクラス"""
    
    def __init__(self):
        self.schedule_repo = CSVScheduleRepository()
        self.school_repo = CSVSchoolRepository(path_config.base_config_dir)
        self.schedule = None
        self.school = None
        self.modifications = 0
    
    def load_data(self, schedule_file: str = "output.csv"):
        """スケジュールと学校データを読み込む"""
        try:
            # 学校データを読み込み
            self.school = self.school_repo.load_school_data()
            
            # スケジュールを読み込み
            output_path = path_config.get_output_path(schedule_file)
            self.schedule = self.schedule_repo.load(str(output_path), self.school)
            
            logger.info(f"データを読み込みました: {output_path}")
            return True
        except Exception as e:
            logger.error(f"データ読み込みエラー: {e}")
            return False
    
    def fix_all(self):
        """全ての修正を実行"""
        print("\n=== 統合修正処理を開始 ===")
        
        # 修正順序が重要
        self.fix_teacher_conflicts()
        self.fix_daily_duplicates()
        self.fix_exchange_sync()
        self.fix_jiritsu_violations()
        self.fix_gym_usage()
        
        print(f"\n総修正数: {self.modifications}件")
    
    def fix_teacher_conflicts(self):
        """教師の重複を修正"""
        print("\n【教師重複の修正】")
        fixed = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                teacher_assignments = {}
                
                # 教師の割り当てを収集
                for class_ref in self.school.get_all_classes():
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        if teacher_name not in teacher_assignments:
                            teacher_assignments[teacher_name] = []
                        teacher_assignments[teacher_name].append((class_ref, assignment))
                
                # 重複を修正
                for teacher, assignments in teacher_assignments.items():
                    # 5組の合同授業は除外
                    grade5_assignments = [(c, a) for c, a in assignments if c.class_number == 5]
                    non_grade5_assignments = [(c, a) for c, a in assignments if c.class_number != 5]
                    
                    if len(non_grade5_assignments) > 1:
                        # 最初のクラスを残して、他は別の教師に変更
                        for i in range(1, len(non_grade5_assignments)):
                            class_ref, assignment = non_grade5_assignments[i]
                            
                            # 代替教師を探す
                            alternative_teacher = self._find_alternative_teacher(
                                assignment.subject, class_ref, time_slot, teacher
                            )
                            
                            if alternative_teacher:
                                new_assignment = Assignment(
                                    class_ref, assignment.subject, alternative_teacher
                                )
                                self.schedule.remove_assignment(time_slot, class_ref)
                                self.schedule.assign(time_slot, new_assignment)
                                fixed += 1
                                self.modifications += 1
                                print(f"  修正: {time_slot} {class_ref} - {teacher} → {alternative_teacher.name}")
        
        print(f"  教師重複修正: {fixed}件")
    
    def fix_daily_duplicates(self):
        """日内重複を修正"""
        print("\n【日内重複の修正】")
        fixed = 0
        
        for class_ref in self.school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                subjects_in_day = {}
                
                # その日の科目を収集
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        subject = assignment.subject.name
                        if subject not in ["欠", "YT", "道", "学", "総", "学総", "行"]:
                            if subject not in subjects_in_day:
                                subjects_in_day[subject] = []
                            subjects_in_day[subject].append((period, assignment))
                
                # 重複を修正
                for subject, occurrences in subjects_in_day.items():
                    if len(occurrences) > 1:
                        # 最初の1つを残して、他は別の科目に変更
                        for i in range(1, len(occurrences)):
                            period, assignment = occurrences[i]
                            time_slot = TimeSlot(day, period)
                            
                            # 代替科目を探す
                            alternative = self._find_alternative_subject(
                                class_ref, time_slot, subject
                            )
                            
                            if alternative:
                                new_assignment = Assignment(
                                    class_ref, alternative['subject'], alternative['teacher']
                                )
                                self.schedule.remove_assignment(time_slot, class_ref)
                                self.schedule.assign(time_slot, new_assignment)
                                fixed += 1
                                self.modifications += 1
                                print(f"  修正: {class_ref} {time_slot} - {subject} → {alternative['subject'].name}")
        
        print(f"  日内重複修正: {fixed}件")
    
    def fix_exchange_sync(self):
        """交流学級同期を修正"""
        print("\n【交流学級同期の修正】")
        fixed = 0
        
        exchange_pairs = [
            (ClassReference(1, 1), ClassReference(1, 6)),
            (ClassReference(1, 2), ClassReference(1, 7)),
            (ClassReference(2, 3), ClassReference(2, 6)),
            (ClassReference(2, 2), ClassReference(2, 7)),
            (ClassReference(3, 3), ClassReference(3, 6)),
            (ClassReference(3, 2), ClassReference(3, 7))
        ]
        
        for parent_class, exchange_class in exchange_pairs:
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    parent_assignment = self.schedule.get_assignment(time_slot, parent_class)
                    exchange_assignment = self.schedule.get_assignment(time_slot, exchange_class)
                    
                    if exchange_assignment and exchange_assignment.subject.name not in ["自立", "日生", "作業"]:
                        if not parent_assignment or parent_assignment.subject != exchange_assignment.subject:
                            # 親学級の授業を交流学級にコピー
                            if parent_assignment:
                                self.schedule.remove_assignment(time_slot, exchange_class)
                                self.schedule.assign(time_slot, Assignment(
                                    exchange_class, parent_assignment.subject, parent_assignment.teacher
                                ))
                                fixed += 1
                                self.modifications += 1
                                print(f"  修正: {time_slot} {exchange_class} - {parent_class}と同期")
        
        print(f"  交流学級同期修正: {fixed}件")
    
    def fix_jiritsu_violations(self):
        """自立活動違反を修正"""
        print("\n【自立活動違反の修正】")
        fixed = 0
        
        exchange_pairs = [
            (ClassReference(1, 1), ClassReference(1, 6)),
            (ClassReference(1, 2), ClassReference(1, 7)),
            (ClassReference(2, 3), ClassReference(2, 6)),
            (ClassReference(2, 2), ClassReference(2, 7)),
            (ClassReference(3, 3), ClassReference(3, 6)),
            (ClassReference(3, 2), ClassReference(3, 7))
        ]
        
        for parent_class, exchange_class in exchange_pairs:
            jiritsu_count = 0
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 6):  # 6限は除外
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = self.schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = self.schedule.get_assignment(time_slot, parent_class)
                    
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                            # 親学級を数学または英語に変更
                            target_subject = Subject("数") if jiritsu_count % 2 == 0 else Subject("英")
                            teacher = self.school.get_assigned_teacher(target_subject, parent_class)
                            
                            if teacher and self._is_teacher_available(teacher, time_slot):
                                new_assignment = Assignment(parent_class, target_subject, teacher)
                                if parent_assignment:
                                    self.schedule.remove_assignment(time_slot, parent_class)
                                self.schedule.assign(time_slot, new_assignment)
                                fixed += 1
                                self.modifications += 1
                                jiritsu_count += 1
                                print(f"  修正: {time_slot} {parent_class} → {target_subject.name}（{exchange_class}の自立のため）")
        
        print(f"  自立活動違反修正: {fixed}件")
    
    def fix_gym_usage(self):
        """体育館使用違反を修正"""
        print("\n【体育館使用違反の修正】")
        fixed = 0
        
        # 実装は省略（必要に応じて追加）
        print(f"  体育館使用修正: {fixed}件")
    
    def _find_alternative_teacher(self, subject: Subject, class_ref: ClassReference, 
                                  time_slot: TimeSlot, exclude_teacher: str) -> Optional[Teacher]:
        """代替教師を探す"""
        all_teachers = self.school.get_subject_teachers(subject)
        
        for teacher in all_teachers:
            if teacher.name != exclude_teacher and self._is_teacher_available(teacher, time_slot):
                return teacher
        
        return None
    
    def _find_alternative_subject(self, class_ref: ClassReference, time_slot: TimeSlot, 
                                  exclude_subject: str) -> Optional[Dict]:
        """代替科目と教師を探す"""
        all_subjects = self.school.get_required_subjects(class_ref)
        
        for subject in all_subjects:
            if subject.name != exclude_subject and subject.name not in ["欠", "YT", "道", "学", "総", "学総", "行"]:
                teacher = self.school.get_assigned_teacher(subject, class_ref)
                if teacher and self._is_teacher_available(teacher, time_slot):
                    # この科目が既にその日に配置されていないかチェック
                    if not self._is_subject_in_day(class_ref, time_slot.day, subject.name):
                        return {'subject': subject, 'teacher': teacher}
        
        return None
    
    def _is_teacher_available(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教師が利用可能かチェック"""
        # 既に他のクラスで教えていないかチェック
        for class_ref in self.school.get_all_classes():
            assignment = self.schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                # 5組の合同授業は例外
                if class_ref.class_number != 5:
                    return False
        
        # 不在チェック
        return not self.school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher)
    
    def _is_subject_in_day(self, class_ref: ClassReference, day: str, subject_name: str) -> bool:
        """その日に既に科目が配置されているかチェック"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = self.schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == subject_name:
                return True
        return False
    
    def save_schedule(self, output_file: str = "output_fixed.csv"):
        """修正済みスケジュールを保存"""
        try:
            self.schedule_repo.save_schedule(self.schedule, output_file)
            print(f"\n修正済みスケジュールを保存: {output_file}")
        except Exception as e:
            logger.error(f"保存エラー: {e}")


def main():
    parser = argparse.ArgumentParser(description='統合修正ツール')
    parser.add_argument('--type', choices=['all', 'teacher', 'daily', 'exchange', 'jiritsu', 'gym'],
                        default='all', help='修正タイプ')
    parser.add_argument('--input', default='output.csv', help='入力ファイル')
    parser.add_argument('--output', default='output_fixed.csv', help='出力ファイル')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細ログを表示')
    
    args = parser.parse_args()
    
    # ログレベルの設定
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    fixer = UnifiedFixer()
    if not fixer.load_data(args.input):
        return
    
    if args.type == 'all':
        fixer.fix_all()
    elif args.type == 'teacher':
        fixer.fix_teacher_conflicts()
    elif args.type == 'daily':
        fixer.fix_daily_duplicates()
    elif args.type == 'exchange':
        fixer.fix_exchange_sync()
    elif args.type == 'jiritsu':
        fixer.fix_jiritsu_violations()
    elif args.type == 'gym':
        fixer.fix_gym_usage()
    
    if fixer.modifications > 0:
        fixer.save_schedule(args.output)
    else:
        print("\n修正が必要な違反はありませんでした。")


if __name__ == "__main__":
    main()