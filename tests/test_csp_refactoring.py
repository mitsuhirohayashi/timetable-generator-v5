"""CSPオーケストレーターのテスト"""
import unittest
from pathlib import Path
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain.services.csp_orchestrator import CSPOrchestrator
from src.domain.constraints.base import ConstraintValidator
from src.infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfigLoader
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.config.path_config import path_config


class TestCSPOrchestrator(unittest.TestCase):
    """CSPオーケストレーターの動作を確認"""
    
    def setUp(self):
        """テスト環境のセットアップ"""
        # 設定を読み込み
        config_loader = AdvancedCSPConfigLoader()
        self.config = config_loader.load()
        
        # 制約バリデーターを作成（空のリストで初期化）
        self.constraint_validator = ConstraintValidator([])
        
        # 学校データを読み込み
        school_repo = CSVSchoolRepository(path_config.config_dir)
        self.school = school_repo.load_school_data("base_timetable.csv")
        
        # CSPオーケストレーターを作成
        self.orchestrator = CSPOrchestrator(
            self.constraint_validator, self.config
        )
    
    def test_interface(self):
        """インターフェースを確認"""
        # オーケストレーターが必要なメソッドを持つことを確認
        self.assertTrue(hasattr(self.orchestrator, 'generate'))
        
        # 内部サービスが作成されていることを確認
        self.assertTrue(hasattr(self.orchestrator, 'jiritsu_service'))
        self.assertTrue(hasattr(self.orchestrator, 'grade5_service'))
        self.assertTrue(hasattr(self.orchestrator, 'regular_service'))
        self.assertTrue(hasattr(self.orchestrator, 'optimizer'))
        self.assertTrue(hasattr(self.orchestrator, 'evaluator'))
    
    def test_generation_results(self):
        """生成結果が妥当であることを確認"""
        # CSPオーケストレーターで生成
        schedule = self.orchestrator.generate(self.school, max_iterations=10)
        
        # 基本的な検証
        self.assertIsNotNone(schedule)
        assignments = list(schedule.get_all_assignments())
        self.assertGreater(len(assignments), 0)
        
        # 制約違反が少ないことを確認
        violations = self.constraint_validator.validate_all(schedule, self.school)
        self.assertLess(len(violations), 10)  # 違反が10個未満


class TestServiceIsolation(unittest.TestCase):
    """各サービスが独立して動作することを確認"""
    
    def setUp(self):
        """テスト環境のセットアップ"""
        from src.domain.services.implementations.backtrack_jiritsu_placement_service import BacktrackJiritsuPlacementService
        from src.domain.services.implementations.synchronized_grade5_service import SynchronizedGrade5Service
        from src.domain.services.implementations.greedy_subject_placement_service import GreedySubjectPlacementService
        from src.domain.services.implementations.weighted_schedule_evaluator import WeightedScheduleEvaluator
        
        # 設定とバリデーターを作成
        config_loader = AdvancedCSPConfigLoader()
        self.config = config_loader.load()
        self.constraint_validator = ConstraintValidator([])
        
        # 各サービスを作成
        self.jiritsu_service = BacktrackJiritsuPlacementService(self.config, self.constraint_validator)
        self.grade5_service = SynchronizedGrade5Service(self.config, self.constraint_validator)
        self.regular_service = GreedySubjectPlacementService(self.config, self.constraint_validator)
        self.evaluator = WeightedScheduleEvaluator(self.config, self.constraint_validator)
        
        # テスト用の学校データ
        school_repo = CSVSchoolRepository(path_config.config_dir)
        self.school = school_repo.load_school_data("base_timetable.csv")
    
    def test_jiritsu_service_isolation(self):
        """自立活動配置サービスの独立性"""
        from src.domain.entities.schedule import Schedule
        
        schedule = Schedule()
        requirements = self.jiritsu_service.analyze_requirements(self.school, schedule)
        
        # 要件が正しく分析されることを確認
        self.assertIsInstance(requirements, list)
        # 交流学級の数だけ要件があるはず
        self.assertGreater(len(requirements), 0)
    
    def test_grade5_service_isolation(self):
        """5組同期サービスの独立性"""
        from src.domain.entities.schedule import Schedule
        
        schedule = Schedule()
        common_subjects = self.grade5_service.get_common_subjects(
            self.school, self.config.grade5_classes
        )
        
        # 共通教科が正しく取得されることを確認
        self.assertIsInstance(common_subjects, dict)
        self.assertGreater(len(common_subjects), 0)
    
    def test_evaluator_isolation(self):
        """評価サービスの独立性"""
        from src.domain.entities.schedule import Schedule
        
        schedule = Schedule()
        score = self.evaluator.evaluate(schedule, self.school, [])
        
        # スコアが計算されることを確認
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        
        # 内訳も取得できることを確認
        breakdown = self.evaluator.evaluate_with_breakdown(schedule, self.school, [])
        self.assertIsNotNone(breakdown.details)
        self.assertEqual(breakdown.total_score, score)


if __name__ == '__main__':
    unittest.main()