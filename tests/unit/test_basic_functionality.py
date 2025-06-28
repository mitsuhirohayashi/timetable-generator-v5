"""基本機能のテスト

時間割生成システムの基本的な機能をテストします。
"""
import unittest
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.domain.exceptions import (
    TimetableGenerationError,
    ConstraintViolationError,
    DataLoadingError
)
# script_utilitiesは削除されているため、必要な機能は直接実装
from src.domain.utils.schedule_utils import ScheduleUtils


class TestScheduleUtils(unittest.TestCase):
    """ScheduleUtilsのテスト"""
    
    def test_is_fixed_subject(self):
        """固定科目判定のテスト"""
        # 固定科目
        self.assertTrue(ScheduleUtils.is_fixed_subject("欠"))
        self.assertTrue(ScheduleUtils.is_fixed_subject("YT"))
        self.assertTrue(ScheduleUtils.is_fixed_subject("学"))
        self.assertTrue(ScheduleUtils.is_fixed_subject("道"))
        self.assertTrue(ScheduleUtils.is_fixed_subject("総合"))
        
        # 通常科目
        self.assertFalse(ScheduleUtils.is_fixed_subject("数"))
        self.assertFalse(ScheduleUtils.is_fixed_subject("英"))
        self.assertFalse(ScheduleUtils.is_fixed_subject("国"))
    
    def test_exchange_class_identification(self):
        """交流学級判定のテスト"""
        # 交流学級の判定
        self.assertTrue(ScheduleUtils.is_exchange_class("1年6組"))
        self.assertTrue(ScheduleUtils.is_exchange_class("2年7組"))
        self.assertTrue(ScheduleUtils.is_exchange_class("3年6組"))
        
        # 交流学級でないクラス
        self.assertFalse(ScheduleUtils.is_exchange_class("1年1組"))
        self.assertFalse(ScheduleUtils.is_exchange_class("2年2組"))
    
    def test_is_grade5_class(self):
        """5組判定のテスト"""
        # 5組
        self.assertTrue(ScheduleUtils.is_grade5_class("1年5組"))
        self.assertTrue(ScheduleUtils.is_grade5_class("2年5組"))
        self.assertTrue(ScheduleUtils.is_grade5_class("3年5組"))
        
        # 通常クラス
        self.assertFalse(ScheduleUtils.is_grade5_class("1年1組"))
        self.assertFalse(ScheduleUtils.is_grade5_class("2年2組"))


class TestExceptions(unittest.TestCase):
    """カスタム例外のテスト"""
    
    def test_timetable_generation_error(self):
        """TimetableGenerationErrorのテスト"""
        error = TimetableGenerationError(
            "テストエラー",
            details={'code': 'TEST001'}
        )
        self.assertEqual(error.message, "テストエラー")
        self.assertEqual(error.details['code'], 'TEST001')
    
    def test_constraint_violation_error(self):
        """ConstraintViolationErrorのテスト"""
        violations = [
            {'type': 'teacher_conflict', 'message': '教師重複'},
            {'type': 'daily_duplicate', 'message': '日内重複'}
        ]
        error = ConstraintViolationError(
            "制約違反",
            violations=violations
        )
        self.assertEqual(len(error.violations), 2)
        self.assertEqual(error.violations[0]['type'], 'teacher_conflict')
    
    def test_data_loading_error(self):
        """DataLoadingErrorのテスト"""
        error = DataLoadingError(
            "ファイル読み込みエラー",
            file_path="/path/to/file.csv"
        )
        self.assertEqual(error.file_path, "/path/to/file.csv")


# ScriptUtilitiesのテストは削除（script_utilsが存在しないため）
# 代わりにScheduleUtilsの機能を使用


class TestPerformanceProfiler(unittest.TestCase):
    """パフォーマンスプロファイラーのテスト"""
    
    def test_basic_profiling(self):
        """基本的なプロファイリングのテスト"""
        from src.infrastructure.performance import PerformanceProfiler
        
        profiler = PerformanceProfiler()
        
        # 計測
        with profiler.measure("test_operation", category="test"):
            import time
            time.sleep(0.01)  # 10ms
        
        # レポート取得
        report = profiler.get_report()
        self.assertEqual(len(report['metrics']), 1)
        self.assertGreaterEqual(report['metrics'][0]['duration'], 0.01)
        self.assertEqual(report['metrics'][0]['metadata']['category'], 'test')
    
    def test_nested_profiling(self):
        """ネストしたプロファイリングのテスト"""
        from src.infrastructure.performance import PerformanceProfiler
        
        profiler = PerformanceProfiler()
        
        with profiler.measure("parent"):
            with profiler.measure("child1"):
                pass
            with profiler.measure("child2"):
                pass
        
        report = profiler.get_report()
        parent_metric = report['metrics'][0]
        self.assertEqual(len(parent_metric['sub_metrics']), 2)
        self.assertEqual(parent_metric['sub_metrics'][0]['name'], 'child1')
        self.assertEqual(parent_metric['sub_metrics'][1]['name'], 'child2')


def run_tests():
    """全テストを実行"""
    # テストスイートを作成
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 各テストクラスを追加
    suite.addTests(loader.loadTestsFromTestCase(TestScheduleUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestExceptions))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceProfiler))
    
    # テストを実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)