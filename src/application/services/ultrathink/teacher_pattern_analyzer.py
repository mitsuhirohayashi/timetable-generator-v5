"""
教師パターン分析器

教師の配置パターンを分析し、各教師の好みや傾向を検出します。
- 好みの時間帯（午前・午後）
- 連続授業の傾向
- 曜日別の配置傾向
- 教師間の協力関係
"""
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import json
import os

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Teacher, Subject
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment


@dataclass
class TeacherPreference:
    """教師の好み・傾向データ"""
    teacher_name: str
    
    # 時間帯の好み（0.0～1.0: 高いほど好み）
    morning_preference: float = 0.5  # 午前中
    afternoon_preference: float = 0.5  # 午後
    first_period_preference: float = 0.5  # 1限目
    last_period_preference: float = 0.5  # 6限目
    
    # 曜日別の好み
    day_preferences: Dict[str, float] = field(default_factory=lambda: {
        "月": 0.5, "火": 0.5, "水": 0.5, "木": 0.5, "金": 0.5
    })
    
    # 連続授業の好み
    consecutive_preference: float = 0.5  # 連続授業を好むか
    max_consecutive_preferred: int = 2  # 好ましい最大連続数
    
    # 特定クラスとの相性
    class_affinities: Dict[str, float] = field(default_factory=dict)
    
    # ワークライフバランス
    daily_max_preferred: int = 4  # 1日の好ましい最大授業数
    weekly_max_preferred: int = 18  # 週の好ましい最大授業数
    break_time_preference: float = 0.7  # 休憩時間の重要度
    
    # 統計データ
    total_observations: int = 0
    satisfaction_scores: List[float] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class TeachingPattern:
    """教師の教育パターン"""
    teacher_name: str
    
    # 時間帯別の配置頻度
    time_slot_frequency: Dict[Tuple[str, int], int] = field(default_factory=dict)
    
    # 連続授業のパターン
    consecutive_patterns: List[int] = field(default_factory=list)  # 連続数の履歴
    
    # クラス別の配置頻度
    class_frequency: Dict[str, int] = field(default_factory=dict)
    
    # 科目別の配置時間帯
    subject_time_preferences: Dict[str, Dict[Tuple[str, int], int]] = field(default_factory=dict)
    
    # 教師間の協力パターン
    collaboration_patterns: Dict[str, int] = field(default_factory=dict)  # 同じ時間帯に教える頻度
    
    # パフォーマンス指標
    violation_rate: float = 0.0  # 制約違反率
    student_feedback_score: float = 0.5  # 生徒からのフィードバック（仮想）
    efficiency_score: float = 0.5  # 効率性スコア


class TeacherPatternAnalyzer:
    """教師の配置パターンを分析するクラス"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Args:
            data_dir: パターンデータを保存するディレクトリ
        """
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "teacher_patterns")
        
        # データディレクトリの作成
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # 教師の好みデータ
        self.preferences: Dict[str, TeacherPreference] = {}
        
        # 教師のパターンデータ
        self.patterns: Dict[str, TeachingPattern] = {}
        
        # 分析履歴
        self.analysis_history: List[Dict] = []
        
        # データの読み込み
        self._load_data()
    
    def analyze_schedule(self, schedule: Schedule, school: School) -> Dict[str, Any]:
        """スケジュールから教師のパターンを分析"""
        self.logger.info("教師パターンの分析を開始")
        
        analysis_result = {
            'timestamp': datetime.now().isoformat(),
            'teacher_patterns': {},
            'collaboration_matrix': {},
            'time_preferences': {},
            'workload_balance': {},
            'recommendations': []
        }
        
        # 各教師のパターンを収集
        teacher_schedules = self._collect_teacher_schedules(schedule, school)
        
        for teacher_name, assignments in teacher_schedules.items():
            # パターンの更新
            pattern = self._update_teacher_pattern(teacher_name, assignments)
            
            # 好みの推定
            preference = self._estimate_teacher_preference(teacher_name, pattern)
            
            # 分析結果に追加
            analysis_result['teacher_patterns'][teacher_name] = {
                'preference': self._preference_to_dict(preference),
                'pattern': self._pattern_to_dict(pattern),
                'satisfaction_score': self._calculate_satisfaction(assignments, preference),
                'workload': len(assignments)
            }
        
        # 教師間の協力関係を分析
        analysis_result['collaboration_matrix'] = self._analyze_collaboration(schedule, school)
        
        # 時間帯別の傾向を分析
        analysis_result['time_preferences'] = self._analyze_time_preferences()
        
        # ワークロードバランスを分析
        analysis_result['workload_balance'] = self._analyze_workload_balance(teacher_schedules)
        
        # 改善提案を生成
        analysis_result['recommendations'] = self._generate_recommendations(analysis_result)
        
        # 履歴に追加
        self.analysis_history.append(analysis_result)
        
        # データを保存
        self._save_data()
        
        self.logger.info("教師パターンの分析完了")
        return analysis_result
    
    def get_teacher_preference(self, teacher_name: str) -> TeacherPreference:
        """教師の好みデータを取得"""
        if teacher_name not in self.preferences:
            self.preferences[teacher_name] = TeacherPreference(teacher_name)
        return self.preferences[teacher_name]
    
    def get_teacher_pattern(self, teacher_name: str) -> TeachingPattern:
        """教師のパターンデータを取得"""
        if teacher_name not in self.patterns:
            self.patterns[teacher_name] = TeachingPattern(teacher_name)
        return self.patterns[teacher_name]
    
    def calculate_placement_score(
        self,
        teacher_name: str,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        context: Optional[Dict] = None
    ) -> float:
        """特定の配置の好ましさをスコア化（0.0～1.0）"""
        preference = self.get_teacher_preference(teacher_name)
        pattern = self.get_teacher_pattern(teacher_name)
        
        score = 0.5  # 基本スコア
        
        # 時間帯の好み
        if time_slot.period <= 3:  # 午前
            score += (preference.morning_preference - 0.5) * 0.2
        else:  # 午後
            score += (preference.afternoon_preference - 0.5) * 0.2
        
        # 1限目・6限目の好み
        if time_slot.period == 1:
            score += (preference.first_period_preference - 0.5) * 0.15
        elif time_slot.period == 6:
            score += (preference.last_period_preference - 0.5) * 0.15
        
        # 曜日の好み
        day_pref = preference.day_preferences.get(time_slot.day, 0.5)
        score += (day_pref - 0.5) * 0.15
        
        # クラスとの相性
        class_key = f"{class_ref.grade}-{class_ref.class_number}"
        class_affinity = preference.class_affinities.get(class_key, 0.5)
        score += (class_affinity - 0.5) * 0.1
        
        # コンテキストを考慮
        if context:
            # 連続授業の考慮
            if context.get('is_consecutive', False):
                if preference.consecutive_preference > 0.5:
                    score += 0.1
                else:
                    score -= 0.1
            
            # 1日の授業数を考慮
            daily_count = context.get('daily_count', 0)
            if daily_count > preference.daily_max_preferred:
                score -= 0.1 * (daily_count - preference.daily_max_preferred)
        
        # スコアを0.0～1.0に正規化
        return max(0.0, min(1.0, score))
    
    def _collect_teacher_schedules(
        self,
        schedule: Schedule,
        school: School
    ) -> Dict[str, List[Tuple[TimeSlot, Assignment]]]:
        """教師ごとのスケジュールを収集"""
        teacher_schedules = defaultdict(list)
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.teacher:
                teacher_schedules[assignment.teacher.name].append((time_slot, assignment))
        
        # 時間順にソート
        for teacher_name in teacher_schedules:
            teacher_schedules[teacher_name].sort(
                key=lambda x: (
                    ["月", "火", "水", "木", "金"].index(x[0].day),
                    x[0].period
                )
            )
        
        return teacher_schedules
    
    def _update_teacher_pattern(
        self,
        teacher_name: str,
        assignments: List[Tuple[TimeSlot, Assignment]]
    ) -> TeachingPattern:
        """教師のパターンを更新"""
        pattern = self.get_teacher_pattern(teacher_name)
        
        # 時間帯別の頻度を更新
        for time_slot, assignment in assignments:
            key = (time_slot.day, time_slot.period)
            pattern.time_slot_frequency[key] = pattern.time_slot_frequency.get(key, 0) + 1
            
            # クラス別の頻度
            class_key = f"{assignment.class_ref.grade}-{assignment.class_ref.class_number}"
            pattern.class_frequency[class_key] = pattern.class_frequency.get(class_key, 0) + 1
            
            # 科目別の時間帯
            subject_name = assignment.subject.name
            if subject_name not in pattern.subject_time_preferences:
                pattern.subject_time_preferences[subject_name] = {}
            pattern.subject_time_preferences[subject_name][key] = \
                pattern.subject_time_preferences[subject_name].get(key, 0) + 1
        
        # 連続授業のパターンを分析
        consecutive_count = 0
        prev_slot = None
        
        for time_slot, _ in assignments:
            if prev_slot and prev_slot.day == time_slot.day and prev_slot.period + 1 == time_slot.period:
                consecutive_count += 1
            else:
                if consecutive_count > 0:
                    pattern.consecutive_patterns.append(consecutive_count + 1)
                consecutive_count = 0
            prev_slot = time_slot
        
        if consecutive_count > 0:
            pattern.consecutive_patterns.append(consecutive_count + 1)
        
        return pattern
    
    def _estimate_teacher_preference(
        self,
        teacher_name: str,
        pattern: TeachingPattern
    ) -> TeacherPreference:
        """パターンから教師の好みを推定"""
        preference = self.get_teacher_preference(teacher_name)
        
        # 観測数を増やす
        preference.total_observations += 1
        
        # 時間帯の好みを更新（指数移動平均）
        alpha = 0.1  # 学習率
        
        morning_count = sum(
            count for (day, period), count in pattern.time_slot_frequency.items()
            if period <= 3
        )
        afternoon_count = sum(
            count for (day, period), count in pattern.time_slot_frequency.items()
            if period > 3
        )
        total_count = morning_count + afternoon_count
        
        if total_count > 0:
            morning_ratio = morning_count / total_count
            preference.morning_preference = (1 - alpha) * preference.morning_preference + alpha * morning_ratio
            preference.afternoon_preference = 1 - preference.morning_preference
        
        # 1限目・6限目の好み
        first_count = sum(
            count for (day, period), count in pattern.time_slot_frequency.items()
            if period == 1
        )
        last_count = sum(
            count for (day, period), count in pattern.time_slot_frequency.items()
            if period == 6
        )
        
        if total_count > 0:
            preference.first_period_preference = (1 - alpha) * preference.first_period_preference + \
                                               alpha * (first_count / total_count * 5)  # 5倍して強調
            preference.last_period_preference = (1 - alpha) * preference.last_period_preference + \
                                              alpha * (last_count / total_count * 5)
        
        # 曜日別の好み
        for day in ["月", "火", "水", "木", "金"]:
            day_count = sum(
                count for (d, period), count in pattern.time_slot_frequency.items()
                if d == day
            )
            if total_count > 0:
                day_ratio = day_count / total_count * 5  # 5日で正規化
                preference.day_preferences[day] = (1 - alpha) * preference.day_preferences[day] + \
                                                alpha * day_ratio
        
        # 連続授業の好み
        if pattern.consecutive_patterns:
            avg_consecutive = sum(pattern.consecutive_patterns) / len(pattern.consecutive_patterns)
            if avg_consecutive > 2:
                preference.consecutive_preference = min(1.0, preference.consecutive_preference + alpha * 0.1)
            else:
                preference.consecutive_preference = max(0.0, preference.consecutive_preference - alpha * 0.1)
            preference.max_consecutive_preferred = int(avg_consecutive + 0.5)
        
        # 更新日時
        preference.last_updated = datetime.now()
        
        return preference
    
    def _calculate_satisfaction(
        self,
        assignments: List[Tuple[TimeSlot, Assignment]],
        preference: TeacherPreference
    ) -> float:
        """教師の満足度を計算（0.0～1.0）"""
        if not assignments:
            return 0.5
        
        satisfaction_scores = []
        daily_counts = defaultdict(int)
        
        # 各授業の満足度を計算
        for i, (time_slot, assignment) in enumerate(assignments):
            daily_counts[time_slot.day] += 1
            
            # コンテキストを準備
            context = {
                'daily_count': daily_counts[time_slot.day],
                'is_consecutive': False
            }
            
            # 連続授業かチェック
            if i > 0:
                prev_slot, _ = assignments[i-1]
                if prev_slot.day == time_slot.day and prev_slot.period + 1 == time_slot.period:
                    context['is_consecutive'] = True
            
            # 配置スコアを計算
            score = self.calculate_placement_score(
                assignment.teacher.name,
                time_slot,
                assignment.class_ref,
                context
            )
            satisfaction_scores.append(score)
        
        # ワークロードの満足度
        weekly_count = len(assignments)
        workload_satisfaction = 1.0
        if weekly_count > preference.weekly_max_preferred:
            excess = weekly_count - preference.weekly_max_preferred
            workload_satisfaction = max(0.0, 1.0 - excess * 0.05)
        
        # 全体の満足度
        if satisfaction_scores:
            placement_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores)
            total_satisfaction = placement_satisfaction * 0.7 + workload_satisfaction * 0.3
        else:
            total_satisfaction = workload_satisfaction
        
        return total_satisfaction
    
    def _analyze_collaboration(self, schedule: Schedule, school: School) -> Dict[str, Dict[str, int]]:
        """教師間の協力関係を分析"""
        collaboration_matrix = defaultdict(lambda: defaultdict(int))
        
        # 時間帯ごとに教師を収集
        time_slot_teachers = defaultdict(set)
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.teacher:
                time_slot_teachers[time_slot].add(assignment.teacher.name)
        
        # 同じ時間帯に教える教師のペアをカウント
        for teachers in time_slot_teachers.values():
            teacher_list = list(teachers)
            for i in range(len(teacher_list)):
                for j in range(i + 1, len(teacher_list)):
                    teacher1, teacher2 = sorted([teacher_list[i], teacher_list[j]])
                    collaboration_matrix[teacher1][teacher2] += 1
        
        return dict(collaboration_matrix)
    
    def _analyze_time_preferences(self) -> Dict[str, Dict[str, float]]:
        """時間帯別の傾向を分析"""
        time_preferences = {
            'morning_lovers': [],  # 午前派
            'afternoon_lovers': [],  # 午後派
            'early_birds': [],  # 早朝派（1限目好き）
            'night_owls': [],  # 遅番派（6限目好き）
            'balanced': []  # バランス型
        }
        
        for teacher_name, preference in self.preferences.items():
            # 午前・午後の好み
            if preference.morning_preference > 0.65:
                time_preferences['morning_lovers'].append({
                    'name': teacher_name,
                    'score': preference.morning_preference
                })
            elif preference.afternoon_preference > 0.65:
                time_preferences['afternoon_lovers'].append({
                    'name': teacher_name,
                    'score': preference.afternoon_preference
                })
            
            # 1限目・6限目の好み
            if preference.first_period_preference > 0.6:
                time_preferences['early_birds'].append({
                    'name': teacher_name,
                    'score': preference.first_period_preference
                })
            if preference.last_period_preference > 0.6:
                time_preferences['night_owls'].append({
                    'name': teacher_name,
                    'score': preference.last_period_preference
                })
            
            # バランス型
            if (0.4 <= preference.morning_preference <= 0.6 and
                0.4 <= preference.first_period_preference <= 0.6 and
                0.4 <= preference.last_period_preference <= 0.6):
                time_preferences['balanced'].append({
                    'name': teacher_name,
                    'score': 0.5
                })
        
        # スコアでソート
        for category in time_preferences:
            time_preferences[category].sort(key=lambda x: x['score'], reverse=True)
        
        return time_preferences
    
    def _analyze_workload_balance(
        self,
        teacher_schedules: Dict[str, List[Tuple[TimeSlot, Assignment]]]
    ) -> Dict[str, Any]:
        """ワークロードバランスを分析"""
        workloads = {
            teacher: len(assignments)
            for teacher, assignments in teacher_schedules.items()
        }
        
        if not workloads:
            return {}
        
        avg_workload = sum(workloads.values()) / len(workloads)
        max_workload = max(workloads.values())
        min_workload = min(workloads.values())
        
        # 標準偏差を計算
        variance = sum((w - avg_workload) ** 2 for w in workloads.values()) / len(workloads)
        std_dev = variance ** 0.5
        
        # バランススコア（低いほど良い）
        balance_score = std_dev / avg_workload if avg_workload > 0 else 0
        
        return {
            'average': avg_workload,
            'max': max_workload,
            'min': min_workload,
            'std_dev': std_dev,
            'balance_score': balance_score,
            'overloaded': [t for t, w in workloads.items() if w > avg_workload + std_dev],
            'underloaded': [t for t, w in workloads.items() if w < avg_workload - std_dev],
            'distribution': workloads
        }
    
    def _generate_recommendations(self, analysis_result: Dict) -> List[str]:
        """分析結果から改善提案を生成"""
        recommendations = []
        
        # ワークロードバランスの改善提案
        workload = analysis_result.get('workload_balance', {})
        if workload.get('balance_score', 0) > 0.2:
            recommendations.append(
                f"ワークロードのバランスが悪いです（スコア: {workload['balance_score']:.2f}）。"
                f"過負荷の教師: {', '.join(workload.get('overloaded', [])[:3])}"
            )
        
        # 満足度の低い教師への対応
        low_satisfaction_teachers = []
        for teacher, data in analysis_result.get('teacher_patterns', {}).items():
            if data.get('satisfaction_score', 0.5) < 0.4:
                low_satisfaction_teachers.append(teacher)
        
        if low_satisfaction_teachers:
            recommendations.append(
                f"満足度の低い教師がいます: {', '.join(low_satisfaction_teachers[:3])}。"
                "配置パターンの見直しを検討してください。"
            )
        
        # 時間帯の偏りへの対応
        time_prefs = analysis_result.get('time_preferences', {})
        morning_lovers = len(time_prefs.get('morning_lovers', []))
        afternoon_lovers = len(time_prefs.get('afternoon_lovers', []))
        
        if abs(morning_lovers - afternoon_lovers) > 5:
            if morning_lovers > afternoon_lovers:
                recommendations.append(
                    "午前派の教師が多いため、午前中の授業が混雑する可能性があります。"
                )
            else:
                recommendations.append(
                    "午後派の教師が多いため、午後の授業が混雑する可能性があります。"
                )
        
        # 協力関係の活用提案
        collaboration = analysis_result.get('collaboration_matrix', {})
        strong_pairs = []
        for teacher1, partners in collaboration.items():
            for teacher2, count in partners.items():
                if count > 10:  # 頻繁に同じ時間帯
                    strong_pairs.append((teacher1, teacher2, count))
        
        if strong_pairs:
            recommendations.append(
                "以下の教師ペアは頻繁に同じ時間帯に授業があります。"
                "チームティーチングの機会として活用できるかもしれません: " +
                ", ".join([f"{t1}-{t2}" for t1, t2, _ in strong_pairs[:3]])
            )
        
        return recommendations
    
    def _preference_to_dict(self, preference: TeacherPreference) -> Dict:
        """TeacherPreferenceを辞書に変換"""
        return {
            'morning_preference': preference.morning_preference,
            'afternoon_preference': preference.afternoon_preference,
            'first_period_preference': preference.first_period_preference,
            'last_period_preference': preference.last_period_preference,
            'day_preferences': preference.day_preferences,
            'consecutive_preference': preference.consecutive_preference,
            'max_consecutive_preferred': preference.max_consecutive_preferred,
            'daily_max_preferred': preference.daily_max_preferred,
            'weekly_max_preferred': preference.weekly_max_preferred,
            'class_affinities': preference.class_affinities
        }
    
    def _pattern_to_dict(self, pattern: TeachingPattern) -> Dict:
        """TeachingPatternを辞書に変換"""
        return {
            'time_slot_frequency': {
                f"{day}_{period}": count
                for (day, period), count in pattern.time_slot_frequency.items()
            },
            'consecutive_average': sum(pattern.consecutive_patterns) / len(pattern.consecutive_patterns) if pattern.consecutive_patterns else 0,
            'most_frequent_classes': sorted(
                pattern.class_frequency.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'violation_rate': pattern.violation_rate,
            'efficiency_score': pattern.efficiency_score
        }
    
    def _save_data(self):
        """データを保存"""
        # 好みデータの保存
        preferences_file = os.path.join(self.data_dir, "teacher_preferences.json")
        preferences_data = {
            name: self._preference_to_dict(pref)
            for name, pref in self.preferences.items()
        }
        
        with open(preferences_file, 'w', encoding='utf-8') as f:
            json.dump(preferences_data, f, ensure_ascii=False, indent=2)
        
        # パターンデータの保存
        patterns_file = os.path.join(self.data_dir, "teacher_patterns.json")
        patterns_data = {
            name: self._pattern_to_dict(pattern)
            for name, pattern in self.patterns.items()
        }
        
        with open(patterns_file, 'w', encoding='utf-8') as f:
            json.dump(patterns_data, f, ensure_ascii=False, indent=2)
        
        # 分析履歴の保存（最新10件）
        history_file = os.path.join(self.data_dir, "analysis_history.json")
        recent_history = self.analysis_history[-10:] if len(self.analysis_history) > 10 else self.analysis_history
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(recent_history, f, ensure_ascii=False, indent=2)
    
    def _load_data(self):
        """データを読み込み"""
        # 好みデータの読み込み
        preferences_file = os.path.join(self.data_dir, "teacher_preferences.json")
        if os.path.exists(preferences_file):
            with open(preferences_file, 'r', encoding='utf-8') as f:
                preferences_data = json.load(f)
                for name, data in preferences_data.items():
                    pref = TeacherPreference(name)
                    for key, value in data.items():
                        if hasattr(pref, key):
                            setattr(pref, key, value)
                    self.preferences[name] = pref
        
        # パターンデータの読み込み
        patterns_file = os.path.join(self.data_dir, "teacher_patterns.json")
        if os.path.exists(patterns_file):
            with open(patterns_file, 'r', encoding='utf-8') as f:
                patterns_data = json.load(f)
                for name, data in patterns_data.items():
                    pattern = TeachingPattern(name)
                    # time_slot_frequencyの復元
                    if 'time_slot_frequency' in data:
                        for key, count in data['time_slot_frequency'].items():
                            day, period = key.split('_')
                            pattern.time_slot_frequency[(day, int(period))] = count
                    self.patterns[name] = pattern
        
        # 分析履歴の読み込み
        history_file = os.path.join(self.data_dir, "analysis_history.json")
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                self.analysis_history = json.load(f)