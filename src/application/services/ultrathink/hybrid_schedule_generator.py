"""
フェーズ4: ハイブリッドアプローチ（Ultrathink最終版）

全てのフェーズを統合した究極の時間割生成システム。
教師中心生成とインテリジェント修正を組み合わせ、
学習機能により実行のたびに賢くなります。

主な特徴：
1. 教師中心の初期生成（フェーズ2）
2. インテリジェント修正（フェーズ3）
3. 局所最適脱出メカニズム
4. 継続的学習と改善
"""
import logging
import random
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime

from .teacher_centric_generator import TeacherCentricGenerator
from .optimizer.intelligent_schedule_optimizer import IntelligentScheduleOptimizer
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot
from ....domain.value_objects.time_slot import ClassReference
from ....domain.services.validators.constraint_validator import ConstraintValidator
from ....domain.services.synchronizers.exchange_class_synchronizer import ExchangeClassSynchronizer
from ....domain.services.synchronizers.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer


@dataclass
class GenerationResult:
    """生成結果"""
    schedule: Schedule
    statistics: Dict
    learning_data: Dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class LearningData:
    """学習データ"""
    successful_patterns: List[Dict] = field(default_factory=list)
    failure_patterns: List[Dict] = field(default_factory=list)
    teacher_preferences: Dict[str, Dict] = field(default_factory=dict)
    constraint_difficulty: Dict[str, float] = field(default_factory=dict)
    
    def add_success(self, pattern: Dict):
        self.successful_patterns.append(pattern)
        # 最新の1000パターンのみ保持
        if len(self.successful_patterns) > 1000:
            self.successful_patterns = self.successful_patterns[-1000:]
    
    def add_failure(self, pattern: Dict):
        self.failure_patterns.append(pattern)
        if len(self.failure_patterns) > 500:
            self.failure_patterns = self.failure_patterns[-500:]
    
    def update_teacher_preference(self, teacher: str, day: str, period: int, score: float):
        if teacher not in self.teacher_preferences:
            self.teacher_preferences[teacher] = {}
        key = f"{day}_{period}"
        current = self.teacher_preferences[teacher].get(key, 0.5)
        # 指数移動平均で更新
        self.teacher_preferences[teacher][key] = 0.9 * current + 0.1 * score
    
    def get_teacher_preference(self, teacher: str, day: str, period: int) -> float:
        if teacher not in self.teacher_preferences:
            return 0.5
        key = f"{day}_{period}"
        return self.teacher_preferences[teacher].get(key, 0.5)


class HybridScheduleGenerator:
    """ハイブリッド時間割生成器"""
    
    def __init__(
        self,
        learning_file: Optional[str] = None,
        enable_logging: bool = True
    ):
        self.logger = logging.getLogger(__name__)
        if not enable_logging:
            self.logger.setLevel(logging.WARNING)
        
        # サブコンポーネントの初期化
        self.teacher_generator = TeacherCentricGenerator(enable_logging=enable_logging)
        self.optimizer = IntelligentScheduleOptimizer()
        self.constraint_validator = ConstraintValidator()
        
        # 学習データ
        self.learning_file = learning_file or "learning_data.json"
        self.learning_data = self._load_learning_data()
        
        # 設定パラメータ
        self.max_generation_attempts = 3
        self.max_optimization_iterations = 30
        self.escape_threshold = 0.8  # 局所最適脱出の閾値
        self.random_restart_probability = 0.2
        
        # テスト期間（ハードコード）
        self.test_periods = {
            ("月", 1), ("月", 2), ("月", 3),
            ("火", 1), ("火", 2), ("火", 3),
            ("水", 1), ("水", 2)
        }
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        target_violations: int = 0,
        time_limit: int = 300  # 秒
    ) -> GenerationResult:
        """ハイブリッドアプローチで時間割を生成
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            target_violations: 目標違反数（デフォルト0）
            time_limit: 制限時間（秒）
            
        Returns:
            生成結果
        """
        
        self.logger.info("=== ハイブリッド時間割生成開始 ===")
        start_time = datetime.now()
        
        best_schedule = None
        best_violations = float('inf')
        generation_stats = {
            'phase2_attempts': 0,
            'phase3_iterations': 0,
            'escapes': 0,
            'restarts': 0,
            'final_violations': 0,
            'teacher_conflicts': 0
        }
        
        for attempt in range(self.max_generation_attempts):
            self.logger.info(f"\n【第{attempt + 1}回生成試行】")
            
            # 1. フェーズ2: 教師中心の初期生成
            self.logger.info("フェーズ2: 教師中心生成を実行...")
            
            # 学習データを反映したシードを設定
            if attempt > 0 and random.random() < self.random_restart_probability:
                seed = None  # ランダムリスタート
                generation_stats['restarts'] += 1
            else:
                seed = self._generate_smart_seed(school)
            
            schedule = self.teacher_generator.generate(
                school, 
                initial_schedule=initial_schedule,
                seed=seed
            )
            generation_stats['phase2_attempts'] += 1
            
            # 初期状態の評価
            initial_violations = self._count_violations(schedule, school)
            self.logger.info(f"初期違反数: {initial_violations}")
            
            # 2. フェーズ3: インテリジェント修正
            self.logger.info("フェーズ3: インテリジェント最適化を実行...")
            
            optimization_stats = self.optimizer.optimize(
                schedule, 
                school, 
                max_iterations=self.max_optimization_iterations
            )
            generation_stats['phase3_iterations'] += optimization_stats['chains_executed']
            
            # 最適化後の評価
            current_violations = optimization_stats['final_violations']
            teacher_conflicts = self._count_teacher_conflicts(schedule, school)
            
            self.logger.info(f"最適化後: 全違反={current_violations}, 教師重複={teacher_conflicts}")
            
            # ベストスケジュールの更新
            if current_violations < best_violations:
                best_schedule = schedule
                best_violations = current_violations
                generation_stats['teacher_conflicts'] = teacher_conflicts
            
            # 目標達成チェック
            if current_violations <= target_violations:
                self.logger.info(f"✓ 目標達成！違反数: {current_violations}")
                break
            
            # 3. 局所最適脱出
            if attempt < self.max_generation_attempts - 1:
                improvement_rate = (initial_violations - current_violations) / initial_violations if initial_violations > 0 else 0
                
                if improvement_rate < self.escape_threshold:
                    self.logger.info("局所最適に陥った可能性 - 脱出戦略を実行")
                    self._escape_local_optimum(schedule, school)
                    generation_stats['escapes'] += 1
            
            # 時間制限チェック
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > time_limit:
                self.logger.warning(f"時間制限に到達: {elapsed:.1f}秒")
                break
        
        # 4. 最終処理
        generation_stats['final_violations'] = best_violations
        generation_stats['elapsed_time'] = (datetime.now() - start_time).total_seconds()
        
        # 学習データの更新
        self._update_learning_data(best_schedule, school, generation_stats)
        self._save_learning_data()
        
        # 結果の生成
        result = GenerationResult(
            schedule=best_schedule,
            statistics=generation_stats,
            learning_data={
                'patterns_learned': len(self.learning_data.successful_patterns),
                'teacher_preferences': len(self.learning_data.teacher_preferences)
            }
        )
        
        self._print_final_summary(result)
        
        return result
    
    def _load_learning_data(self) -> LearningData:
        """学習データを読み込む"""
        try:
            if Path(self.learning_file).exists():
                with open(self.learning_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    learning = LearningData()
                    learning.successful_patterns = data.get('successful_patterns', [])
                    learning.failure_patterns = data.get('failure_patterns', [])
                    learning.teacher_preferences = data.get('teacher_preferences', {})
                    learning.constraint_difficulty = data.get('constraint_difficulty', {})
                    return learning
        except Exception as e:
            self.logger.warning(f"学習データ読み込みエラー: {e}")
        
        return LearningData()
    
    def _save_learning_data(self):
        """学習データを保存"""
        try:
            data = {
                'successful_patterns': self.learning_data.successful_patterns,
                'failure_patterns': self.learning_data.failure_patterns,
                'teacher_preferences': self.learning_data.teacher_preferences,
                'constraint_difficulty': self.learning_data.constraint_difficulty,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.learning_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"学習データ保存エラー: {e}")
    
    def _generate_smart_seed(self, school: School) -> int:
        """学習データに基づくスマートなシード生成"""
        # 成功パターンの数と現在時刻を組み合わせる
        base_seed = len(self.learning_data.successful_patterns)
        time_component = int(datetime.now().timestamp()) % 10000
        return base_seed * 10000 + time_component
    
    def _count_violations(self, schedule: Schedule, school: School) -> int:
        """全違反数をカウント"""
        violations = self.constraint_validator.validate_all_constraints(schedule, school)
        return len(violations)
    
    def _count_teacher_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師重複をカウント（テスト期間を除く）"""
        from collections import defaultdict
        
        fixed_teachers = {
            "欠", "欠課先生", "YT担当", "YT担当先生", 
            "道担当", "道担当先生", "学担当", "学担当先生", 
            "総担当", "総担当先生", "学総担当", "学総担当先生", 
            "行担当", "行担当先生", "技家担当", "技家担当先生"
        }
        
        grade5_refs = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
        
        conflicts = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 教師ごとにクラスを収集
                teacher_assignments = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        
                        # 固定科目の教師は除外
                        if teacher_name in fixed_teachers:
                            continue
                        
                        teacher_assignments[teacher_name].append(class_ref)
                
                # 重複をチェック
                for teacher_name, classes in teacher_assignments.items():
                    if len(classes) > 1:
                        # 5組のみの場合は正常
                        all_grade5 = all(c in grade5_refs for c in classes)
                        if not all_grade5:
                            conflicts += 1
        
        return conflicts
    
    def _escape_local_optimum(self, schedule: Schedule, school: School):
        """局所最適から脱出"""
        # 複数の戦略をランダムに選択
        strategies = [
            self._random_perturbation,
            self._guided_destruction,
            self._constraint_relaxation
        ]
        
        strategy = random.choice(strategies)
        strategy(schedule, school)
    
    def _random_perturbation(self, schedule: Schedule, school: School):
        """ランダムな摂動を加える"""
        self.logger.debug("戦略: ランダム摂動")
        
        # ランダムに10個の授業を交換
        days = ["月", "火", "水", "木", "金"]
        for _ in range(10):
            day1 = random.choice(days)
            day2 = random.choice(days)
            period1 = random.randint(1, 6)
            period2 = random.randint(1, 6)
            
            slot1 = TimeSlot(day1, period1)
            slot2 = TimeSlot(day2, period2)
            
            # ランダムなクラスを選択
            all_classes = list(school.get_all_classes())
            class_ref = random.choice(all_classes)
            
            # ロックチェック
            if schedule.is_locked(slot1, class_ref) or schedule.is_locked(slot2, class_ref):
                continue
            
            # 交換実行
            assignment1 = schedule.get_assignment(slot1, class_ref)
            assignment2 = schedule.get_assignment(slot2, class_ref)
            
            if assignment1 and assignment2:
                try:
                    schedule.remove_assignment(slot1, class_ref)
                    schedule.remove_assignment(slot2, class_ref)
                    schedule.assign(slot1, assignment2)
                    schedule.assign(slot2, assignment1)
                except Exception:
                    pass
    
    def _guided_destruction(self, schedule: Schedule, school: School):
        """問題のある部分を選択的に破壊"""
        self.logger.debug("戦略: ガイド付き破壊")
        
        # 教師重複が多い時間帯を特定
        problem_slots = self._identify_problem_slots(schedule, school)
        
        # 問題のあるスロットの授業を削除
        for slot, class_ref in problem_slots[:5]:  # 最大5個
            if not schedule.is_locked(slot, class_ref):
                try:
                    schedule.remove_assignment(slot, class_ref)
                except Exception:
                    pass
    
    def _constraint_relaxation(self, schedule: Schedule, school: School):
        """制約を一時的に緩和"""
        self.logger.debug("戦略: 制約緩和")
        # この実装では、オプティマイザーの温度を上げることで実現
        self.optimizer.temperature = 1.0  # 温度をリセット
    
    def _identify_problem_slots(
        self, 
        schedule: Schedule, 
        school: School
    ) -> List[Tuple[TimeSlot, ClassReference]]:
        """問題のあるスロットを特定"""
        problem_slots = []
        
        violations = self.constraint_validator.validate_all_constraints(schedule, school)
        
        for violation in violations:
            if 'time_slot' in violation and 'class_ref' in violation:
                problem_slots.append((violation['time_slot'], violation['class_ref']))
        
        return problem_slots
    
    def _update_learning_data(
        self, 
        schedule: Schedule, 
        school: School,
        stats: Dict
    ):
        """学習データを更新"""
        # 成功パターンの記録
        if stats['final_violations'] == 0:
            pattern = {
                'teacher_conflicts': stats['teacher_conflicts'],
                'phase2_attempts': stats['phase2_attempts'],
                'phase3_iterations': stats['phase3_iterations'],
                'escapes': stats['escapes'],
                'timestamp': datetime.now().isoformat()
            }
            self.learning_data.add_success(pattern)
        
        # 教師の好みを更新
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        # 違反がない場合は高スコア
                        score = 1.0 if stats['final_violations'] == 0 else 0.5
                        self.learning_data.update_teacher_preference(
                            assignment.teacher.name, day, period, score
                        )
    
    def _print_final_summary(self, result: GenerationResult):
        """最終サマリーを出力"""
        self.logger.info("\n=== ハイブリッド生成完了 ===")
        self.logger.info(f"最終違反数: {result.statistics['final_violations']}")
        self.logger.info(f"教師重複: {result.statistics['teacher_conflicts']}")
        self.logger.info(f"実行時間: {result.statistics['elapsed_time']:.1f}秒")
        self.logger.info(f"フェーズ2試行: {result.statistics['phase2_attempts']}回")
        self.logger.info(f"フェーズ3イテレーション: {result.statistics['phase3_iterations']}回")
        self.logger.info(f"脱出戦略実行: {result.statistics['escapes']}回")
        self.logger.info(f"学習パターン数: {result.learning_data['patterns_learned']}")