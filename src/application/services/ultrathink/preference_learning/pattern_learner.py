"""パターン学習モジュール

スケジュールから成功パターンと失敗パターンを学習します。
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from .data_models import LearningState
from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School


class PatternLearner:
    """パターン学習クラス"""
    
    def __init__(self, state: LearningState):
        """初期化
        
        Args:
            state: 学習状態
        """
        self.logger = logging.getLogger(__name__)
        self.state = state
    
    def learn_patterns(
        self,
        schedule: Schedule,
        school: School,
        violations: List[Any]
    ) -> List[Dict]:
        """パターンを学習
        
        Args:
            schedule: スケジュール
            school: 学校情報
            violations: 制約違反リスト
            
        Returns:
            新しく学習したパターンのリスト
        """
        new_patterns = []
        
        # 成功パターンの抽出
        if len(violations) < 10:  # 違反が少ない場合
            # 各教師の配置パターンを分析
            teacher_patterns = defaultdict(list)
            
            for time_slot, assignment in schedule.get_all_assignments():
                if assignment.teacher:
                    teacher_patterns[assignment.teacher.name].append({
                        'time_slot': time_slot,
                        'class_ref': assignment.class_ref,
                        'subject': assignment.subject.name
                    })
            
            # パターンを抽出
            for teacher_name, placements in teacher_patterns.items():
                if len(placements) >= 3:
                    # 連続授業パターン
                    consecutive = self.find_consecutive_patterns(placements)
                    if consecutive:
                        new_patterns.append({
                            'type': 'consecutive',
                            'teacher': teacher_name,
                            'pattern': consecutive
                        })
                    
                    # 時間帯集中パターン
                    time_concentration = self.find_time_concentration(placements)
                    if time_concentration:
                        new_patterns.append({
                            'type': 'time_concentration',
                            'teacher': teacher_name,
                            'pattern': time_concentration
                        })
        
        # パターンをデータベースに追加
        for pattern in new_patterns:
            self.state.success_patterns.append({
                'pattern': pattern,
                'timestamp': datetime.now().isoformat(),
                'violation_count': len(violations)
            })
        
        return new_patterns
    
    def find_consecutive_patterns(
        self,
        placements: List[Dict]
    ) -> Optional[Dict]:
        """連続授業パターンを検出
        
        Args:
            placements: 配置リスト
            
        Returns:
            最も長い連続パターン、またはNone
        """
        # 曜日ごとに整理
        by_day = defaultdict(list)
        for p in placements:
            by_day[p['time_slot'].day].append(p)
        
        consecutive_patterns = []
        for day, day_placements in by_day.items():
            # 時限でソート
            day_placements.sort(key=lambda x: x['time_slot'].period)
            
            # 連続をチェック
            consecutive = []
            for i in range(len(day_placements) - 1):
                if day_placements[i]['time_slot'].period + 1 == day_placements[i+1]['time_slot'].period:
                    if not consecutive:
                        consecutive = [day_placements[i], day_placements[i+1]]
                    else:
                        consecutive.append(day_placements[i+1])
                else:
                    if len(consecutive) >= 2:
                        consecutive_patterns.append({
                            'day': day,
                            'periods': [p['time_slot'].period for p in consecutive],
                            'length': len(consecutive)
                        })
                    consecutive = []
            
            if len(consecutive) >= 2:
                consecutive_patterns.append({
                    'day': day,
                    'periods': [p['time_slot'].period for p in consecutive],
                    'length': len(consecutive)
                })
        
        if consecutive_patterns:
            # 最も長い連続を返す
            return max(consecutive_patterns, key=lambda x: x['length'])
        
        return None
    
    def find_time_concentration(
        self,
        placements: List[Dict]
    ) -> Optional[Dict]:
        """時間帯集中パターンを検出
        
        Args:
            placements: 配置リスト
            
        Returns:
            時間帯集中パターン、またはNone
        """
        # 時限ごとにカウント
        period_counts = defaultdict(int)
        for p in placements:
            period_counts[p['time_slot'].period] += 1
        
        # 最も多い時限
        if period_counts:
            max_period = max(period_counts, key=period_counts.get)
            max_count = period_counts[max_period]
            
            # 全体の30%以上なら集中パターン
            if max_count / len(placements) > 0.3:
                return {
                    'preferred_period': max_period,
                    'concentration': max_count / len(placements),
                    'count': max_count
                }
        
        return None
    
    def record_placement(
        self,
        assignment,
        time_slot,
        satisfaction: float,
        pattern_analysis: Dict
    ):
        """配置を記録
        
        Args:
            assignment: 配置情報
            time_slot: タイムスロット
            satisfaction: 満足度
            pattern_analysis: パターン分析結果
        """
        teacher_name = assignment.teacher.name
        
        # 教師の学習データを初期化
        if teacher_name not in self.state.teacher_learning_data:
            self.state.teacher_learning_data[teacher_name] = {
                'placements': [],
                'average_satisfaction': 0.5,
                'improvement_rate': 0.0,
                'best_patterns': [],
                'worst_patterns': []
            }
        
        # 配置データを記録
        placement_data = {
            'time_slot': {'day': time_slot.day, 'period': time_slot.period},
            'class_ref': f"{assignment.class_ref.grade}-{assignment.class_ref.class_number}",
            'subject': assignment.subject.name,
            'satisfaction': satisfaction,
            'timestamp': datetime.now().isoformat()
        }
        
        teacher_data = self.state.teacher_learning_data[teacher_name]
        teacher_data['placements'].append(placement_data)
        
        # 最新100件のみ保持
        if len(teacher_data['placements']) > 100:
            teacher_data['placements'] = teacher_data['placements'][-100:]
        
        # 平均満足度を更新
        recent_satisfactions = [
            p['satisfaction'] for p in teacher_data['placements'][-20:]
        ]
        teacher_data['average_satisfaction'] = sum(recent_satisfactions) / len(recent_satisfactions)
        
        # パターンを記録
        if satisfaction > 0.8:
            self.state.success_patterns.append({
                'teacher': teacher_name,
                'pattern': placement_data,
                'context': pattern_analysis.get('teacher_patterns', {}).get(teacher_name, {})
            })
        elif satisfaction < 0.3:
            self.state.failure_patterns.append({
                'teacher': teacher_name,
                'pattern': placement_data,
                'context': pattern_analysis.get('teacher_patterns', {}).get(teacher_name, {})
            })