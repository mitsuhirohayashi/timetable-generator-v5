"""
制約違反分析サービス
制約違反を分析し、QandAシステムと連携して質問を生成する
"""

import logging
from typing import List, Dict, Optional
from collections import defaultdict

from ..services.qanda_service import ImprovedQandAService as QandAService
from ...domain.constraints.base import ConstraintViolation
from ...domain.value_objects.time_slot import TimeSlot


class ConstraintViolationAnalyzer:
    """制約違反を分析し、解決のための質問を生成するサービス"""
    
    def __init__(self, qanda_service: Optional[QandAService] = None):
        self.logger = logging.getLogger(__name__)
        self.qanda_service = qanda_service or QandAService()
    
    def analyze_violations(self, violations: List[ConstraintViolation]) -> Dict[str, any]:
        """
        制約違反を分析し、パターンを特定
        
        Args:
            violations: 制約違反のリスト
            
        Returns:
            分析結果の辞書
        """
        analysis = {
            'total_violations': len(violations),
            'by_type': defaultdict(list),
            'by_class': defaultdict(list),
            'by_teacher': defaultdict(list),
            'patterns': [],
            'questions_generated': []
        }
        
        # 違反を分類
        for violation in violations:
            # 違反タイプ別
            violation_type = self._categorize_violation(violation)
            analysis['by_type'][violation_type].append(violation)
            
            # クラス別
            if hasattr(violation, 'assignment') and violation.assignment:
                class_str = str(violation.assignment.class_ref)
                analysis['by_class'][class_str].append(violation)
                
                # 教師別
                if violation.assignment.teacher:
                    teacher_name = violation.assignment.teacher.name
                    analysis['by_teacher'][teacher_name].append(violation)
        
        # パターンを検出
        analysis['patterns'] = self._detect_patterns(analysis)
        
        # 質問を生成
        questions = self._generate_questions_from_patterns(analysis['patterns'])
        for question in questions:
            if self.qanda_service.add_system_question(question['text'], question.get('context')):
                analysis['questions_generated'].append(question)
        
        return analysis
    
    def _categorize_violation(self, violation: ConstraintViolation) -> str:
        """違反をカテゴリー分類"""
        # violationがConstraintViolationオブジェクトか確認
        if hasattr(violation, 'description'):
            desc = violation.description.lower()
        elif isinstance(violation, str):
            desc = violation.lower()
        else:
            desc = str(violation).lower()
        
        if '教師' in desc and '重複' in desc:
            return 'teacher_conflict'
        elif '日内重複' in desc:
            return 'daily_duplicate'
        elif '体育館' in desc:
            return 'gym_usage'
        elif '自立' in desc:
            return 'jiritsu_activity'
        elif '時数' in desc:
            return 'subject_hours'
        elif '会議' in desc or '不在' in desc:
            return 'teacher_unavailable'
        else:
            return 'other'
    
    def _detect_patterns(self, analysis: Dict[str, any]) -> List[Dict[str, any]]:
        """違反のパターンを検出"""
        patterns = []
        
        # 教師重複パターン
        for teacher, violations in analysis['by_teacher'].items():
            teacher_conflicts = [v for v in violations if self._categorize_violation(v) == 'teacher_conflict']
            if len(teacher_conflicts) > 3:  # 3件以上の重複がある場合
                # 時間帯別に集計
                time_conflicts = defaultdict(list)
                for v in teacher_conflicts:
                    if hasattr(v, 'time_slot') and v.time_slot:
                        key = (v.time_slot.day, v.time_slot.period)
                        time_conflicts[key].append(v)
                
                # 同時刻に3クラス以上を担当している場合
                for (day, period), conflicts in time_conflicts.items():
                    if len(conflicts) >= 3:
                        classes = [str(c.assignment.class_ref) for c in conflicts if hasattr(c, 'assignment') and c.assignment]
                        patterns.append({
                            'type': 'multiple_class_teaching',
                            'teacher': teacher,
                            'time': f"{day}{period}限",
                            'classes': classes,
                            'count': len(classes)
                        })
        
        # 特定クラスの違反集中パターン
        for class_ref, violations in analysis['by_class'].items():
            if len(violations) > 5:  # 5件以上の違反がある場合
                violation_types = defaultdict(int)
                for v in violations:
                    violation_types[self._categorize_violation(v)] += 1
                
                patterns.append({
                    'type': 'class_violation_concentration',
                    'class': class_ref,
                    'total_violations': len(violations),
                    'violation_breakdown': dict(violation_types)
                })
        
        # 自立活動の配置問題パターン
        jiritsu_violations = analysis['by_type'].get('jiritsu_activity', [])
        if len(jiritsu_violations) > 0:
            jiritsu_classes = defaultdict(int)
            for v in jiritsu_violations:
                if hasattr(v, 'assignment') and v.assignment:
                    jiritsu_classes[str(v.assignment.class_ref)] += 1
            
            for class_ref, count in jiritsu_classes.items():
                if count > 2:  # 2件以上の自立活動違反
                    patterns.append({
                        'type': 'jiritsu_placement_issue',
                        'class': class_ref,
                        'violation_count': count
                    })
        
        return patterns
    
    def _generate_questions_from_patterns(self, patterns: List[Dict[str, any]]) -> List[Dict[str, str]]:
        """検出されたパターンから質問を生成"""
        questions = []
        
        for pattern in patterns:
            if pattern['type'] == 'multiple_class_teaching':
                question = {
                    'text': f"{pattern['teacher']}先生が{pattern['time']}に{', '.join(pattern['classes'])}の{pattern['count']}クラスを同時に教えることはできません。どのように教師配置を調整すべきですか？",
                    'context': f"違反パターン: 教師の同時複数クラス担当"
                }
                questions.append(question)
            
            elif pattern['type'] == 'class_violation_concentration':
                main_violation = max(pattern['violation_breakdown'].items(), key=lambda x: x[1])
                question = {
                    'text': f"{pattern['class']}で{pattern['total_violations']}件の制約違反が発生しています（主に{main_violation[0]}）。このクラスの時間割をどのように改善すべきですか？",
                    'context': f"違反内訳: {pattern['violation_breakdown']}"
                }
                questions.append(question)
            
            elif pattern['type'] == 'jiritsu_placement_issue':
                question = {
                    'text': f"{pattern['class']}の自立活動配置で{pattern['violation_count']}件の違反が発生しています。自立活動の配置ルールを見直す必要がありますか？",
                    'context': "自立活動は親学級が数学または英語の時のみ配置可能"
                }
                questions.append(question)
        
        return questions
    
    def suggest_solutions(self, violation_analysis: Dict[str, any]) -> List[str]:
        """
        違反分析結果から解決策を提案
        
        Args:
            violation_analysis: analyze_violationsの結果
            
        Returns:
            提案される解決策のリスト
        """
        suggestions = []
        
        # 教師重複が多い場合
        teacher_conflicts = violation_analysis['by_type'].get('teacher_conflict', [])
        if len(teacher_conflicts) > 10:
            suggestions.append("教師の担当クラス数を見直し、複数の教師で分担することを検討してください。")
        
        # 日内重複が多い場合
        daily_duplicates = violation_analysis['by_type'].get('daily_duplicate', [])
        if len(daily_duplicates) > 5:
            suggestions.append("1日1コマ制限を厳密に適用し、科目の配置を分散させてください。")
        
        # 特定のクラスに違反が集中している場合
        for class_ref, violations in violation_analysis['by_class'].items():
            if len(violations) > 8:
                suggestions.append(f"{class_ref}の時間割を全面的に見直すことをお勧めします。")
        
        return suggestions