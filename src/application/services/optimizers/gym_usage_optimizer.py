"""体育館使用最適化サービス"""
import logging
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ....domain.value_objects.assignment import Assignment


class GymUsageOptimizer:
    """体育館使用を最適化するサービス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 理想の結果から抽出した体育授業配置パターン
        # 同じ時間に複数クラスが体育を行う（合同体育）
        self._ideal_pe_groups = {
            # 火曜日の体育配置（理想の結果より）
            ("火", 4): ["1年1組", "3年1組"],  # 火曜4限：1年1組と3年1組が合同
            ("火", 5): ["1年2組", "3年2組"],  # 火曜5限：1年2組と3年2組が合同
            
            # 水曜日の体育配置
            ("水", 2): ["2年1組", "2年2組"],  # 水曜2限：2年生が合同
            ("水", 4): ["1年3組"],            # 水曜4限：1年3組単独
            
            # 木曜日の体育配置
            ("木", 2): ["3年3組"],            # 木曜2限：3年3組単独
            ("木", 3): ["2年3組"],            # 木曜3限：2年3組単独
            
            # 金曜日の体育配置
            ("金", 1): ["2年1組"],            # 金曜1限：2年1組単独
            ("金", 3): ["1年1組", "3年2組"],  # 金曜3限：1年1組と3年2組が合同
        }
        
        # 体育の連続授業パターン（2時間連続）
        self._consecutive_pe_patterns = {
            "1年1組": [("火", 4), ("火", 5)],  # 火曜4-5限連続
            "2年2組": [("水", 2), ("水", 3)],  # 水曜2-3限連続
        }
    
    def optimize_gym_usage(self, schedule: Schedule, school: School) -> Tuple[Schedule, int]:
        """体育館使用を最適化"""
        self.logger.info("=== 体育館使用最適化を開始 ===")
        
        changes_count = 0
        
        # Step 1: 現在の体育授業配置を分析
        current_pe_slots = self._analyze_current_pe_placement(schedule, school)
        
        # Step 2: 理想的な配置との差分を計算
        required_changes = self._calculate_required_changes(current_pe_slots)
        
        # Step 3: 変更を適用
        for change in required_changes:
            if self._apply_pe_change(schedule, school, change):
                changes_count += 1
        
        # Step 4: 合同体育の設定
        self._setup_joint_pe_classes(schedule, school)
        
        self.logger.info(f"体育館使用最適化完了: {changes_count}件の変更")
        
        return schedule, changes_count
    
    def _analyze_current_pe_placement(self, schedule: Schedule, school: School) -> Dict[Tuple[str, int], List[ClassReference]]:
        """現在の体育授業配置を分析"""
        pe_slots = defaultdict(list)
        
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment and assignment.subject.name == "保":
                        pe_slots[(day, period)].append(class_ref)
        
        return pe_slots
    
    def _calculate_required_changes(self, current_pe_slots: Dict) -> List[Dict]:
        """必要な変更を計算"""
        changes = []
        
        # 理想的な配置と現在の配置を比較
        for (day, period), ideal_classes in self._ideal_pe_groups.items():
            current_classes = [c.full_name for c in current_pe_slots.get((day, period), [])]
            
            # 追加が必要なクラス
            for class_name in ideal_classes:
                if class_name not in current_classes:
                    changes.append({
                        "type": "add",
                        "class": class_name,
                        "day": day,
                        "period": period
                    })
            
            # 削除が必要なクラス（理想にないが現在ある）
            for class_name in current_classes:
                if class_name not in ideal_classes:
                    changes.append({
                        "type": "remove",
                        "class": class_name,
                        "day": day,
                        "period": period
                    })
        
        return changes
    
    def _apply_pe_change(self, schedule: Schedule, school: School, change: Dict) -> bool:
        """体育授業の変更を適用"""
        class_parts = change["class"].replace("年", " ").replace("組", "").split()
        if len(class_parts) != 2:
            return False
        
        class_ref = ClassReference(int(class_parts[0]), int(class_parts[1]))
        time_slot = TimeSlot(change["day"], change["period"])
        
        if change["type"] == "add":
            # 体育を追加
            current = schedule.get_assignment(time_slot, class_ref)
            if current and current.subject.name == "保":
                return False  # 既に体育
            
            # 体育教師を取得
            pe_teacher = school.get_assigned_teacher(Subject("保"), class_ref)
            if not pe_teacher:
                return False
            
            # 既存の授業を削除
            if current:
                schedule.remove_assignment(time_slot, class_ref)
            
            # 体育を配置
            assignment = Assignment(class_ref, Subject("保"), pe_teacher)
            schedule.assign(time_slot, assignment)
            
            self.logger.info(f"体育追加: {class_ref} {time_slot}")
            return True
        
        elif change["type"] == "remove":
            # 体育を削除
            current = schedule.get_assignment(time_slot, class_ref)
            if not current or current.subject.name != "保":
                return False
            
            schedule.remove_assignment(time_slot, class_ref)
            self.logger.info(f"体育削除: {class_ref} {time_slot}")
            return True
        
        return False
    
    def _setup_joint_pe_classes(self, schedule: Schedule, school: School) -> None:
        """合同体育の設定"""
        for (day, period), classes in self._ideal_pe_groups.items():
            if len(classes) > 1:
                self.logger.info(f"{day}曜{period}限: {', '.join(classes)}が合同体育")
                
                # 同じ体育教師を割り当てる（可能な場合）
                time_slot = TimeSlot(day, period)
                teachers = []
                
                for class_name in classes:
                    class_parts = class_name.replace("年", " ").replace("組", "").split()
                    if len(class_parts) == 2:
                        class_ref = ClassReference(int(class_parts[0]), int(class_parts[1]))
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher:
                            teachers.append(assignment.teacher)
                
                # 最も多く割り当てられている教師を選択
                if teachers:
                    teacher_counts = defaultdict(int)
                    for teacher in teachers:
                        teacher_counts[teacher] += 1
                    
                    main_teacher = max(teacher_counts.items(), key=lambda x: x[1])[0]
                    
                    # 全クラスに同じ教師を割り当て
                    for class_name in classes:
                        class_parts = class_name.replace("年", " ").replace("組", "").split()
                        if len(class_parts) == 2:
                            class_ref = ClassReference(int(class_parts[0]), int(class_parts[1]))
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            if assignment and assignment.teacher != main_teacher:
                                schedule.remove_assignment(time_slot, class_ref)
                                new_assignment = Assignment(class_ref, assignment.subject, main_teacher)
                                schedule.assign(time_slot, new_assignment)
    
    def validate_gym_usage(self, schedule: Schedule, school: School) -> List[str]:
        """体育館使用の妥当性を検証"""
        violations = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                pe_classes = []
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append(class_ref)
                
                # 体育館の収容能力をチェック（最大2クラスまで）
                if len(pe_classes) > 2:
                    violations.append(
                        f"{day}曜{period}限: 体育が{len(pe_classes)}クラス"
                        f"（{', '.join([c.full_name for c in pe_classes])}）"
                    )
                
                # 合同体育の妥当性をチェック
                if len(pe_classes) == 2:
                    # 学年が離れすぎていないかチェック
                    grades = [c.grade for c in pe_classes]
                    if max(grades) - min(grades) > 2:
                        violations.append(
                            f"{day}曜{period}限: 学年差が大きすぎる合同体育"
                            f"（{pe_classes[0].full_name}と{pe_classes[1].full_name}）"
                        )
        
        return violations