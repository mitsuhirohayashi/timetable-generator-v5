"""ドメイン層の共通定数定義

このファイルには、システム全体で使用される定数を定義します。
設定ファイルから動的に読み込まれる値と、コード内で固定の値の両方を管理します。
"""

from typing import FrozenSet, List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# グローバル変数として設定を保持
_config_loaded = False
_config = None

def _load_config():
    """設定を遅延読み込み"""
    global _config_loaded, _config
    if not _config_loaded:
        try:
            # 循環インポートを避けるため、関数内でインポート
            from ..infrastructure.config.system_config_loader import get_system_config
            _config = get_system_config()
            _config_loaded = True
        except Exception as e:
            logger.warning(f"設定ファイルの読み込みに失敗しました。デフォルト値を使用します: {e}")
            _config = None
            _config_loaded = True
    return _config

# デフォルト値を定義
_DEFAULT_WEEKDAYS = ["月", "火", "水", "木", "金"]
_DEFAULT_MIN_PERIOD = 1
_DEFAULT_MAX_PERIOD = 6
_DEFAULT_GRADE5_CLASSES = ["1年5組", "2年5組", "3年5組"]
_DEFAULT_JIRITSU_SUBJECTS = ["自立", "日生", "生単", "作業"]
_DEFAULT_JIRITSU_PARENT_SUBJECTS = ["数", "英"]
_DEFAULT_FIXED_SUBJECTS = [
    "欠", "YT", "学", "学活", "総", "総合", "道", "道徳", 
    "学総", "行", "行事", "テスト", "技家"
]
_DEFAULT_MEETING_TYPES = ["HF", "企画", "特会", "生指"]
_DEFAULT_MEETINGS = {
    "HF": ("火", 4),
    "企画": ("火", 3),
    "特会": ("水", 2),
    "生指": ("木", 3)
}
_DEFAULT_CORE_SUBJECTS = ["国", "数", "英", "理", "社"]
_DEFAULT_SPECIAL_SUBJECTS = ["音", "美", "技", "家", "体"]
_DEFAULT_OTHER_SUBJECTS = ["道", "総", "学"]
_DEFAULT_EXCHANGE_CLASS_PAIRS = {
    "1年6組": "1年1組",
    "1年7組": "1年2組",
    "2年6組": "2年3組",
    "2年7組": "2年2組",
    "3年6組": "3年3組",
    "3年7組": "3年2組"
}
_DEFAULT_STANDARD_HOURS = {
    "国": 4,
    "数": 3,
    "英": 4,
    "理": 3,
    "社": 3,
    "音": 1,
    "美": 1,
    "体": 3,
    "技": 1,
    "家": 1,
    "道": 1,
    "総": 2,
    "学": 1
}

# プロパティアクセサーを定義
@property
def WEEKDAYS() -> List[str]:
    """曜日リスト"""
    config = _load_config()
    return config.weekdays if config else _DEFAULT_WEEKDAYS

@property
def WEEKDAY_SET() -> FrozenSet[str]:
    """曜日セット"""
    return frozenset(WEEKDAYS)

@property
def MIN_PERIOD() -> int:
    """最小時限"""
    config = _load_config()
    return config.periods['min'] if config else _DEFAULT_MIN_PERIOD

@property
def MAX_PERIOD() -> int:
    """最大時限"""
    config = _load_config()
    return config.periods['max'] if config else _DEFAULT_MAX_PERIOD

# 直接定義する定数（プロパティではない）
WEEKDAYS: List[str] = _DEFAULT_WEEKDAYS
WEEKDAY_SET: FrozenSet[str] = frozenset(WEEKDAYS)
MIN_PERIOD = _DEFAULT_MIN_PERIOD
MAX_PERIOD = _DEFAULT_MAX_PERIOD
PERIODS = range(MIN_PERIOD, MAX_PERIOD + 1)
PERIOD_COUNT = MAX_PERIOD - MIN_PERIOD + 1

# 5組関連
GRADE5_CLASSES: FrozenSet[str] = frozenset(_DEFAULT_GRADE5_CLASSES)
GRADE5_CLASS_LIST: List[str] = _DEFAULT_GRADE5_CLASSES

# 自立活動関連
JIRITSU_SUBJECTS: FrozenSet[str] = frozenset(_DEFAULT_JIRITSU_SUBJECTS)
JIRITSU_PARENT_SUBJECTS: FrozenSet[str] = frozenset(_DEFAULT_JIRITSU_PARENT_SUBJECTS)

# 固定科目関連
FIXED_SUBJECTS: FrozenSet[str] = frozenset(_DEFAULT_FIXED_SUBJECTS)

# 会議関連
MEETING_TYPES: FrozenSet[str] = frozenset(_DEFAULT_MEETING_TYPES)
DEFAULT_MEETINGS: Dict[str, tuple[str, int]] = _DEFAULT_MEETINGS

# 教科カテゴリ
CORE_SUBJECTS: FrozenSet[str] = frozenset(_DEFAULT_CORE_SUBJECTS)
SPECIAL_SUBJECTS: FrozenSet[str] = frozenset(_DEFAULT_SPECIAL_SUBJECTS)
OTHER_SUBJECTS: FrozenSet[str] = frozenset(_DEFAULT_OTHER_SUBJECTS)

# 交流学級ペア
EXCHANGE_CLASS_PAIRS: Dict[str, str] = _DEFAULT_EXCHANGE_CLASS_PAIRS

# 標準授業時間（1週間あたり）
STANDARD_HOURS: Dict[str, int] = _DEFAULT_STANDARD_HOURS

# 制約優先度
class Priority:
    """制約の優先度定数"""
    CRITICAL = 100
    HIGH = 80
    MEDIUM = 60
    LOW = 40
    VERY_LOW = 20

# エラーメッセージテンプレート（コード固定）
ERROR_MESSAGES = {
    "teacher_conflict": "{teacher}先生が{day}{period}限に複数のクラスを担当しています: {classes}",
    "gym_conflict": "{day}{period}限に体育館を複数のクラスが使用しています: {classes}",
    "daily_duplicate": "{class_ref}の{day}に{subject}が{count}回配置されています",
    "jiritsu_sync": "{exchange_class}の自立活動時、{parent_class}は数学か英語でなければなりません",
    "fixed_subject": "{day}{period}限の{subject}は固定科目のため変更できません"
}

# ログレベル（コード固定）
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50
}

def reload_constants():
    """定数を再読み込み"""
    global _config_loaded, _config
    _config_loaded = False
    _config = None
    
    # 再読み込み
    config = _load_config()
    if config:
        # グローバル変数を更新
        global WEEKDAYS, WEEKDAY_SET, MIN_PERIOD, MAX_PERIOD, PERIODS, PERIOD_COUNT
        global GRADE5_CLASSES, GRADE5_CLASS_LIST, JIRITSU_SUBJECTS, JIRITSU_PARENT_SUBJECTS
        global FIXED_SUBJECTS, MEETING_TYPES, DEFAULT_MEETINGS
        global CORE_SUBJECTS, SPECIAL_SUBJECTS, OTHER_SUBJECTS
        global EXCHANGE_CLASS_PAIRS, STANDARD_HOURS
        
        WEEKDAYS = config.weekdays
        WEEKDAY_SET = frozenset(WEEKDAYS)
        MIN_PERIOD = config.periods['min']
        MAX_PERIOD = config.periods['max']
        PERIODS = range(MIN_PERIOD, MAX_PERIOD + 1)
        PERIOD_COUNT = MAX_PERIOD - MIN_PERIOD + 1
        
        GRADE5_CLASSES = frozenset(config.grade5_classes)
        GRADE5_CLASS_LIST = config.grade5_classes
        
        JIRITSU_SUBJECTS = config.jiritsu_subjects
        JIRITSU_PARENT_SUBJECTS = config.jiritsu_parent_subjects
        
        FIXED_SUBJECTS = config.fixed_subjects
        
        MEETING_TYPES = config.meeting_types
        DEFAULT_MEETINGS = config.default_meetings
        
        CORE_SUBJECTS = config.core_subjects
        SPECIAL_SUBJECTS = config.special_subjects
        OTHER_SUBJECTS = config.other_subjects
        
        EXCHANGE_CLASS_PAIRS = config.exchange_class_pairs
        STANDARD_HOURS = config.standard_hours
        
        # 優先度も更新
        Priority.CRITICAL = config.constraint_priorities['critical']
        Priority.HIGH = config.constraint_priorities['high']
        Priority.MEDIUM = config.constraint_priorities['medium']
        Priority.LOW = config.constraint_priorities['low']
        Priority.VERY_LOW = config.constraint_priorities['very_low']
        
        logger.info("定数を設定ファイルから再読み込みしました")