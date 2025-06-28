"""
超最適化時間割生成サービス

UltraOptimizedScheduleGeneratorをアプリケーション層から使用するためのサービス。
"""
import logging
import time
from typing import Dict, Any, Optional, Tuple

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from .ultrathink.ultra_optimized_schedule_generator import (
    UltraOptimizedScheduleGenerator,
    UltraOptimizationConfig
)


class UltraOptimizedGeneratorService:
    """超最適化時間割生成サービス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.generator = None
        self._initialized = False
    
    def initialize(self, config: Optional[Dict[str, Any]] = None):
        """
        ジェネレーターを初期化
        
        Args:
            config: 設定辞書
                - enable_parallel: 並列処理を有効化
                - cache_size_mb: キャッシュサイズ（MB）
                - beam_width: ビームサーチの幅
                - optimization_level: 最適化レベル
        """
        if self._initialized:
            return
        
        # 設定からUltraOptimizationConfigを作成
        ultra_config = self._create_config(config or {})
        
        # ジェネレーターを作成
        self.generator = UltraOptimizedScheduleGenerator(ultra_config)
        self._initialized = True
        
        self.logger.info("超最適化ジェネレーターを初期化しました")
    
    def generate(
        self,
        initial_schedule: Schedule,
        school: School,
        constraints: Optional[Dict[str, Any]] = None,
        time_limit: Optional[float] = None
    ) -> Tuple[Schedule, Dict[str, Any]]:
        """
        時間割を生成
        
        Args:
            initial_schedule: 初期スケジュール
            school: 学校情報
            constraints: 制約情報
            time_limit: 制限時間（秒）
            
        Returns:
            Tuple[生成されたスケジュール, 実行メトリクス]
        """
        if not self._initialized:
            self.initialize()
        
        self.logger.info("超最適化時間割生成を開始")
        start_time = time.time()
        
        # 制約情報の準備
        if constraints is None:
            constraints = self._get_default_constraints()
        
        # 時間制限の設定
        if time_limit is None:
            time_limit = 300  # デフォルト5分
        
        constraints['time_limit'] = time_limit
        
        try:
            # 生成実行
            schedule, metrics = self.generator.generate(
                initial_schedule,
                school,
                constraints
            )
            
            # 成功
            execution_time = time.time() - start_time
            self.logger.info(
                f"超最適化時間割生成完了: "
                f"実行時間={execution_time:.2f}秒, "
                f"違反数={metrics.get('total_violations', 'unknown')}"
            )
            
            # メトリクスに実行時間を追加
            metrics['total_execution_time'] = execution_time
            
            return schedule, metrics
            
        except Exception as e:
            self.logger.error(f"超最適化時間割生成でエラー: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        統計情報を取得
        
        Returns:
            統計情報の辞書
        """
        if not self._initialized:
            return {}
        
        return self.generator.get_statistics()
    
    def shutdown(self):
        """ジェネレーターをシャットダウン"""
        if self._initialized and self.generator:
            self.generator.shutdown()
            self._initialized = False
            self.logger.info("超最適化ジェネレーターをシャットダウンしました")
    
    def _create_config(self, config_dict: Dict[str, Any]) -> UltraOptimizationConfig:
        """設定オブジェクトを作成"""
        # Create config with defaults
        config = UltraOptimizationConfig()
        
        # Set valid attributes if they exist in config_dict
        if 'enable_parallel' in config_dict:
            config.enable_parallel_processing = config_dict['enable_parallel']
        if 'max_workers' in config_dict:
            config.max_workers = config_dict['max_workers']
        if 'cache_size_mb' in config_dict:
            config.cache_size_mb = config_dict['cache_size_mb']
        if 'optimization_level' in config_dict:
            # Convert string to OptimizationLevel if needed
            level = config_dict['optimization_level']
            if isinstance(level, str):
                from .ultrathink.ultra_optimized_schedule_generator import OptimizationLevel
                config.optimization_level = OptimizationLevel(level)
            else:
                config.optimization_level = level
        if 'enable_learning' in config_dict:
            config.enable_learning = config_dict['enable_learning']
        if 'time_limit' in config_dict:
            config.time_limit = config_dict['time_limit']
        if 'target_violations' in config_dict:
            config.target_violations = config_dict['target_violations']
            
        return config
    
    def _get_default_constraints(self) -> Dict[str, Any]:
        """デフォルト制約を取得"""
        return {
            'fixed_subjects': [
                "欠", "YT", "学", "学活", "総", "総合",
                "道", "道徳", "学総", "行", "行事", "テスト", "技家"
            ],
            'validate_immediately': True,
            'optimization_level': 'balanced'
        }
    
    def __enter__(self):
        """コンテキストマネージャー開始"""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了"""
        self.shutdown()