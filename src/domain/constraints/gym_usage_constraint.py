"""体育館使用制約 - 保健体育は同時に1クラスまで（合同授業を除く）

This refactored version recognizes legitimate joint PE sessions, particularly
for special support classes that have PE together due to small class sizes.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Set
from .base import HardConstraint, ConstraintPriority, ConstraintResult, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment, ClassReference


class GymUsageConstraintRefactored(HardConstraint):
    """体育館使用制約（合同体育を考慮）
    
    保健体育の授業は体育館が1つしかないため、
    同じ時間帯に複数のクラスで実施できない。
    ただし、設定された合同体育クラスは例外とする。
    """
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="体育館使用制約（合同体育対応）",
            description="保健体育は同時に1グループまで（合同体育を考慮）"
        )
        self.logger = logging.getLogger(__name__)
        self.joint_pe_groups = self._load_joint_pe_config()
        self.logger.info(f"Loaded joint PE groups: {self._format_joint_pe_groups()}")
    
    def _load_joint_pe_config(self) -> Dict[str, Set[ClassReference]]:
        """Load joint PE configuration from team_teaching_config.json and exchange_class_pairs.csv
        
        Returns:
            Dict mapping group names to sets of ClassReferences that have PE together
        """
        joint_pe_groups = {}
        
        try:
            # Load Grade 5 PE configuration from team_teaching_config.json
            config_path = Path(__file__).parent.parent.parent.parent / "data" / "config" / "team_teaching_config.json"
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Load special support classes PE configuration
                if 'special_support_classes' in config and 'pe_together' in config['special_support_classes']:
                    pe_together = config['special_support_classes']['pe_together']
                    
                    for class_num, data in pe_together.items():
                        classes = data.get('classes', [])
                        class_refs = set()
                        
                        for class_str in classes:
                            # Parse "1-5" format to ClassReference(1, 5)
                            parts = class_str.split('-')
                            if len(parts) == 2:
                                grade = int(parts[0])
                                class_num_int = int(parts[1])
                                class_refs.add(ClassReference(grade, class_num_int))
                        
                        if class_refs:
                            group_name = f"grade{class_num}_joint_pe"
                            joint_pe_groups[group_name] = class_refs
                            self.logger.debug(f"Loaded joint PE group {group_name}: {[str(c) for c in class_refs]}")
            
            # Load exchange class pairs from exchange_class_pairs.csv
            exchange_pairs_path = Path(__file__).parent.parent.parent.parent / "data" / "config" / "exchange_class_pairs.csv"
            
            if exchange_pairs_path.exists():
                import csv
                with open(exchange_pairs_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        exchange_class = row['exchange_class']
                        parent_class = row['parent_class']
                        
                        # Parse class references
                        exchange_parts = exchange_class.replace('年', '-').replace('組', '').split('-')
                        parent_parts = parent_class.replace('年', '-').replace('組', '').split('-')
                        
                        if len(exchange_parts) == 2 and len(parent_parts) == 2:
                            exchange_ref = ClassReference(int(exchange_parts[0]), int(exchange_parts[1]))
                            parent_ref = ClassReference(int(parent_parts[0]), int(parent_parts[1]))
                            
                            # Create joint PE group for this exchange pair
                            group_name = f"exchange_{exchange_ref}_{parent_ref}"
                            joint_pe_groups[group_name] = {exchange_ref, parent_ref}
                            self.logger.info(f"Loaded exchange pair PE group {group_name}: {exchange_ref}, {parent_ref}")
            
            # If no config found, use default Grade 5 joint PE
            if not joint_pe_groups:
                joint_pe_groups['grade5_joint_pe'] = {
                    ClassReference(1, 5),
                    ClassReference(2, 5),
                    ClassReference(3, 5)
                }
                self.logger.info("Using default Grade 5 joint PE configuration")
                
        except Exception as e:
            self.logger.error(f"Error loading joint PE configuration: {e}")
            # Use default configuration
            joint_pe_groups['grade5_joint_pe'] = {
                ClassReference(1, 5),
                ClassReference(2, 5),
                ClassReference(3, 5)
            }
        
        return joint_pe_groups
    
    def _format_joint_pe_groups(self) -> str:
        """Format joint PE groups for logging"""
        result = []
        for group_name, classes in self.joint_pe_groups.items():
            # Sort by grade then class_number
            sorted_classes = sorted(classes, key=lambda c: (c.grade, c.class_number))
            class_strs = [str(c) for c in sorted_classes]
            result.append(f"{group_name}: [{', '.join(class_strs)}]")
        return "; ".join(result)
    
    def _is_joint_pe_session(self, pe_classes: List[ClassReference]) -> bool:
        """Check if the PE classes form a legitimate joint session
        
        Args:
            pe_classes: List of classes having PE at the same time
            
        Returns:
            True if these classes are allowed to have PE together
        """
        pe_class_set = set(pe_classes)
        
        # Check if the classes match any joint PE group
        for group_name, group_classes in self.joint_pe_groups.items():
            # Check if all PE classes are part of the same joint group
            if pe_class_set.issubset(group_classes):
                self.logger.debug(f"Classes {[str(c) for c in pe_classes]} are part of joint PE group {group_name}")
                return True
        
        return False
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """配置前チェック：この時間に保健体育を配置可能かチェック"""
        
        # 保健体育以外は制約なし
        if assignment.subject.name != "保":
            return True
        
        # この時間の全ての割り当てをチェック
        assignments = schedule.get_assignments_by_time_slot(time_slot)
        pe_assignments = [a for a in assignments if a.subject.name == "保"]
        
        if not pe_assignments:
            return True  # No PE classes yet
        
        # Check if adding this class would form a valid joint PE session
        existing_pe_classes = [a.class_ref for a in pe_assignments]
        proposed_pe_classes = existing_pe_classes + [assignment.class_ref]
        
        # If it's a joint PE session, allow it
        if self._is_joint_pe_session(proposed_pe_classes):
            return True
        
        # Otherwise, only allow if no other PE classes exist
        if len(pe_assignments) >= 1:
            self.logger.debug(
                f"{time_slot}に既に保健体育が実施中 "
                f"({[str(a.class_ref) for a in pe_assignments]})。"
                f"{assignment.class_ref}は合同体育グループに含まれないため配置不可"
            )
            return False
        
        return True
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """スケジュール全体の体育館使用制約を検証"""
        violations = []
        
        # 各時間枠で保健体育の実施クラス数をチェック
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                
                # 保健体育の授業を収集
                pe_assignments = []
                pe_classes = []
                for assignment in assignments:
                    if assignment.subject.name == "保":
                        pe_assignments.append(assignment)
                        pe_classes.append(assignment.class_ref)
                
                # 2クラス以上が同時に保健体育を実施している場合
                if len(pe_classes) > 1:
                    # 合同体育セッションかチェック
                    if not self._is_joint_pe_session(pe_classes):
                        # 合同体育でない場合のみ違反
                        for assignment in pe_assignments:
                            violation = ConstraintViolation(
                                description=f"体育館使用制約違反: {time_slot}に{len(pe_classes)}クラスが同時に保健体育を実施 "
                                           f"(合同体育グループではない) - {', '.join(str(c) for c in pe_classes)}",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
                    else:
                        # 合同体育の場合はログに記録（違反ではない）
                        self.logger.info(
                            f"{time_slot}: 合同体育セッション検出 - "
                            f"{', '.join(str(c) for c in pe_classes)}"
                        )
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations
        )