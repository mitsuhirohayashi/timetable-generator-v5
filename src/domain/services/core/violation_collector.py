"""制約違反コレクター - 制約違反の収集と管理を専門に行うサービス"""
from typing import List, Dict, Optional, Set
from collections import defaultdict
from dataclasses import dataclass, field
import logging
from ....shared.mixins.logging_mixin import LoggingMixin

from ...value_objects.assignment import ConstraintViolation
from ...value_objects.time_slot import TimeSlot, ClassReference


@dataclass
class ViolationStatistics(LoggingMixin):
    """制約違反の統計情報"""
    total_count: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_time_slot: Dict[TimeSlot, int] = field(default_factory=lambda: defaultdict(int))
    by_class: Dict[ClassReference, int] = field(default_factory=lambda: defaultdict(int))


class ViolationCollector(LoggingMixin):
    """制約違反の収集と管理を行うサービス"""
    
    def __init__(self):
        self._violations: List[ConstraintViolation] = []
        self._violation_index: Dict[str, List[ConstraintViolation]] = defaultdict(list)
        super().__init__()
    
    def add_violation(self, violation: ConstraintViolation) -> None:
        """制約違反を追加"""
        self._violations.append(violation)
        
        # インデックスに追加（型別）
        violation_type = self._get_violation_type(violation)
        self._violation_index[violation_type].append(violation)
        
        self.logger.debug(f"制約違反を追加: {violation.description}")
    
    def add_violations(self, violations: List[ConstraintViolation]) -> None:
        """複数の制約違反を一括追加"""
        for violation in violations:
            self.add_violation(violation)
    
    def clear(self) -> None:
        """全ての制約違反をクリア"""
        self._violations.clear()
        self._violation_index.clear()
        self.logger.debug("全ての制約違反をクリアしました")
    
    def get_all_violations(self) -> List[ConstraintViolation]:
        """全ての制約違反を取得"""
        return self._violations.copy()
    
    def get_violations_by_type(self, violation_type: str) -> List[ConstraintViolation]:
        """指定したタイプの制約違反を取得"""
        return self._violation_index.get(violation_type, []).copy()
    
    def get_violations_by_severity(self, severity: str) -> List[ConstraintViolation]:
        """指定した重要度の制約違反を取得"""
        return [v for v in self._violations if v.severity == severity]
    
    def get_violations_by_time_slot(self, time_slot: TimeSlot) -> List[ConstraintViolation]:
        """指定した時間枠に関する制約違反を取得"""
        return [v for v in self._violations if v.time_slot == time_slot]
    
    def get_violations_by_class(self, class_ref: ClassReference) -> List[ConstraintViolation]:
        """指定したクラスに関する制約違反を取得"""
        violations = []
        for v in self._violations:
            if v.assignment and v.assignment.class_ref == class_ref:
                violations.append(v)
        return violations
    
    def has_violations(self) -> bool:
        """制約違反が存在するかどうか"""
        return len(self._violations) > 0
    
    def count(self) -> int:
        """制約違反の総数"""
        return len(self._violations)
    
    def get_statistics(self) -> ViolationStatistics:
        """制約違反の統計情報を取得"""
        stats = ViolationStatistics()
        stats.total_count = len(self._violations)
        
        for violation in self._violations:
            # タイプ別
            vtype = self._get_violation_type(violation)
            stats.by_type[vtype] = stats.by_type.get(vtype, 0) + 1
            
            # 重要度別
            if violation.severity:
                stats.by_severity[violation.severity] = \
                    stats.by_severity.get(violation.severity, 0) + 1
            
            # 時間枠別
            if violation.time_slot:
                stats.by_time_slot[violation.time_slot] += 1
            
            # クラス別
            if violation.assignment and violation.assignment.class_ref:
                stats.by_class[violation.assignment.class_ref] += 1
        
        return stats
    
    def get_critical_violations(self) -> List[ConstraintViolation]:
        """重大な制約違反（ERROR以上）を取得"""
        critical_severities = {"ERROR", "CRITICAL", "FATAL"}
        return [v for v in self._violations 
                if v.severity and v.severity.upper() in critical_severities]
    
    def get_summary(self) -> str:
        """制約違反のサマリーを取得"""
        if not self._violations:
            return "制約違反なし"
        
        stats = self.get_statistics()
        lines = [
            f"制約違反総数: {stats.total_count}件",
            "タイプ別:"
        ]
        
        for vtype, count in sorted(stats.by_type.items()):
            lines.append(f"  - {vtype}: {count}件")
        
        if stats.by_severity:
            lines.append("重要度別:")
            for severity, count in sorted(stats.by_severity.items()):
                lines.append(f"  - {severity}: {count}件")
        
        return "\n".join(lines)
    
    def filter_violations(self, 
                         violation_type: Optional[str] = None,
                         severity: Optional[str] = None,
                         time_slot: Optional[TimeSlot] = None,
                         class_ref: Optional[ClassReference] = None) -> List[ConstraintViolation]:
        """条件に基づいて制約違反をフィルタリング"""
        violations = self._violations
        
        if violation_type:
            violations = [v for v in violations if self._get_violation_type(v) == violation_type]
        
        if severity:
            violations = [v for v in violations if v.severity == severity]
        
        if time_slot:
            violations = [v for v in violations if v.time_slot == time_slot]
        
        if class_ref:
            violations = [v for v in violations 
                         if v.assignment and v.assignment.class_ref == class_ref]
        
        return violations
    
    def merge(self, other: 'ViolationCollector') -> None:
        """他のViolationCollectorの内容をマージ"""
        self.add_violations(other.get_all_violations())
    
    def _get_violation_type(self, violation: ConstraintViolation) -> str:
        """制約違反のタイプを判定"""
        description = violation.description.lower()
        
        # キーワードベースの分類
        if "教員" in description or "teacher" in description:
            return "teacher_conflict"
        elif "日内重複" in description or "daily duplicate" in description:
            return "daily_duplicate"
        elif "体育館" in description or "gym" in description:
            return "gym_usage"
        elif "自立" in description or "jiritsu" in description:
            return "jiritsu"
        elif "5組" in description or "grade5" in description:
            return "grade5_sync"
        elif "固定" in description or "fixed" in description:
            return "fixed_subject"
        elif "標準時数" in description or "standard hours" in description:
            return "standard_hours"
        else:
            return "other"