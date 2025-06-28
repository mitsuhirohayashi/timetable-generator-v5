"""重み付きスケジュール評価の実装"""
import logging
from typing import List, Dict
from collections import defaultdict

from ....domain.interfaces.schedule_evaluator import ScheduleEvaluator, EvaluationBreakdown
from ....domain.interfaces.jiritsu_placement_service import JiritsuRequirement
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.interfaces.csp_configuration import ICSPConfiguration


class WeightedScheduleEvaluator(ScheduleEvaluator):
    """重み付きスケジュール評価"""
    
    def __init__(self, csp_config: ICSPConfiguration = None, constraint_validator = None):
        # 依存性注入
        if csp_config is None:
            from ....infrastructure.di_container import get_csp_configuration
            csp_config = get_csp_configuration()
            
        self.csp_config = csp_config
        self.constraint_validator = constraint_validator
        self.logger = logging.getLogger(__name__)
        
        # 評価重み（設定ファイルから読み込むことも可能）
        self.weights = {
            'jiritsu_violation': 1000,
            'constraint_violation': 100,
            'teacher_load_variance': 0.01
        }
    
    def evaluate(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement]) -> float:
        """スケジュールの品質を評価"""
        score = 0.0
        
        # 自立活動制約違反
        jiritsu_violations = self.count_jiritsu_violations(schedule, jiritsu_requirements)
        score += jiritsu_violations * self.weights['jiritsu_violation']
        
        # その他の制約違反
        if hasattr(self.constraint_validator, 'validate_all'):
            violations = self.constraint_validator.validate_all(schedule, school)
            score += len(violations) * self.weights['constraint_violation']
        elif hasattr(self.constraint_validator, 'validate_schedule'):
            result = self.constraint_validator.validate_schedule(schedule, school)
            score += len(result.violations) * self.weights['constraint_violation']
        else:
            # フォールバック: 違反なしと仮定
            score += 0
        
        # 教員負荷のバランス
        variance = self.calculate_teacher_load_variance(schedule)
        score += variance * self.weights['teacher_load_variance']
        
        return score
    
    def evaluate_with_breakdown(self, schedule: Schedule, school: School,
                               jiritsu_requirements: List[JiritsuRequirement]) -> EvaluationBreakdown:
        """詳細な評価内訳を含む評価"""
        # 各項目を計算
        jiritsu_violations = self.count_jiritsu_violations(schedule, jiritsu_requirements)
        constraint_violations = len(self.constraint_validator.validate_all(schedule, school))
        teacher_load_variance = self.calculate_teacher_load_variance(schedule)
        
        # スコアを計算
        jiritsu_score = jiritsu_violations * self.weights['jiritsu_violation']
        constraint_score = constraint_violations * self.weights['constraint_violation']
        variance_score = teacher_load_variance * self.weights['teacher_load_variance']
        total_score = jiritsu_score + constraint_score + variance_score
        
        # 詳細情報
        details = {
            'jiritsu_score': jiritsu_score,
            'constraint_score': constraint_score,
            'variance_score': variance_score,
            'jiritsu_weight': self.weights['jiritsu_violation'],
            'constraint_weight': self.weights['constraint_violation'],
            'variance_weight': self.weights['teacher_load_variance']
        }
        
        return EvaluationBreakdown(
            jiritsu_violations=jiritsu_violations,
            constraint_violations=constraint_violations,
            teacher_load_variance=teacher_load_variance,
            total_score=total_score,
            details=details
        )
    
    def count_jiritsu_violations(self, schedule: Schedule, 
                                jiritsu_requirements: List[JiritsuRequirement]) -> int:
        """自立活動制約違反の数をカウント"""
        violations = 0
        
        for req in jiritsu_requirements:
            for slot, assignment in schedule.get_all_assignments():
                if (assignment.class_ref == req.exchange_class and 
                    assignment.subject.name == "自立"):
                    parent_assignment = schedule.get_assignment(slot, req.parent_class)
                    # CSP設定からパラメータを取得
                    csp_params = self.csp_config.get_all_parameters()
                    parent_subjects = csp_params.get('parent_subjects_for_jiritsu', ["数", "英"])
                    
                    if (not parent_assignment or 
                        parent_assignment.subject.name not in parent_subjects):
                        violations += 1
                        self.logger.debug(
                            f"自立活動制約違反: {slot} {req.exchange_class}が自立だが、"
                            f"{req.parent_class}が数/英でない"
                        )
        
        return violations
    
    def calculate_teacher_load_variance(self, schedule: Schedule) -> float:
        """教員負荷の分散を計算"""
        teacher_loads = defaultdict(int)
        
        # 各教員の授業数をカウント
        for _, assignment in schedule.get_all_assignments():
            if assignment.teacher:
                teacher_loads[assignment.teacher.name] += 1
        
        if not teacher_loads:
            return 0.0
        
        # 平均と分散を計算
        avg_load = sum(teacher_loads.values()) / len(teacher_loads)
        variance = sum((load - avg_load) ** 2 for load in teacher_loads.values())
        
        return variance