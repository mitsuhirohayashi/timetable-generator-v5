"""テスト期間データ保持チェックユーティリティ"""
import logging
from typing import Dict, Set, Tuple, List
from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference
from .test_period_protector import TestPeriodProtector
from ....shared.mixins.logging_mixin import LoggingMixin


class TestPeriodPreservationChecker(LoggingMixin):
    """テスト期間データが保持されているかチェックするユーティリティ"""
    
    def __init__(self):
        super().__init__()
        self.protector = TestPeriodProtector()
    
    def check_test_period_preservation(
        self, 
        initial_schedule: Schedule, 
        final_schedule: Schedule, 
        school: School
    ) -> Dict[str, any]:
        """初期スケジュールと最終スケジュールを比較してテスト期間データの保持状況をチェック"""
        
        results = {
            'total_test_slots': 0,
            'preserved_count': 0,
            'lost_count': 0,
            'lost_assignments': [],
            'preserved_by_class': {},
            'lost_by_class': {}
        }
        
        # すべてのテスト期間スロットをチェック
        for day, period in self.protector.test_periods:
            time_slot = TimeSlot(day, period)
            results['total_test_slots'] += 1
            
            for class_ref in school.get_all_classes():
                initial_assignment = initial_schedule.get_assignment(time_slot, class_ref)
                final_assignment = final_schedule.get_assignment(time_slot, class_ref)
                
                # クラス別の統計を初期化
                class_key = class_ref.full_name
                if class_key not in results['preserved_by_class']:
                    results['preserved_by_class'][class_key] = 0
                    results['lost_by_class'][class_key] = 0
                
                if initial_assignment:
                    if final_assignment and initial_assignment.subject.name == final_assignment.subject.name:
                        # データが保持されている
                        results['preserved_count'] += 1
                        results['preserved_by_class'][class_key] += 1
                    else:
                        # データが失われている
                        results['lost_count'] += 1
                        results['lost_by_class'][class_key] += 1
                        results['lost_assignments'].append({
                            'time_slot': time_slot,
                            'class': class_ref,
                            'initial_subject': initial_assignment.subject.name,
                            'final_subject': final_assignment.subject.name if final_assignment else 'None',
                            'was_locked': initial_schedule.is_locked(time_slot, class_ref)
                        })
        
        # ログ出力
        self._log_results(results)
        
        return results
    
    def _log_results(self, results: Dict[str, any]) -> None:
        """チェック結果をログ出力"""
        self.logger.warning("=== テスト期間データ保持チェック結果 ===")
        self.logger.warning(f"総テスト期間割り当て数: {results['preserved_count'] + results['lost_count']}")
        self.logger.warning(f"保持された割り当て: {results['preserved_count']}")
        self.logger.warning(f"失われた割り当て: {results['lost_count']}")
        
        if results['lost_count'] > 0:
            self.logger.error("=== 失われたテスト期間データ ===")
            # クラス別の集計
            for class_name, count in results['lost_by_class'].items():
                if count > 0:
                    self.logger.error(f"{class_name}: {count}件のデータが失われました")
            
            # 詳細情報（最初の10件）
            self.logger.error("=== 詳細（最初の10件） ===")
            for i, lost in enumerate(results['lost_assignments'][:10]):
                lock_status = "ロック済み" if lost['was_locked'] else "未ロック"
                self.logger.error(
                    f"{i+1}. {lost['time_slot']} {lost['class']}: "
                    f"{lost['initial_subject']} → {lost['final_subject']} ({lock_status})"
                )
        
        # クラス別の保持状況
        self.logger.info("=== クラス別保持状況 ===")
        for class_name in sorted(results['preserved_by_class'].keys()):
            preserved = results['preserved_by_class'][class_name]
            lost = results['lost_by_class'][class_name]
            total = preserved + lost
            if total > 0:
                rate = (preserved / total) * 100
                status = "✓" if lost == 0 else "✗"
                self.logger.info(f"{status} {class_name}: {preserved}/{total} ({rate:.1f}%)")