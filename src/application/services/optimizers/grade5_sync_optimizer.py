"""5組同期最適化サービス - 5組の教科同期を修正"""
import logging
from typing import List, Dict, Set, Tuple, Optional
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from ....domain.value_objects.assignment import Assignment


class Grade5SyncOptimizer:
    """5組（1-5, 2-5, 3-5）の教科同期を最適化するサービス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 5組のクラス
        self.grade5_classes = [
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        ]
        
        # 固定教科（移動不可）
        self.fixed_subjects = {"欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家"}
    
    def fix_grade5_sync_violations(self, schedule: Schedule, school: School) -> int:
        """5組の同期違反を修正
        
        Returns:
            修正した違反の数
        """
        self.logger.info("=== 5組同期違反の修正を開始 ===")
        fixed_count = 0
        
        # 全時間枠をチェック
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間の5組の教科を取得
                subjects = self._get_grade5_subjects(schedule, time_slot)
                
                # 同期が取れていない場合
                if not self._is_synchronized(subjects):
                    self.logger.info(f"{time_slot}で5組の同期違反: {subjects}")
                    
                    # 修正を試みる
                    if self._fix_sync_violation(schedule, school, time_slot, subjects):
                        fixed_count += 1
        
        self.logger.info(f"=== 5組同期修正完了: {fixed_count}件修正 ===")
        return fixed_count
    
    def _get_grade5_subjects(self, schedule: Schedule, time_slot: TimeSlot) -> Dict[ClassReference, Optional[str]]:
        """指定時間の5組の教科を取得"""
        subjects = {}
        
        for class_ref in self.grade5_classes:
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                subjects[class_ref] = assignment.subject.name
            else:
                subjects[class_ref] = None
        
        return subjects
    
    def _is_synchronized(self, subjects: Dict[ClassReference, Optional[str]]) -> bool:
        """5組の教科が同期しているかチェック"""
        values = list(subjects.values())
        
        # 全て同じ値（Noneも含む）なら同期している
        return all(v == values[0] for v in values)
    
    def _fix_sync_violation(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot,
        subjects: Dict[ClassReference, Optional[str]]
    ) -> bool:
        """同期違反を修正
        
        Returns:
            修正に成功した場合True
        """
        # 最も多い教科を特定（多数決）
        subject_counts = {}
        for subject in subjects.values():
            if subject is not None:
                subject_counts[subject] = subject_counts.get(subject, 0) + 1
        
        if not subject_counts:
            # 全て空きの場合は修正不要
            return True
        
        # 最も多い教科を採用
        target_subject = max(subject_counts.items(), key=lambda x: x[1])[0]
        
        # 固定教科の場合は特別な処理
        if target_subject in self.fixed_subjects:
            # 欠の場合は全クラスを欠に統一
            if target_subject == "欠":
                return self._unify_to_kekka(schedule, school, time_slot)
            else:
                self.logger.warning(f"{target_subject}は固定教科のため同期修正が困難")
                return False
        
        # 各クラスを目標教科に統一
        success = True
        for class_ref, current_subject in subjects.items():
            if current_subject != target_subject:
                if not self._change_subject_to(schedule, school, class_ref, time_slot, target_subject):
                    success = False
        
        return success
    
    def _unify_to_kekka(self, schedule: Schedule, school: School, time_slot: TimeSlot) -> bool:
        """全ての5組を「欠」に統一"""
        success = True
        
        for class_ref in self.grade5_classes:
            assignment = schedule.get_assignment(time_slot, class_ref)
            
            # 既に欠の場合はスキップ
            if assignment and assignment.subject.name == "欠":
                continue
            
            # ロックされている場合はスキップ
            if schedule.is_locked(time_slot, class_ref):
                self.logger.warning(f"{class_ref}の{time_slot}はロックされているため変更不可")
                success = False
                continue
            
            # 既存の割り当てを削除
            if assignment:
                schedule.remove_assignment(time_slot, class_ref)
            
            # 欠を配置
            kekka_assignment = Assignment(class_ref, Subject("欠"), None)
            if not schedule.assign(time_slot, kekka_assignment):
                self.logger.error(f"{class_ref}の{time_slot}に欠を配置できませんでした")
                success = False
        
        return success
    
    def _change_subject_to(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        target_subject: str
    ) -> bool:
        """指定クラスの指定時間を目標教科に変更"""
        # ロックチェック
        if schedule.is_locked(time_slot, class_ref):
            self.logger.warning(f"{class_ref}の{time_slot}はロックされているため変更不可")
            return False
        
        # 現在の割り当てを削除
        current = schedule.get_assignment(time_slot, class_ref)
        if current:
            schedule.remove_assignment(time_slot, class_ref)
        
        # 目標教科の教師を取得
        target_subject_obj = Subject(target_subject)
        teacher = school.get_assigned_teacher(target_subject_obj, class_ref)
        
        if not teacher:
            self.logger.warning(f"{class_ref}の{target_subject}担当教師が見つかりません")
            # 元に戻す
            if current:
                schedule.assign(time_slot, current)
            return False
        
        # 新しい割り当てを作成
        new_assignment = Assignment(class_ref, target_subject_obj, teacher)
        
        # 配置を試みる
        if schedule.assign(time_slot, new_assignment):
            self.logger.info(f"{class_ref}の{time_slot}を{target_subject}に変更しました")
            return True
        else:
            # 失敗したら元に戻す
            if current:
                schedule.assign(time_slot, current)
            return False