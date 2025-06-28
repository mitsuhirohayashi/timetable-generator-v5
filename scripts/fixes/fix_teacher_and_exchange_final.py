#!/usr/bin/env python3
"""最終的な教師重複と交流学級同期違反を修正するスクリプト"""

import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Set, Optional

# timetable_v5ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot


class TeacherAndExchangeFinalFixer:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.schedule_repo = CSVScheduleRepository(str(self.data_dir))
        self.school_repo = CSVSchoolRepository(str(self.data_dir))
        self.teacher_repo = TeacherMappingRepository(str(self.data_dir))
        
        # 交流学級マッピング
        self.exchange_pairs = {
            '1年6組': '1年1組',
            '1年7組': '1年2組',
            '2年6組': '2年3組',
            '2年7組': '2年2組',
            '3年6組': '3年3組',
            '3年7組': '3年2組',
        }
        
        # 固定科目
        self.fixed_subjects = {'欠', 'YT', '学', '学活', '総', '総合', '道', '道徳', '学総', '行', '行事', 'テスト', '技家'}
        
        # 主要教科
        self.main_subjects = {'国', '数', '英', '理', '社'}
        
        # 5組クラス
        self.grade5_classes = {'1年5組', '2年5組', '3年5組'}
        
    def load_data(self):
        """データを読み込む"""
        print("データを読み込み中...")
        self.school = self.school_repo.load_school_data("config/base_timetable.csv")
        self.schedule = self.schedule_repo.load("output/output_fixed.csv", self.school)
        self.teacher_mapping = self.teacher_repo.load_teacher_mapping("config/teacher_subject_mapping.csv")
        
    def get_teacher_for_assignment(self, class_name: str, subject: str) -> Optional[str]:
        """クラスと教科から教師を取得"""
        for (teacher, subj, cls), _ in self.teacher_mapping.items():
            if cls == class_name and subj == subject:
                return teacher
        return None
        
    def find_teacher_conflicts(self) -> Dict[Tuple[str, int], List[Tuple[str, str, str]]]:
        """教師の重複を検出"""
        teacher_schedule = defaultdict(lambda: defaultdict(list))
        
        days = ['月', '火', '水', '木', '金']
        
        for class_name in self.schedule.classes:
            for day_idx, day in enumerate(days):
                for period in range(1, 7):
                    slot = TimeSlot(day, period)
                    assignment = self.schedule.get_assignment(class_name, slot)
                    
                    if assignment and assignment.subject and assignment.subject not in self.fixed_subjects:
                        teacher = self.get_teacher_for_assignment(class_name, assignment.subject)
                        if teacher:
                            teacher_schedule[teacher][(day, period)].append((class_name, assignment.subject))
        
        # 重複を検出
        conflicts = {}
        for teacher, schedule in teacher_schedule.items():
            for (day, period), classes in schedule.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_count = sum(1 for cls, _ in classes if cls in self.grade5_classes)
                    if grade5_count == len(classes) and grade5_count > 1:
                        continue
                    conflicts[(day, period)] = [(teacher, cls, subj) for cls, subj in classes]
                    
        return conflicts
    
    def find_exchange_sync_violations(self) -> List[Tuple[str, str, TimeSlot, str, str]]:
        """交流学級の同期違反を検出"""
        violations = []
        days = ['月', '火', '水', '木', '金']
        
        for exchange_class, parent_class in self.exchange_pairs.items():
            for day_idx, day in enumerate(days):
                for period in range(1, 7):
                    slot = TimeSlot(day, period)
                    
                    exchange_assignment = self.schedule.get_assignment(exchange_class, slot)
                    parent_assignment = self.schedule.get_assignment(parent_class, slot)
                    
                    if not exchange_assignment or not parent_assignment:
                        continue
                        
                    exchange_subject = exchange_assignment.subject if exchange_assignment else None
                    parent_subject = parent_assignment.subject if parent_assignment else None
                    
                    # 交流学級が自立活動の場合
                    if exchange_subject == '自立':
                        if parent_subject not in ['数', '英']:
                            violations.append((exchange_class, parent_class, slot, exchange_subject, parent_subject))
                    # 交流学級が自立活動でない場合、親学級と同じでなければならない
                    elif exchange_subject != parent_subject:
                        violations.append((exchange_class, parent_class, slot, exchange_subject, parent_subject))
                        
        return violations
    
    def find_available_subjects(self, class_name: str, exclude_subjects: Set[str]) -> List[str]:
        """利用可能な科目を取得"""
        available = []
        
        # その日に既に配置されている科目を確認
        day_subjects = set()
        for period in range(1, 7):
            assignment = self.schedule.get_assignment(class_name, TimeSlot(exclude_subjects, period))
            if assignment and assignment.subject:
                day_subjects.add(assignment.subject)
        
        # 教師マッピングから利用可能な科目を取得
        for (teacher, subject, cls), _ in self.teacher_mapping.items():
            if cls == class_name and subject not in self.fixed_subjects and subject not in exclude_subjects:
                available.append(subject)
                
        return list(set(available))
    
    def swap_assignments(self, class1: str, slot1: TimeSlot, class2: str, slot2: TimeSlot) -> bool:
        """2つの時間帯の授業を交換"""
        assignment1 = self.schedule.get_assignment(class1, slot1)
        assignment2 = self.schedule.get_assignment(class2, slot2)
        
        if not assignment1 or not assignment2:
            return False
            
        # 固定科目は交換しない
        if assignment1.subject in self.fixed_subjects or assignment2.subject in self.fixed_subjects:
            return False
            
        # 交換
        self.schedule.assign(class1, slot1, assignment2.subject)
        self.schedule.assign(class2, slot2, assignment1.subject)
        
        return True
    
    def fix_teacher_conflicts(self) -> int:
        """教師の重複を修正"""
        print("\n=== 教師重複の修正 ===")
        fixed_count = 0
        
        conflicts = self.find_teacher_conflicts()
        
        for (day, period), teacher_assignments in sorted(conflicts.items()):
            print(f"\n{day}曜{period}校時の重複:")
            for teacher, class_name, subject in teacher_assignments:
                print(f"  - {teacher}先生: {class_name} {subject}")
            
            # 最初のクラスを残し、他のクラスの授業を移動
            base_teacher, base_class, base_subject = teacher_assignments[0]
            
            for teacher, conflict_class, conflict_subject in teacher_assignments[1:]:
                # 同じ日の他の時間帯を探す
                moved = False
                for alt_period in range(1, 7):
                    if alt_period == period:
                        continue
                        
                    alt_slot = TimeSlot(day, alt_period)
                    alt_assignment = self.schedule.get_assignment(conflict_class, alt_slot)
                    
                    if alt_assignment and alt_assignment.subject not in self.fixed_subjects:
                        # その時間の教師を確認
                        alt_teacher = self.get_teacher_for_assignment(conflict_class, alt_assignment.subject)
                        
                        # 交換先でも重複が発生しないか確認
                        conflict_free = True
                        for cls in self.schedule.classes:
                            check_assignment = self.schedule.get_assignment(cls, TimeSlot(day, period))
                            if check_assignment and check_assignment.subject == alt_assignment.subject:
                                check_teacher = self.get_teacher_for_assignment(cls, alt_assignment.subject)
                                if check_teacher == alt_teacher and cls != conflict_class:
                                    conflict_free = False
                                    break
                        
                        if conflict_free:
                            if self.swap_assignments(conflict_class, TimeSlot(day, period), conflict_class, alt_slot):
                                print(f"  → {conflict_class}の{day}曜{period}校時と{alt_period}校時を交換")
                                fixed_count += 1
                                moved = True
                                break
                
                if not moved:
                    print(f"  → {conflict_class}の{conflict_subject}を移動できませんでした")
        
        return fixed_count
    
    def fix_exchange_sync_violations(self) -> int:
        """交流学級の同期違反を修正"""
        print("\n=== 交流学級同期の修正 ===")
        fixed_count = 0
        
        violations = self.find_exchange_sync_violations()
        
        for exchange_class, parent_class, slot, exchange_subject, parent_subject in violations:
            print(f"\n{exchange_class}と{parent_class}の{slot.day}曜{slot.period}校時:")
            print(f"  交流学級: {exchange_subject}, 親学級: {parent_subject}")
            
            # 交流学級が自立活動の場合
            if exchange_subject == '自立':
                # 親学級を数学か英語に変更
                target_subjects = ['数', '英']
                for target_subject in target_subjects:
                    # その日の他の時間帯でtarget_subjectを探す
                    for alt_period in range(1, 7):
                        if alt_period == slot.period:
                            continue
                            
                        alt_slot = TimeSlot(slot.day, alt_period)
                        alt_assignment = self.schedule.get_assignment(parent_class, alt_slot)
                        
                        if alt_assignment and alt_assignment.subject == target_subject:
                            if self.swap_assignments(parent_class, slot, parent_class, alt_slot):
                                print(f"  → {parent_class}の{slot.day}曜{slot.period}校時を{target_subject}に変更")
                                fixed_count += 1
                                break
                    if fixed_count > 0:
                        break
            else:
                # 交流学級を親学級と同じにする
                self.schedule.assign(exchange_class, slot, parent_subject)
                print(f"  → {exchange_class}を{parent_subject}に変更")
                fixed_count += 1
        
        return fixed_count
    
    def fill_empty_slots(self) -> int:
        """空きスロットを埋める"""
        print("\n=== 空きスロットの充填 ===")
        filled_count = 0
        
        days = ['月', '火', '水', '木', '金']
        
        for class_name in self.schedule.classes:
            for day_idx, day in enumerate(days):
                for period in range(1, 7):
                    slot = TimeSlot(day, period)
                    assignment = self.schedule.get_assignment(class_name, slot)
                    
                    if not assignment or not assignment.subject:
                        # 利用可能な科目を探す
                        day_subjects = set()
                        for p in range(1, 7):
                            a = self.schedule.get_assignment(class_name, TimeSlot(day, p))
                            if a and a.subject:
                                day_subjects.add(a.subject)
                        
                        # 主要教科を優先
                        available_subjects = []
                        for (teacher, subject, cls), _ in self.teacher_mapping.items():
                            if cls == class_name and subject not in self.fixed_subjects and subject not in day_subjects:
                                if subject in self.main_subjects:
                                    available_subjects.insert(0, subject)
                                else:
                                    available_subjects.append(subject)
                        
                        if available_subjects:
                            self.schedule.assign(class_name, slot, available_subjects[0])
                            print(f"  {class_name}の{day}曜{period}校時に{available_subjects[0]}を配置")
                            filled_count += 1
        
        return filled_count
    
    def verify_fixes(self):
        """修正後の違反を確認"""
        print("\n=== 修正後の検証 ===")
        
        # 教師重複を再確認
        conflicts = self.find_teacher_conflicts()
        print(f"\n教師重複: {len(conflicts)}件")
        
        # 交流学級同期を再確認
        sync_violations = self.find_exchange_sync_violations()
        print(f"交流学級同期違反: {len(sync_violations)}件")
        
        # 空きスロットを確認
        empty_count = 0
        days = ['月', '火', '水', '木', '金']
        for class_name in self.schedule.classes:
            for day in days:
                for period in range(1, 7):
                    assignment = self.schedule.get_assignment(class_name, TimeSlot(day, period))
                    if not assignment or not assignment.subject:
                        empty_count += 1
        
        print(f"空きスロット: {empty_count}件")
        
        return len(conflicts), len(sync_violations), empty_count
    
    def save_result(self, output_filename: str):
        """結果を保存"""
        output_path = self.data_dir / "output" / output_filename
        self.schedule_repo.save(self.schedule, str(output_path))
        print(f"\n結果を保存しました: {output_path}")
    
    def run(self):
        """メイン処理"""
        print("=== 最終修正処理開始 ===")
        
        # データ読み込み
        self.load_data()
        
        # 初期状態を確認
        print("\n初期違反状態:")
        initial_conflicts = self.find_teacher_conflicts()
        initial_sync_violations = self.find_exchange_sync_violations()
        print(f"教師重複: {len(initial_conflicts)}件")
        print(f"交流学級同期違反: {len(initial_sync_violations)}件")
        
        # 修正実行
        teacher_fixed = self.fix_teacher_conflicts()
        sync_fixed = self.fix_exchange_sync_violations()
        filled = self.fill_empty_slots()
        
        print(f"\n修正結果:")
        print(f"教師重複修正: {teacher_fixed}件")
        print(f"交流学級同期修正: {sync_fixed}件")
        print(f"空きスロット充填: {filled}件")
        
        # 最終検証
        final_conflicts, final_sync, final_empty = self.verify_fixes()
        
        # 結果保存
        self.save_result("output_final.csv")
        
        print("\n=== 処理完了 ===")
        print(f"残存違反数:")
        print(f"  教師重複: {final_conflicts}件")
        print(f"  交流学級同期: {final_sync}件")
        print(f"  空きスロット: {final_empty}件")


if __name__ == "__main__":
    import os
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    fixer = TeacherAndExchangeFinalFixer(data_dir)
    fixer.run()