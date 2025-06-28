"""並列タスクとその結果の定義

並列処理エンジンで使用するタスクと結果のデータクラスを定義します。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .....domain.entities.schedule import Schedule


@dataclass
class ParallelTask:
    """並列タスクの定義
    
    Attributes:
        task_id: タスクの一意識別子
        task_type: タスクタイプ（"placement", "verification", "optimization"）
        target: 処理対象（クラス、時間帯、または最適化対象）
        function: 実行する関数名
        args: 関数に渡す引数
        priority: 優先度（高いほど先に実行）
    """
    task_id: str
    task_type: str
    target: Any
    function: str
    args: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0


@dataclass
class TaskResult:
    """タスク実行結果
    
    Attributes:
        task_id: タスクの一意識別子
        success: 成功したかどうか
        result: 実行結果
        error: エラーメッセージ（エラー時のみ）
        execution_time: 実行時間（秒）
        improvements: 改善点のリスト
    """
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    improvements: List[str] = field(default_factory=list)


@dataclass
class OptimizationCandidate:
    """最適化候補
    
    最適化プロセスで生成される候補解を表現します。
    
    Attributes:
        schedule: スケジュール
        score: 評価スコア（高いほど良い）
        violations: 制約違反数
        conflicts: 教師の競合数
        metadata: その他のメタデータ
    """
    schedule: Schedule
    score: float
    violations: int
    conflicts: int
    metadata: Dict[str, Any] = field(default_factory=dict)