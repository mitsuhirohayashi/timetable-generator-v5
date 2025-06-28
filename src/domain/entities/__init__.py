"""ドメインエンティティ

Phase 2リファクタリング移行のため、一時的に新旧の実装を共存させています。
USE_REFACTORED_ENTITIESをTrueに設定すると、新しい実装が使用されます。
"""
import os

# 環境変数で切り替え可能にする
USE_REFACTORED_ENTITIES = os.environ.get('USE_REFACTORED_ENTITIES', 'False').lower() == 'true'

if USE_REFACTORED_ENTITIES:
    # リファクタリング版を使用
    from .schedule_refactored import Schedule
    from .school_refactored import School
    # Grade5Unitはまだリファクタリング版がないため、既存版を使用
    from .grade5_unit import Grade5Unit
else:
    # 既存版を使用（デフォルト）
    from .schedule import Schedule
    from .school import School
    from .grade5_unit import Grade5Unit

# データクラスとサービスは常にエクスポート（新規開発用）
from .schedule_data import ScheduleData
from .school_data import SchoolData
from .grade5_unit_data import Grade5UnitData

__all__ = [
    'Schedule',
    'School',
    'Grade5Unit',
    'ScheduleData',
    'SchoolData',
    'Grade5UnitData',
]