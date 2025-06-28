"""
自動最適化システム

実行環境、問題特性、過去の実行結果に基づいて
最適な設定を自動的に選択・調整します。
"""
import logging
import json
import os
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import psutil
import numpy as np
from collections import defaultdict

from ....domain.entities.school import School
from ....domain.entities.schedule import Schedule

# Avoid circular import
if TYPE_CHECKING:
    from .ultra_optimized_schedule_generator import (
        UltraOptimizationConfig,
        OptimizationLevel,
        OptimizationResult
    )


@dataclass
class SystemProfile:
    """システムプロファイル"""
    cpu_cores: int
    cpu_threads: int
    memory_gb: float
    cpu_speed_index: float  # ベンチマークスコア
    has_gpu: bool
    os_type: str
    python_version: str


@dataclass
class ProblemProfile:
    """問題プロファイル"""
    num_classes: int
    num_teachers: int
    num_subjects: int
    num_time_slots: int
    
    # 複雑性指標
    constraint_density: float  # 制約の密度
    fixed_ratio: float  # 固定授業の割合
    exchange_class_count: int  # 交流学級数
    special_requirements: int  # 特殊要件数
    
    # 推定難易度（0-1）
    estimated_difficulty: float = 0.0
    
    def calculate_difficulty(self):
        """難易度を計算"""
        # 基本的な複雑さ
        size_factor = (self.num_classes * self.num_time_slots) / 1000.0
        
        # 制約の複雑さ
        constraint_factor = self.constraint_density
        
        # 特殊要件の影響
        special_factor = min(1.0, self.special_requirements / 10.0)
        
        # 交流学級の影響
        exchange_factor = min(1.0, self.exchange_class_count / 5.0)
        
        # 総合難易度
        self.estimated_difficulty = min(1.0, 
            size_factor * 0.3 +
            constraint_factor * 0.3 +
            special_factor * 0.2 +
            exchange_factor * 0.2
        )


@dataclass
class ExecutionHistory:
    """実行履歴"""
    problem_hash: str
    config_used: Dict[str, Any]
    execution_time: float
    violations: int
    success: bool
    teacher_satisfaction: float
    memory_used_mb: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OptimizationRecommendation:
    """最適化推奨設定"""
    config: 'UltraOptimizationConfig'
    confidence: float
    reasoning: List[str]
    expected_time: float
    expected_quality: float


class AutoOptimizer:
    """自動最適化システム"""
    
    def __init__(
        self,
        history_file: str = "optimization_history.json",
        profile_cache_file: str = "system_profile_cache.json"
    ):
        self.logger = logging.getLogger(__name__)
        self.history_file = Path(history_file)
        self.profile_cache_file = Path(profile_cache_file)
        
        # 実行履歴
        self.execution_history: List[ExecutionHistory] = []
        self.load_history()
        
        # システムプロファイル（キャッシュ）
        self.system_profile = self._get_or_create_system_profile()
        
        # 設定テンプレート
        self.config_templates = self._create_config_templates()
        
        # 統計情報
        self.stats = {
            'total_optimizations': 0,
            'successful_optimizations': 0,
            'average_improvement': 0.0
        }
    
    def recommend_config(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> OptimizationRecommendation:
        """最適な設定を推奨"""
        self.logger.info("=== 自動最適化分析開始 ===")
        
        # 問題プロファイルを作成
        problem_profile = self._analyze_problem(school, initial_schedule)
        self.logger.info(f"問題難易度: {problem_profile.estimated_difficulty:.2f}")
        
        # システム能力を評価
        system_capability = self._evaluate_system_capability()
        self.logger.info(f"システム能力スコア: {system_capability:.2f}")
        
        # 類似の過去実行を検索
        similar_executions = self._find_similar_executions(problem_profile)
        
        # 最適設定を決定
        if similar_executions:
            # 過去の成功事例に基づく設定
            config, reasoning = self._config_from_history(
                similar_executions,
                problem_profile,
                system_capability
            )
            confidence = min(0.9, len(similar_executions) / 10.0)
        else:
            # ルールベースの設定
            config, reasoning = self._config_from_rules(
                problem_profile,
                system_capability
            )
            confidence = 0.7
        
        # ユーザー設定を反映
        if user_preferences:
            config = self._apply_user_preferences(config, user_preferences)
            reasoning.append("ユーザー設定を適用")
        
        # 期待値を計算
        expected_time = self._estimate_execution_time(problem_profile, config)
        expected_quality = self._estimate_quality(problem_profile, config)
        
        recommendation = OptimizationRecommendation(
            config=config,
            confidence=confidence,
            reasoning=reasoning,
            expected_time=expected_time,
            expected_quality=expected_quality
        )
        
        self._log_recommendation(recommendation)
        self.stats['total_optimizations'] += 1
        
        return recommendation
    
    def record_execution(
        self,
        school: School,
        config: 'UltraOptimizationConfig',
        result: 'OptimizationResult'
    ):
        """実行結果を記録"""
        problem_profile = self._analyze_problem(school, result.schedule)
        
        history_entry = ExecutionHistory(
            problem_hash=self._compute_problem_hash(problem_profile),
            config_used=asdict(config),
            execution_time=result.execution_time,
            violations=result.violations,
            success=result.is_successful(),
            teacher_satisfaction=result.statistics.get('teacher_satisfaction', {}).get('average', 0.0),
            memory_used_mb=result.statistics.get('memory_usage', {}).get('peak_mb', 0.0)
        )
        
        self.execution_history.append(history_entry)
        
        # 成功率を更新
        if history_entry.success:
            self.stats['successful_optimizations'] += 1
        
        # 改善率を計算
        if len(self.execution_history) > 1:
            prev_time = self.execution_history[-2].execution_time
            improvement = (prev_time - result.execution_time) / prev_time
            n = len(self.execution_history)
            self.stats['average_improvement'] = (
                (self.stats['average_improvement'] * (n - 1) + improvement) / n
            )
        
        # 履歴を保存
        self.save_history()
        
        self.logger.info(f"実行結果を記録: 成功={history_entry.success}, 時間={history_entry.execution_time:.1f}秒")
    
    def _analyze_problem(
        self,
        school: School,
        initial_schedule: Optional[Schedule]
    ) -> ProblemProfile:
        """問題を分析してプロファイルを作成"""
        classes = school.get_all_classes()
        teachers = school.get_all_teachers()
        # Get all subjects from class requirements
        subjects = set()
        for class_ref in classes:
            subjects.update(school.get_required_subjects(class_ref))
        
        # 基本情報
        num_classes = len(classes)
        num_teachers = len(teachers)
        num_subjects = len(subjects)
        num_time_slots = 30  # 5日 × 6時限
        
        # 制約密度を計算
        total_possible_assignments = num_classes * num_time_slots
        constraints_count = self._count_constraints(school)
        constraint_density = min(1.0, constraints_count / total_possible_assignments)
        
        # 固定授業の割合
        fixed_count = 0
        if initial_schedule:
            for _, assignment in initial_schedule.get_all_assignments():
                if assignment.subject.name in ["欠", "YT", "学", "道", "総合", "行"]:
                    fixed_count += 1
        fixed_ratio = fixed_count / total_possible_assignments if total_possible_assignments > 0 else 0
        
        # 交流学級数
        exchange_class_count = sum(1 for c in classes if c.class_number >= 6)
        
        # 特殊要件数（5組、テスト期間など）
        special_requirements = 0
        if any(c.class_number == 5 for c in classes):
            special_requirements += 3  # 5組は特殊
        # 他の特殊要件もカウント
        
        profile = ProblemProfile(
            num_classes=num_classes,
            num_teachers=num_teachers,
            num_subjects=num_subjects,
            num_time_slots=num_time_slots,
            constraint_density=constraint_density,
            fixed_ratio=fixed_ratio,
            exchange_class_count=exchange_class_count,
            special_requirements=special_requirements
        )
        
        profile.calculate_difficulty()
        
        return profile
    
    def _evaluate_system_capability(self) -> float:
        """システム能力を評価（0-1）"""
        # CPU性能
        cpu_score = min(1.0, self.system_profile.cpu_threads / 16.0)
        
        # メモリ容量
        memory_score = min(1.0, self.system_profile.memory_gb / 16.0)
        
        # CPU速度
        speed_score = min(1.0, self.system_profile.cpu_speed_index / 2000.0)
        
        # 総合スコア
        capability = (
            cpu_score * 0.4 +
            memory_score * 0.3 +
            speed_score * 0.3
        )
        
        return capability
    
    def _find_similar_executions(
        self,
        problem_profile: ProblemProfile,
        max_results: int = 10
    ) -> List[ExecutionHistory]:
        """類似の過去実行を検索"""
        if not self.execution_history:
            return []
        
        # 類似度を計算
        similarities = []
        current_hash = self._compute_problem_hash(problem_profile)
        
        for history in self.execution_history:
            # 問題の類似度
            if history.problem_hash == current_hash:
                similarity = 1.0
            else:
                # 簡易的な類似度計算
                similarity = 0.5
            
            # 成功した実行を優先
            if history.success:
                similarity *= 1.5
            
            similarities.append((similarity, history))
        
        # 類似度でソート
        similarities.sort(key=lambda x: x[0], reverse=True)
        
        # 上位を返す
        return [h for _, h in similarities[:max_results]]
    
    def _config_from_history(
        self,
        similar_executions: List[ExecutionHistory],
        problem_profile: ProblemProfile,
        system_capability: float
    ) -> Tuple['UltraOptimizationConfig', List[str]]:
        """過去の実行履歴から設定を生成"""
        from .ultra_optimized_schedule_generator import UltraOptimizationConfig
        
        reasoning = ["過去の成功事例に基づく設定"]
        
        # 成功した実行の設定を集計
        successful_configs = [
            h.config_used for h in similar_executions
            if h.success
        ]
        
        if not successful_configs:
            # 成功事例がない場合はルールベースにフォールバック
            return self._config_from_rules(problem_profile, system_capability)
        
        # 最も成功率の高い設定を基準にする
        base_config = successful_configs[0]
        
        # UltraOptimizationConfigを作成
        config = UltraOptimizationConfig()
        
        # 設定を適用
        for key, value in base_config.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # システム能力に応じて調整
        if system_capability < 0.5:
            config.max_workers = min(config.max_workers, 2)
            config.enable_parallel_processing = False
            reasoning.append("システム性能が低いため並列処理を制限")
        
        reasoning.append(f"{len(successful_configs)}個の成功事例を参考")
        
        return config, reasoning
    
    def _config_from_rules(
        self,
        problem_profile: ProblemProfile,
        system_capability: float
    ) -> Tuple['UltraOptimizationConfig', List[str]]:
        """ルールベースで設定を生成"""
        from .ultra_optimized_schedule_generator import UltraOptimizationConfig, OptimizationLevel
        
        reasoning = ["ルールベースの自動設定"]
        
        # 基本設定
        config = UltraOptimizationConfig()
        
        # 問題の難易度に応じた最適化レベル
        if problem_profile.estimated_difficulty < 0.3:
            config.optimization_level = OptimizationLevel.FAST
            reasoning.append("簡単な問題のため高速モード")
        elif problem_profile.estimated_difficulty < 0.6:
            config.optimization_level = OptimizationLevel.BALANCED
            reasoning.append("中程度の問題のためバランスモード")
        else:
            config.optimization_level = OptimizationLevel.QUALITY
            reasoning.append("難しい問題のため品質重視モード")
        
        # システム能力に応じた並列設定
        if system_capability > 0.7:
            config.enable_parallel_processing = True
            config.max_workers = self.system_profile.cpu_threads
            reasoning.append("高性能システムのため並列処理を最大化")
        elif system_capability > 0.4:
            config.enable_parallel_processing = True
            config.max_workers = max(2, self.system_profile.cpu_threads // 2)
            reasoning.append("中性能システムのため並列処理を調整")
        else:
            config.enable_parallel_processing = False
            config.max_workers = 1
            reasoning.append("低性能システムのため並列処理を無効化")
        
        # 問題特性に応じた機能設定
        if problem_profile.exchange_class_count > 0:
            config.enable_test_period_protection = True
            reasoning.append("交流学級があるため厳密な制約チェックを有効化")
        
        if problem_profile.constraint_density > 0.7:
            config.enable_violation_learning = True
            config.enable_learning = True
            reasoning.append("制約が多いため学習機能を有効化")
        
        # メモリに応じたキャッシュ設定
        if self.system_profile.memory_gb > 8:
            config.cache_size_mb = 500
            config.enable_caching = True
            reasoning.append("十分なメモリがあるため大容量キャッシュを使用")
        elif self.system_profile.memory_gb > 4:
            config.cache_size_mb = 200
            config.enable_caching = True
            reasoning.append("標準的なキャッシュサイズを使用")
        else:
            config.cache_size_mb = 50
            config.enable_caching = False
            reasoning.append("メモリが少ないためキャッシュを制限")
        
        # ビーム幅の調整
        if problem_profile.num_classes < 20:
            config.beam_width = 5
        elif problem_profile.num_classes < 30:
            config.beam_width = 10
        else:
            config.beam_width = 15
        reasoning.append(f"問題規模に応じてビーム幅を{config.beam_width}に設定")
        
        return config, reasoning
    
    def _apply_user_preferences(
        self,
        config: 'UltraOptimizationConfig',
        preferences: Dict[str, Any]
    ) -> 'UltraOptimizationConfig':
        """ユーザー設定を適用"""
        for key, value in preferences.items():
            if hasattr(config, key):
                setattr(config, key, value)
                self.logger.debug(f"ユーザー設定を適用: {key}={value}")
        
        return config
    
    def _estimate_execution_time(
        self,
        problem_profile: ProblemProfile,
        config: 'UltraOptimizationConfig'
    ) -> float:
        """実行時間を推定（秒）"""
        from .ultra_optimized_schedule_generator import OptimizationLevel
        # 基本時間（問題サイズに基づく）
        base_time = problem_profile.num_classes * problem_profile.num_time_slots * 0.001
        
        # 難易度による調整
        difficulty_factor = 1.0 + problem_profile.estimated_difficulty * 2.0
        
        # 最適化レベルによる調整
        if config.optimization_level == OptimizationLevel.FAST:
            level_factor = 0.5
        elif config.optimization_level == OptimizationLevel.BALANCED:
            level_factor = 1.0
        elif config.optimization_level == OptimizationLevel.QUALITY:
            level_factor = 2.0
        else:  # EXTREME
            level_factor = 5.0
        
        # 並列処理による高速化
        if config.enable_parallel_processing:
            parallel_factor = 1.0 / (1.0 + np.log(config.max_workers))
        else:
            parallel_factor = 1.0
        
        # 最終的な推定時間
        estimated_time = base_time * difficulty_factor * level_factor * parallel_factor
        
        return max(0.1, estimated_time)
    
    def _estimate_quality(
        self,
        problem_profile: ProblemProfile,
        config: 'UltraOptimizationConfig'
    ) -> float:
        """品質を推定（0-1）"""
        from .ultra_optimized_schedule_generator import OptimizationLevel
        # 基本品質
        base_quality = 0.7
        
        # 最適化レベルによる品質
        if config.optimization_level == OptimizationLevel.QUALITY:
            base_quality += 0.2
        elif config.optimization_level == OptimizationLevel.EXTREME:
            base_quality += 0.25
        elif config.optimization_level == OptimizationLevel.FAST:
            base_quality -= 0.1
        
        # 学習機能による品質向上
        if config.enable_learning and config.enable_violation_learning:
            base_quality += 0.05
        
        # 問題の難易度による調整
        quality = base_quality * (1.0 - problem_profile.estimated_difficulty * 0.3)
        
        return min(1.0, max(0.1, quality))
    
    def _get_or_create_system_profile(self) -> SystemProfile:
        """システムプロファイルを取得または作成"""
        # キャッシュから読み込み
        if self.profile_cache_file.exists():
            try:
                with open(self.profile_cache_file, 'r') as f:
                    data = json.load(f)
                    return SystemProfile(**data)
            except:
                pass
        
        # 新規作成
        profile = self._create_system_profile()
        
        # キャッシュに保存
        try:
            with open(self.profile_cache_file, 'w') as f:
                json.dump(asdict(profile), f)
        except:
            pass
        
        return profile
    
    def _create_system_profile(self) -> SystemProfile:
        """システムプロファイルを作成"""
        import platform
        import sys
        
        # CPU情報
        cpu_cores = psutil.cpu_count(logical=False) or 1
        cpu_threads = psutil.cpu_count(logical=True) or 1
        
        # メモリ情報
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # CPU速度の簡易ベンチマーク
        cpu_speed_index = self._benchmark_cpu()
        
        # GPU情報（簡易チェック）
        has_gpu = self._check_gpu()
        
        # OS情報
        os_type = platform.system()
        
        # Python情報
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        
        return SystemProfile(
            cpu_cores=cpu_cores,
            cpu_threads=cpu_threads,
            memory_gb=memory_gb,
            cpu_speed_index=cpu_speed_index,
            has_gpu=has_gpu,
            os_type=os_type,
            python_version=python_version
        )
    
    def _benchmark_cpu(self) -> float:
        """CPU速度の簡易ベンチマーク"""
        import time
        
        # 簡単な計算でCPU速度を測定
        start = time.perf_counter()
        
        # 行列演算
        a = np.random.rand(100, 100)
        for _ in range(100):
            b = np.dot(a, a)
        
        elapsed = time.perf_counter() - start
        
        # スコア化（低いほど高速）
        score = 1000.0 / elapsed
        
        return score
    
    def _check_gpu(self) -> bool:
        """GPUの存在をチェック"""
        # 簡易的な実装
        try:
            import torch
            return torch.cuda.is_available()
        except:
            pass
        
        try:
            import tensorflow as tf
            return len(tf.config.list_physical_devices('GPU')) > 0
        except:
            pass
        
        return False
    
    def _count_constraints(self, school: School) -> int:
        """制約数をカウント"""
        # 簡易的な実装
        count = 0
        
        # 教師制約
        count += len(school.get_all_teachers()) * 30
        
        # 交流学級制約
        exchange_classes = sum(1 for c in school.get_all_classes() if c.class_number >= 6)
        count += exchange_classes * 10
        
        # その他の制約
        count += 100  # 基本制約
        
        return count
    
    def _compute_problem_hash(self, profile: ProblemProfile) -> str:
        """問題のハッシュを計算"""
        # 簡易的な実装
        key_values = [
            profile.num_classes,
            profile.num_teachers,
            profile.num_subjects,
            int(profile.constraint_density * 100),
            int(profile.estimated_difficulty * 100)
        ]
        
        return "_".join(map(str, key_values))
    
    def _create_config_templates(self) -> Dict[str, 'UltraOptimizationConfig']:
        """設定テンプレートを作成"""
        from .ultra_optimized_schedule_generator import UltraOptimizationConfig, OptimizationLevel
        
        templates = {}
        
        # 高速モード
        fast_config = UltraOptimizationConfig()
        fast_config.optimization_level = OptimizationLevel.FAST
        fast_config.max_workers = 2
        fast_config.beam_width = 5
        fast_config.time_limit = 60
        templates['fast'] = fast_config
        
        # バランスモード
        balanced_config = UltraOptimizationConfig()
        balanced_config.optimization_level = OptimizationLevel.BALANCED
        balanced_config.max_workers = 4
        balanced_config.beam_width = 10
        balanced_config.time_limit = 180
        templates['balanced'] = balanced_config
        
        # 品質重視モード
        quality_config = UltraOptimizationConfig()
        quality_config.optimization_level = OptimizationLevel.QUALITY
        quality_config.max_workers = 8
        quality_config.beam_width = 15
        quality_config.time_limit = 300
        quality_config.enable_learning = True
        quality_config.enable_violation_learning = True
        templates['quality'] = quality_config
        
        return templates
    
    def _log_recommendation(self, recommendation: OptimizationRecommendation):
        """推奨設定をログ出力"""
        self.logger.info("=== 自動最適化推奨設定 ===")
        self.logger.info(f"信頼度: {recommendation.confidence:.1%}")
        self.logger.info(f"予想実行時間: {recommendation.expected_time:.1f}秒")
        self.logger.info(f"予想品質: {recommendation.expected_quality:.1%}")
        
        self.logger.info("推奨理由:")
        for reason in recommendation.reasoning:
            self.logger.info(f"  - {reason}")
        
        config = recommendation.config
        self.logger.info("主要設定:")
        self.logger.info(f"  最適化レベル: {config.optimization_level.value}")
        self.logger.info(f"  並列処理: {'有効' if config.enable_parallel_processing else '無効'}")
        self.logger.info(f"  ワーカー数: {config.max_workers}")
        self.logger.info(f"  ビーム幅: {config.beam_width}")
    
    def save_history(self):
        """実行履歴を保存"""
        try:
            history_data = [
                {
                    **asdict(h),
                    'timestamp': h.timestamp.isoformat()
                }
                for h in self.execution_history[-1000:]  # 最新1000件のみ保存
            ]
            
            with open(self.history_file, 'w') as f:
                json.dump(history_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"履歴の保存に失敗: {e}")
    
    def load_history(self):
        """実行履歴を読み込み"""
        if not self.history_file.exists():
            return
        
        try:
            with open(self.history_file, 'r') as f:
                history_data = json.load(f)
            
            self.execution_history = [
                ExecutionHistory(
                    **{k: v for k, v in h.items() if k != 'timestamp'},
                    timestamp=datetime.fromisoformat(h['timestamp'])
                )
                for h in history_data
            ]
            
        except Exception as e:
            self.logger.error(f"履歴の読み込みに失敗: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        success_rate = (
            self.stats['successful_optimizations'] / 
            self.stats['total_optimizations']
            if self.stats['total_optimizations'] > 0 else 0
        )
        
        return {
            'total_optimizations': self.stats['total_optimizations'],
            'success_rate': success_rate,
            'average_improvement': self.stats['average_improvement'],
            'history_size': len(self.execution_history),
            'system_profile': asdict(self.system_profile)
        }