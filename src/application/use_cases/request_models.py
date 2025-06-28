"""スケジュール生成・検証のリクエスト/レスポンスモデル"""
from dataclasses import dataclass
from pathlib import Path
from ...domain.entities.schedule import Schedule


@dataclass
class GenerateScheduleRequest:
    """スケジュール生成リクエスト"""
    # ファイル設定
    base_timetable_file: str = "base_timetable.csv"
    desired_timetable_file: str = "input.csv"
    followup_prompt_file: str = "Follow-up.csv"
    basics_file: str = "config/basics.csv"
    output_file: str = "output.csv"
    data_directory: Path = Path(".")
    
    # 基本生成設定
    strategy: str = 'legacy'
    max_iterations: int = 100
    enable_soft_constraints: bool = True
    use_random: bool = False
    randomness_level: float = 0.3
    exploration_range: int = 10
    start_empty: bool = False
    use_advanced_csp: bool = False
    use_improved_csp: bool = False  # 改良版CSPアルゴリズムを使用するかどうか
    use_ultrathink: bool = False  # Ultrathink Perfect Generatorを使用するかどうか
    use_grade5_priority: bool = False  # 5組優先配置アルゴリズムを使用するかどうか
    use_unified_hybrid: bool = False  # 統一ハイブリッドアルゴリズムを使用するかどうか
    # fill_empty_slotsは削除されました - 常にTrueとして動作
    
    # 拡張機能フラグ（デフォルトは無効）
    optimize_meeting_times: bool = False  # 会議時間最適化
    optimize_gym_usage: bool = False      # 体育館使用最適化
    optimize_workload: bool = False       # 教師負担最適化
    use_support_hours: bool = False       # 5組時数表記
    search_mode: str = "standard"         # 探索モード: standard, priority, smart, hybrid
    
    # 超最適化オプション
    use_ultra_optimized: bool = False      # 超最適化ジェネレーターを使用
    ultra_config: dict = None              # 超最適化の詳細設定
    use_auto_optimization: bool = True     # 自動最適化を使用（Ultrathink時のみ有効）
    
    # 人間的柔軟性オプション
    human_like_flexibility: bool = False   # 人間的な柔軟性（教師代替、時数借用など）を有効化


@dataclass
class GenerateScheduleResult:
    """スケジュール生成結果"""
    schedule: Schedule
    violations_count: int
    success: bool
    message: str
    execution_time: float
    # 最適化結果
    meeting_improvements: int = 0
    gym_improvements: int = 0
    workload_improvements: int = 0


@dataclass
class ValidateScheduleRequest:
    """スケジュール検証リクエスト"""
    schedule_file: str
    data_directory: Path = Path(".")
    enable_soft_constraints: bool = True


@dataclass 
class ValidateScheduleResult:
    """スケジュール検証結果"""
    is_valid: bool
    violations: list
    violations_count: int
    message: str