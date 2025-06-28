"""制約特化型最適化サービス

特定の制約違反を効率的に解決するための最適化アルゴリズム
"""
import logging
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment


class ConstraintSpecificOptimizer:
    """制約特化型の最適化を行うサービス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def optimize_gym_usage(self, schedule: Schedule, school: School) -> int:
        """体育館使用制約違反を解決
        
        Args:
            schedule: 対象スケジュール
            school: 学校データ
            
        Returns:
            解決した違反数
        """
        self.logger.info("体育館使用制約の最適化を開始")
        resolved_count = 0
        
        # 体育科目を特定
        gym_subjects = {"保", "保健体育", "体育"}
        
        # 各時間帯の体育館使用状況を集計
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間帯に体育を行っているクラスを収集
                pe_classes = []
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name in gym_subjects:
                        pe_classes.append((class_ref, assignment))
                
                # 2クラス以上が体育を行っている場合、1クラスを残して他を移動
                if len(pe_classes) > 1:
                    self.logger.debug(f"{time_slot}に{len(pe_classes)}クラスが体育実施")
                    
                    # 最初のクラスを残し、他のクラスの体育を移動
                    for i in range(1, len(pe_classes)):
                        class_ref, assignment = pe_classes[i]
                        
                        # 移動先を探す
                        if self._relocate_pe_class(schedule, school, time_slot, class_ref, assignment):
                            resolved_count += 1
                            self.logger.debug(f"{class_ref}の体育を{time_slot}から移動")
        
        self.logger.info(f"体育館使用制約: {resolved_count}件解決")
        return resolved_count
    
    def _relocate_pe_class(self, schedule: Schedule, school: School, 
                          current_slot: TimeSlot, class_ref: ClassReference,
                          pe_assignment: Assignment) -> bool:
        """体育の授業を別の時間帯に移動
        
        Args:
            schedule: スケジュール
            school: 学校データ
            current_slot: 現在の時間帯
            class_ref: 対象クラス
            pe_assignment: 体育の割り当て
            
        Returns:
            移動に成功したらTrue
        """
        gym_subjects = {"保", "保健体育", "体育"}
        
        # 全ての時間帯を試す
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                target_slot = TimeSlot(day, period)
                
                # 同じ時間帯はスキップ
                if target_slot == current_slot:
                    continue
                
                # テスト期間や固定時間はスキップ
                if schedule.is_locked(target_slot, class_ref):
                    continue
                
                # その時間帯の割り当てを確認
                target_assignment = schedule.get_assignment(target_slot, class_ref)
                
                # 空きスロットの場合
                if target_assignment is None:
                    # その時間帯に他のクラスが体育をしていないか確認
                    if not self._has_pe_class_at_slot(schedule, school, target_slot, gym_subjects):
                        # 移動を実行
                        try:
                            schedule.remove_assignment(current_slot, class_ref)
                            schedule.assign(target_slot, pe_assignment)
                            return True
                        except:
                            # 失敗した場合は元に戻す
                            try:
                                schedule.assign(current_slot, pe_assignment)
                            except:
                                pass
                            continue
                
                # 交換可能な科目の場合
                elif target_assignment.subject.name not in gym_subjects:
                    # その時間帯に他のクラスが体育をしていないか確認
                    if not self._has_pe_class_at_slot(schedule, school, target_slot, gym_subjects):
                        # 交換を試みる
                        try:
                            # 一時的に削除
                            schedule.remove_assignment(current_slot, class_ref)
                            schedule.remove_assignment(target_slot, class_ref)
                            
                            # 交換して配置
                            schedule.assign(current_slot, target_assignment)
                            schedule.assign(target_slot, pe_assignment)
                            
                            return True
                        except:
                            # 失敗した場合は元に戻す
                            try:
                                schedule.assign(current_slot, pe_assignment)
                                schedule.assign(target_slot, target_assignment)
                            except:
                                pass
                            continue
        
        return False
    
    def _has_pe_class_at_slot(self, schedule: Schedule, school: School,
                             time_slot: TimeSlot, gym_subjects: Set[str]) -> bool:
        """指定時間帯に体育を行っているクラスがあるか確認"""
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name in gym_subjects:
                return True
        return False
    
    def optimize_daily_duplicates(self, schedule: Schedule, school: School) -> int:
        """日内重複制約違反を解決
        
        Args:
            schedule: 対象スケジュール
            school: 学校データ
            
        Returns:
            解決した違反数
        """
        self.logger.info("日内重複制約の最適化を開始")
        resolved_count = 0
        
        # 各クラス、各日の科目配置を確認
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                # その日の科目を収集
                daily_subjects = defaultdict(list)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        daily_subjects[assignment.subject.name].append((time_slot, assignment))
                
                # 重複している科目を特定
                for subject_name, slots in daily_subjects.items():
                    if len(slots) > 1:
                        self.logger.debug(f"{class_ref}の{day}曜日に{subject_name}が{len(slots)}回")
                        
                        # 最初の1つを残して、他を別の科目と交換
                        for i in range(1, len(slots)):
                            duplicate_slot, duplicate_assignment = slots[i]
                            
                            if self._resolve_duplicate(schedule, school, class_ref, 
                                                     duplicate_slot, duplicate_assignment, day):
                                resolved_count += 1
        
        self.logger.info(f"日内重複制約: {resolved_count}件解決")
        return resolved_count
    
    def _resolve_duplicate(self, schedule: Schedule, school: School,
                          class_ref: ClassReference, duplicate_slot: TimeSlot,
                          duplicate_assignment: Assignment, day: str) -> bool:
        """重複している科目を解決
        
        Args:
            schedule: スケジュール
            school: 学校データ
            class_ref: 対象クラス
            duplicate_slot: 重複している時間帯
            duplicate_assignment: 重複している割り当て
            day: 対象の曜日
            
        Returns:
            解決に成功したらTrue
        """
        # 他の日の時間帯と交換を試みる
        for other_day in ["月", "火", "水", "木", "金"]:
            if other_day == day:
                continue
            
            for period in range(1, 7):
                target_slot = TimeSlot(other_day, period)
                
                # ロックされている場合はスキップ
                if schedule.is_locked(target_slot, class_ref):
                    continue
                
                target_assignment = schedule.get_assignment(target_slot, class_ref)
                
                # 交換可能な科目があるか確認
                if target_assignment and target_assignment.subject.name != duplicate_assignment.subject.name:
                    # その科目が対象日に既にないか確認
                    if not self._has_subject_on_day(schedule, class_ref, day, target_assignment.subject.name):
                        # 交換を実行
                        try:
                            # 一時的に削除
                            schedule.remove_assignment(duplicate_slot, class_ref)
                            schedule.remove_assignment(target_slot, class_ref)
                            
                            # 交換して配置
                            schedule.assign(duplicate_slot, target_assignment)
                            schedule.assign(target_slot, duplicate_assignment)
                            
                            return True
                        except:
                            # エラーが発生した場合は元に戻す
                            try:
                                schedule.assign(duplicate_slot, duplicate_assignment)
                                schedule.assign(target_slot, target_assignment)
                            except:
                                pass
                                
        return False
    
    def _has_subject_on_day(self, schedule: Schedule, class_ref: ClassReference, day: str, subject_name: str) -> bool:
        """指定した日に指定した科目があるか確認
        
        Args:
            schedule: スケジュール
            class_ref: クラス参照
            day: 曜日
            subject_name: 科目名
            
        Returns:
            その日にその科目があればTrue
        """
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == subject_name:
                return True
        return False