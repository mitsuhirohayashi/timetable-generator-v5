"""
教師満足度最適化コンポーネント

教師の好みや働きやすさを考慮して、時間割の質を向上させます。
ハイブリッド生成器V8の機能を抽出・改良したものです。
"""
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict
import json
from pathlib import Path

from ....entities.schedule import Schedule
from ....entities.school import School, Teacher
from ....value_objects.time_slot import TimeSlot
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class TeacherPreference:
    """教師の好み設定"""
    teacher_name: str
    
    # 時間帯の好み（-1.0〜1.0: 負は避けたい、正は好ましい）
    time_preferences: Dict[Tuple[str, int], float] = field(default_factory=dict)
    
    # 連続授業の好み
    max_consecutive_classes: int = 3
    prefer_consecutive: bool = True
    
    # 1日の最大授業数
    max_classes_per_day: int = 5
    
    # 特定クラスとの相性
    class_affinity: Dict[Tuple[int, int], float] = field(default_factory=dict)
    
    # 空き時間の好み
    prefer_morning_free: bool = False
    prefer_afternoon_free: bool = False


@dataclass
class TeacherSatisfactionScore:
    """教師満足度スコア"""
    teacher_name: str
    total_score: float = 0.0
    
    # 詳細スコア
    time_preference_score: float = 0.0
    consecutive_class_score: float = 0.0
    workload_balance_score: float = 0.0
    class_affinity_score: float = 0.0
    free_time_score: float = 0.0
    
    # 違反項目
    violations: List[str] = field(default_factory=list)
    
    def calculate_total(self):
        """総合スコアを計算"""
        self.total_score = (
            self.time_preference_score * 0.3 +
            self.consecutive_class_score * 0.2 +
            self.workload_balance_score * 0.2 +
            self.class_affinity_score * 0.2 +
            self.free_time_score * 0.1
        )


class TeacherSatisfactionOptimizer(LoggingMixin):
    """教師満足度最適化"""
    
    def __init__(
        self,
        preferences_file: Optional[str] = None,
        learning_enabled: bool = True
    ):
        super().__init__()
        self.preferences: Dict[str, TeacherPreference] = {}
        self.satisfaction_history: List[Dict[str, TeacherSatisfactionScore]] = []
        self.learning_enabled = learning_enabled
        
        # 好み設定をロード
        if preferences_file and Path(preferences_file).exists():
            self.load_preferences(preferences_file)
        else:
            self.logger.info("教師の好み設定ファイルが見つかりません。デフォルト設定を使用します。")
    
    def load_preferences(self, filepath: str):
        """教師の好み設定をロード"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for teacher_data in data.get('teachers', []):
                pref = TeacherPreference(
                    teacher_name=teacher_data['name'],
                    max_consecutive_classes=teacher_data.get('max_consecutive', 3),
                    prefer_consecutive=teacher_data.get('prefer_consecutive', True),
                    max_classes_per_day=teacher_data.get('max_per_day', 5)
                )
                
                # 時間帯の好み
                for time_pref in teacher_data.get('time_preferences', []):
                    day = time_pref['day']
                    period = time_pref['period']
                    score = time_pref['score']
                    pref.time_preferences[(day, period)] = score
                
                # クラスとの相性
                for class_pref in teacher_data.get('class_preferences', []):
                    grade = class_pref['grade']
                    class_num = class_pref['class']
                    score = class_pref['score']
                    pref.class_affinity[(grade, class_num)] = score
                
                self.preferences[pref.teacher_name] = pref
                
            self.logger.info(f"{len(self.preferences)}人の教師の好み設定をロードしました。")
            
        except Exception as e:
            self.logger.error(f"好み設定のロードに失敗: {e}")
    
    def get_preference(self, teacher: Teacher) -> TeacherPreference:
        """教師の好み設定を取得（なければデフォルト生成）"""
        if teacher.name not in self.preferences:
            # デフォルト設定を生成
            self.preferences[teacher.name] = self._generate_default_preference(teacher)
        
        return self.preferences[teacher.name]
    
    def _generate_default_preference(self, teacher: Teacher) -> TeacherPreference:
        """デフォルトの好み設定を生成"""
        pref = TeacherPreference(teacher_name=teacher.name)
        
        # 一般的な傾向を設定
        # 1限目と6限目は避けたい傾向
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            pref.time_preferences[(day, 1)] = -0.3  # 朝一は少し避けたい
            pref.time_preferences[(day, 6)] = -0.5  # 最終時限は避けたい
        
        # 金曜の午後は特に避けたい
        pref.time_preferences[("金", 5)] = -0.7
        pref.time_preferences[("金", 6)] = -0.9
        
        return pref
    
    def evaluate_schedule(
        self,
        schedule: Schedule,
        school: School
    ) -> Dict[str, TeacherSatisfactionScore]:
        """スケジュール全体の教師満足度を評価"""
        scores = {}
        
        for teacher in school.get_all_teachers():
            score = self.evaluate_teacher_satisfaction(teacher, schedule, school)
            scores[teacher.name] = score
        
        # 学習用に履歴を保存
        if self.learning_enabled:
            self.satisfaction_history.append(scores)
        
        return scores
    
    def evaluate_teacher_satisfaction(
        self,
        teacher: Teacher,
        schedule: Schedule,
        school: School
    ) -> TeacherSatisfactionScore:
        """個別教師の満足度を評価"""
        score = TeacherSatisfactionScore(teacher_name=teacher.name)
        preference = self.get_preference(teacher)
        
        # 教師の全授業を取得
        teacher_assignments = self._get_teacher_assignments(teacher, schedule)
        
        # 各要素のスコアを計算
        score.time_preference_score = self._calculate_time_preference_score(
            teacher_assignments, preference
        )
        
        score.consecutive_class_score = self._calculate_consecutive_score(
            teacher_assignments, preference
        )
        
        score.workload_balance_score = self._calculate_workload_balance_score(
            teacher_assignments, preference
        )
        
        score.class_affinity_score = self._calculate_class_affinity_score(
            teacher_assignments, preference
        )
        
        score.free_time_score = self._calculate_free_time_score(
            teacher_assignments, preference
        )
        
        # 総合スコアを計算
        score.calculate_total()
        
        return score
    
    def _get_teacher_assignments(
        self,
        teacher: Teacher,
        schedule: Schedule
    ) -> List[Tuple[TimeSlot, Assignment]]:
        """教師の全授業を取得"""
        assignments = []
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.teacher and assignment.teacher.name == teacher.name:
                assignments.append((time_slot, assignment))
        
        return sorted(assignments, key=lambda x: (x[0].day, x[0].period))
    
    def _calculate_time_preference_score(
        self,
        assignments: List[Tuple[TimeSlot, Assignment]],
        preference: TeacherPreference
    ) -> float:
        """時間帯の好みスコアを計算"""
        if not assignments:
            return 1.0
        
        total_score = 0.0
        for time_slot, _ in assignments:
            key = (time_slot.day, time_slot.period)
            pref_score = preference.time_preferences.get(key, 0.0)
            # -1〜1を0〜1に正規化
            normalized_score = (pref_score + 1.0) / 2.0
            total_score += normalized_score
        
        return total_score / len(assignments)
    
    def _calculate_consecutive_score(
        self,
        assignments: List[Tuple[TimeSlot, Assignment]],
        preference: TeacherPreference
    ) -> float:
        """連続授業スコアを計算"""
        if not assignments:
            return 1.0
        
        score = 1.0
        violations = []
        
        # 日ごとにグループ化
        by_day = defaultdict(list)
        for time_slot, assignment in assignments:
            by_day[time_slot.day].append(time_slot.period)
        
        for day, periods in by_day.items():
            periods.sort()
            
            # 連続授業をカウント
            consecutive = 1
            for i in range(1, len(periods)):
                if periods[i] == periods[i-1] + 1:
                    consecutive += 1
                    if consecutive > preference.max_consecutive_classes:
                        violations.append(f"{day}曜日に{consecutive}連続授業")
                        score *= 0.8  # ペナルティ
                else:
                    consecutive = 1
            
            # 飛び飛びの授業もペナルティ
            if not preference.prefer_consecutive and len(periods) > 1:
                gaps = sum(1 for i in range(1, len(periods)) 
                          if periods[i] - periods[i-1] > 1)
                if gaps > 0:
                    score *= (0.9 ** gaps)
        
        return max(0.0, score)
    
    def _calculate_workload_balance_score(
        self,
        assignments: List[Tuple[TimeSlot, Assignment]],
        preference: TeacherPreference
    ) -> float:
        """負荷バランススコアを計算"""
        if not assignments:
            return 1.0
        
        # 日ごとの授業数
        by_day = defaultdict(int)
        for time_slot, _ in assignments:
            by_day[time_slot.day] += 1
        
        score = 1.0
        
        # 1日の最大授業数チェック
        for day, count in by_day.items():
            if count > preference.max_classes_per_day:
                score *= 0.7  # 大きなペナルティ
            elif count == preference.max_classes_per_day:
                score *= 0.9  # 小さなペナルティ
        
        # 日ごとのバランスチェック（標準偏差）
        if len(by_day) > 1:
            avg = sum(by_day.values()) / len(by_day)
            variance = sum((count - avg) ** 2 for count in by_day.values()) / len(by_day)
            std_dev = variance ** 0.5
            
            # 標準偏差が大きいほどペナルティ
            if std_dev > 1.5:
                score *= 0.8
            elif std_dev > 1.0:
                score *= 0.9
        
        return max(0.0, score)
    
    def _calculate_class_affinity_score(
        self,
        assignments: List[Tuple[TimeSlot, Assignment]],
        preference: TeacherPreference
    ) -> float:
        """クラスとの相性スコアを計算"""
        if not assignments or not preference.class_affinity:
            return 0.5  # 中立
        
        total_score = 0.0
        count = 0
        
        for _, assignment in assignments:
            class_key = (assignment.class_ref.grade, assignment.class_ref.class_number)
            if class_key in preference.class_affinity:
                # -1〜1を0〜1に正規化
                affinity = preference.class_affinity[class_key]
                normalized = (affinity + 1.0) / 2.0
                total_score += normalized
                count += 1
        
        if count == 0:
            return 0.5  # 相性データがない場合は中立
        
        return total_score / count
    
    def _calculate_free_time_score(
        self,
        assignments: List[Tuple[TimeSlot, Assignment]],
        preference: TeacherPreference
    ) -> float:
        """空き時間の好みスコアを計算"""
        if not assignments:
            return 1.0
        
        score = 1.0
        
        # 日ごとにグループ化
        by_day = defaultdict(list)
        for time_slot, _ in assignments:
            by_day[time_slot.day].append(time_slot.period)
        
        for day, periods in by_day.items():
            periods.sort()
            
            # 午前空きの好み
            if preference.prefer_morning_free:
                if 1 in periods or 2 in periods:
                    score *= 0.8
            
            # 午後空きの好み
            if preference.prefer_afternoon_free:
                if 5 in periods or 6 in periods:
                    score *= 0.8
        
        return max(0.0, score)
    
    def optimize_assignment(
        self,
        time_slot: TimeSlot,
        candidates: List[Tuple[Teacher, float]],
        schedule: Schedule,
        school: School
    ) -> Optional[Teacher]:
        """満足度を考慮して最適な教師を選択"""
        if not candidates:
            return None
        
        best_teacher = None
        best_score = -1.0
        
        for teacher, base_score in candidates:
            # 現在の満足度を計算
            current_score = self.evaluate_teacher_satisfaction(teacher, schedule, school)
            
            # この時間帯の好みを取得
            preference = self.get_preference(teacher)
            time_pref = preference.time_preferences.get(
                (time_slot.day, time_slot.period), 0.0
            )
            
            # 総合スコア = 基本スコア * 満足度 * 時間帯の好み
            combined_score = base_score * current_score.total_score * ((time_pref + 1.0) / 2.0)
            
            if combined_score > best_score:
                best_score = combined_score
                best_teacher = teacher
        
        return best_teacher
    
    def learn_from_feedback(
        self,
        feedback: Dict[str, float],
        schedule: Schedule
    ):
        """フィードバックから学習"""
        if not self.learning_enabled:
            return
        
        # フィードバックに基づいて好み設定を更新
        for teacher_name, satisfaction_level in feedback.items():
            if teacher_name not in self.preferences:
                continue
            
            preference = self.preferences[teacher_name]
            
            # 低満足度の場合、現在の割り当てから学習
            if satisfaction_level < 0.5:
                # この教師の授業を分析
                for time_slot, assignment in schedule.get_all_assignments():
                    if assignment.teacher and assignment.teacher.name == teacher_name:
                        # この時間帯の好みを下げる
                        key = (time_slot.day, time_slot.period)
                        current = preference.time_preferences.get(key, 0.0)
                        preference.time_preferences[key] = max(-1.0, current - 0.1)
        
        self.logger.info(f"{len(feedback)}人の教師からのフィードバックを学習しました。")
    
    def save_preferences(self, filepath: str):
        """学習した好み設定を保存"""
        data = {'teachers': []}
        
        for pref in self.preferences.values():
            teacher_data = {
                'name': pref.teacher_name,
                'max_consecutive': pref.max_consecutive_classes,
                'prefer_consecutive': pref.prefer_consecutive,
                'max_per_day': pref.max_classes_per_day,
                'time_preferences': [
                    {'day': day, 'period': period, 'score': score}
                    for (day, period), score in pref.time_preferences.items()
                ],
                'class_preferences': [
                    {'grade': grade, 'class': cls, 'score': score}
                    for (grade, cls), score in pref.class_affinity.items()
                ]
            }
            data['teachers'].append(teacher_data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"教師の好み設定を保存しました: {filepath}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        total_score = 0.0
        count = 0
        
        if self.satisfaction_history:
            latest = self.satisfaction_history[-1]
            for score in latest.values():
                total_score += score.total_score
                count += 1
        
        return {
            'preferences_loaded': len(self.preferences),
            'average_satisfaction': total_score / count if count > 0 else 0.0,
            'history_length': len(self.satisfaction_history),
            'learning_enabled': self.learning_enabled
        }