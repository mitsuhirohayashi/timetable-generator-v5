"""教師プロファイリングモジュール

教師の特性、強み、好みを分析しプロファイルを生成します。
"""
import logging
from typing import Dict, List, Any
import numpy as np

from ..teacher_pattern_analyzer import TeacherPreference, TeachingPattern


class TeacherProfiler:
    """教師プロファイリングクラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
    
    def generate_teacher_profile(
        self,
        preference: TeacherPreference,
        pattern: TeachingPattern
    ) -> str:
        """教師のプロファイルを生成
        
        Args:
            preference: 教師の好み
            pattern: 教育パターン
            
        Returns:
            プロファイル文字列
        """
        profiles = []
        
        # 時間帯タイプ
        if preference.morning_preference > 0.65:
            profiles.append("朝型")
        elif preference.afternoon_preference > 0.65:
            profiles.append("午後型")
        else:
            profiles.append("バランス型")
        
        # 連続授業の好み
        if preference.consecutive_preference > 0.6:
            profiles.append("連続授業を好む")
        elif preference.consecutive_preference < 0.4:
            profiles.append("分散配置を好む")
        
        # ワークスタイル
        if preference.daily_max_preferred <= 3:
            profiles.append("軽負荷志向")
        elif preference.daily_max_preferred >= 5:
            profiles.append("集中作業型")
        
        return "、".join(profiles)
    
    def identify_strengths(
        self,
        preference: TeacherPreference,
        pattern: TeachingPattern,
        learning_data: Dict
    ) -> List[str]:
        """教師の強みを特定
        
        Args:
            preference: 教師の好み
            pattern: 教育パターン
            learning_data: 学習データ
            
        Returns:
            強みのリスト
        """
        strengths = []
        
        # 高い満足度
        if learning_data.get('average_satisfaction', 0) > 0.75:
            strengths.append("高い授業満足度を維持")
        
        # 効率性
        if pattern.efficiency_score > 0.7:
            strengths.append("効率的な授業運営")
        
        # 柔軟性
        day_variance = np.var(list(preference.day_preferences.values()))
        if day_variance < 0.05:
            strengths.append("曜日を問わず安定したパフォーマンス")
        
        # 協調性
        if len(pattern.collaboration_patterns) > 5:
            strengths.append("他の教師との良好な協力関係")
        
        return strengths
    
    def summarize_preferences(self, preference: TeacherPreference) -> Dict[str, Any]:
        """好みを要約
        
        Args:
            preference: 教師の好み
            
        Returns:
            好みの要約
        """
        return {
            'time_preference': "朝型" if preference.morning_preference > 0.6 else "午後型" if preference.afternoon_preference > 0.6 else "バランス型",
            'favorite_days': [
                day for day, pref in preference.day_preferences.items()
                if pref > 0.6
            ],
            'avoid_days': [
                day for day, pref in preference.day_preferences.items()
                if pref < 0.4
            ],
            'preferred_workload': f"1日{preference.daily_max_preferred}コマ以内",
            'consecutive_style': "連続希望" if preference.consecutive_preference > 0.6 else "分散希望"
        }
    
    def analyze_collaboration_preferences(
        self,
        teacher_name: str,
        pattern: TeachingPattern
    ) -> Dict[str, Any]:
        """協力関係の好みを分析
        
        Args:
            teacher_name: 教師名
            pattern: 教育パターン
            
        Returns:
            協力関係の分析結果
        """
        return {
            'frequent_partners': sorted(
                pattern.collaboration_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'collaboration_score': len(pattern.collaboration_patterns) / 20,  # 正規化
            'team_teaching_suitable': len(pattern.collaboration_patterns) > 10
        }
    
    def generate_optimization_suggestions(
        self,
        teacher_name: str,
        preference: TeacherPreference,
        pattern: TeachingPattern,
        learning_data: Dict
    ) -> List[str]:
        """最適化の提案を生成
        
        Args:
            teacher_name: 教師名
            preference: 教師の好み
            pattern: 教育パターン
            learning_data: 学習データ
            
        Returns:
            最適化提案のリスト
        """
        suggestions = []
        
        # 満足度が低い場合
        if learning_data.get('average_satisfaction', 0.5) < 0.5:
            if preference.morning_preference > 0.6:
                suggestions.append("午前中の授業を増やすことで満足度が向上する可能性があります")
            if preference.consecutive_preference > 0.6:
                suggestions.append("連続授業の配置を検討してください")
        
        # ワークロードの最適化
        avg_daily = sum(len(v) for v in pattern.time_slot_frequency.values()) / 5
        if avg_daily > preference.daily_max_preferred:
            suggestions.append(f"1日の授業数を{preference.daily_max_preferred}コマ以内に調整することを推奨します")
        
        # 協力関係の活用
        if pattern.collaboration_patterns:
            top_partner = max(pattern.collaboration_patterns.items(), key=lambda x: x[1])[0]
            suggestions.append(f"{top_partner}先生との協力授業の機会を増やすことを検討してください")
        
        return suggestions
    
    def generate_insight(
        self,
        teacher_name: str,
        old_pref: TeacherPreference,
        new_pref: TeacherPreference
    ) -> str:
        """洞察を生成
        
        Args:
            teacher_name: 教師名
            old_pref: 以前の好み
            new_pref: 新しい好み
            
        Returns:
            洞察文字列
        """
        insights = []
        
        # 時間帯の変化
        if new_pref.morning_preference > old_pref.morning_preference + 0.1:
            insights.append(f"{teacher_name}先生は午前中の授業を好む傾向が強まっています")
        elif new_pref.morning_preference < old_pref.morning_preference - 0.1:
            insights.append(f"{teacher_name}先生は午後の授業を好む傾向が強まっています")
        
        # 連続授業の変化
        if new_pref.consecutive_preference > old_pref.consecutive_preference + 0.1:
            insights.append(f"{teacher_name}先生は連続授業を効率的にこなせるようになっています")
        
        return "。".join(insights) if insights else f"{teacher_name}先生の好みに変化が見られました"
    
    def preference_changed_significantly(
        self,
        old_pref: TeacherPreference,
        new_pref: TeacherPreference
    ) -> bool:
        """好みが大きく変化したか判定
        
        Args:
            old_pref: 以前の好み
            new_pref: 新しい好み
            
        Returns:
            大きな変化があった場合True
        """
        threshold = 0.1
        
        # 各属性の変化をチェック
        if abs(old_pref.morning_preference - new_pref.morning_preference) > threshold:
            return True
        if abs(old_pref.consecutive_preference - new_pref.consecutive_preference) > threshold:
            return True
        
        # 曜日の好みの変化
        for day in ["月", "火", "水", "木", "金"]:
            if abs(old_pref.day_preferences[day] - new_pref.day_preferences[day]) > threshold:
                return True
        
        return False
    
    def get_satisfaction_trend(self, teacher_name: str, teacher_data: Dict) -> List[float]:
        """満足度のトレンドを取得
        
        Args:
            teacher_name: 教師名
            teacher_data: 教師の学習データ
            
        Returns:
            満足度トレンドのリスト
        """
        placements = teacher_data.get('placements', [])
        
        if len(placements) < 5:
            return []
        
        # 5件ごとの移動平均
        trend = []
        for i in range(0, len(placements) - 4):
            window = placements[i:i+5]
            avg = sum(p['satisfaction'] for p in window) / 5
            trend.append(avg)
        
        return trend