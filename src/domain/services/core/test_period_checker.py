"""テスト期間チェッカー - テスト期間かどうかを判定するサービス"""
from typing import Set, Tuple
from ....shared.mixins.logging_mixin import LoggingMixin
from ...value_objects.time_slot import TimeSlot


class TestPeriodChecker(LoggingMixin):
    """テスト期間かどうかを判定するサービス"""
    
    def __init__(self, test_periods: Set[Tuple[str, int]] = None):
        """初期化
        
        Args:
            test_periods: テスト期間のセット（曜日, 時限）のタプル
        """
        super().__init__()
        self.test_periods = test_periods or set()
        
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定された時間枠がテスト期間かどうか判定
        
        Args:
            time_slot: 判定する時間枠
            
        Returns:
            テスト期間の場合True
        """
        return (time_slot.day, time_slot.period) in self.test_periods
    
    def add_test_period(self, day: str, period: int) -> None:
        """テスト期間を追加
        
        Args:
            day: 曜日
            period: 時限
        """
        # 既に追加済みの場合はログを出力しない
        if (day, period) not in self.test_periods:
            self.logger.info(f"テスト期間追加: {day}曜{period}限")
        self.test_periods.add((day, period))
        
    def add_test_periods(self, periods: Set[Tuple[str, int]]) -> None:
        """複数のテスト期間を一括追加
        
        Args:
            periods: テスト期間のセット
        """
        self.test_periods.update(periods)
        
    def get_test_periods(self) -> Set[Tuple[str, int]]:
        """現在のテスト期間を取得
        
        Returns:
            テスト期間のセット
        """
        return self.test_periods.copy()