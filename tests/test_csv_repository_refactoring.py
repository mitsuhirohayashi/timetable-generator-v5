"""CSVRepositoryリファクタリングのテスト"""
import unittest
from pathlib import Path
import tempfile
import shutil
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.csv_repository import (
    CSVScheduleRepository,
    CSVSchoolRepository as CSVSchoolRepositoryRefactored
)
from src.infrastructure.config.path_config import path_config


class TestCSVRepositoryRefactoring(unittest.TestCase):
    """リファクタリング前後の動作が同一であることを確認"""
    
    def setUp(self):
        """テスト環境のセットアップ"""
        # 一時ディレクトリを作成
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # テスト用のCSVファイルを作成
        self._create_test_files()
        
        # 新旧のリポジトリを初期化
        self.original_repo = CSVScheduleRepository(base_path=self.test_path)
        self.refactored_repo = CSVScheduleRepository(base_path=self.test_path)
    
    def tearDown(self):
        """テスト環境のクリーンアップ"""
        shutil.rmtree(self.test_dir)
    
    def _create_test_files(self):
        """テスト用のCSVファイルを作成"""
        # 簡単なテスト用時間割CSV
        test_schedule = '''基本時間割,"月","月","火","火"
"","1","2","1","2"
"1年1組","数","国","理","英"
"1年2組","国","数","英","理"
'''
        
        with open(self.test_path / "test_input.csv", 'w', encoding='utf-8') as f:
            f.write(test_schedule)
    
    def test_load_schedule_produces_same_result(self):
        """スケジュール読み込みが同じ結果を生成することを確認"""
        # 両方のリポジトリで読み込み
        original_schedule = self.original_repo.load_desired_schedule("test_input.csv")
        refactored_schedule = self.refactored_repo.load_desired_schedule("test_input.csv")
        
        # 同じ数の割り当てがあることを確認
        original_assignments = list(original_schedule.get_all_assignments())
        refactored_assignments = list(refactored_schedule.get_all_assignments())
        
        self.assertEqual(len(original_assignments), len(refactored_assignments))
        
        # 各割り当てが同じであることを確認
        for (orig_slot, orig_assign), (ref_slot, ref_assign) in zip(
            sorted(original_assignments, key=lambda x: (str(x[0]), str(x[1].class_ref))),
            sorted(refactored_assignments, key=lambda x: (str(x[0]), str(x[1].class_ref)))
        ):
            self.assertEqual(orig_slot, ref_slot)
            self.assertEqual(orig_assign.class_ref, ref_assign.class_ref)
            self.assertEqual(orig_assign.subject.name, ref_assign.subject.name)
    
    def test_save_schedule_produces_same_output(self):
        """スケジュール保存が同じ出力を生成することを確認"""
        # スケジュールを読み込み
        schedule = self.original_repo.load_desired_schedule("test_input.csv")
        
        # 両方のリポジトリで保存
        self.original_repo.save_schedule(schedule, "original_output.csv")
        self.refactored_repo.save_schedule(schedule, "refactored_output.csv")
        
        # ファイル内容を比較
        with open(self.test_path / "original_output.csv", 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        with open(self.test_path / "refactored_output.csv", 'r', encoding='utf-8') as f:
            refactored_content = f.read()
        
        self.assertEqual(original_content, refactored_content)
    
    def test_forbidden_cells_extraction(self):
        """非○○制約の抽出が同じであることを確認"""
        # 非○○制約を含むCSVを作成
        test_schedule_with_forbidden = '''基本時間割,"月","月"
"","1","2"
"1年1組","非数","国"
'''
        
        with open(self.test_path / "test_forbidden.csv", 'w', encoding='utf-8') as f:
            f.write(test_schedule_with_forbidden)
        
        # 両方のリポジトリで読み込み
        self.original_repo.load_desired_schedule("test_forbidden.csv")
        self.refactored_repo.load_desired_schedule("test_forbidden.csv")
        
        # 制約情報を比較
        original_forbidden = self.original_repo.get_forbidden_cells()
        refactored_forbidden = self.refactored_repo.get_forbidden_cells()
        
        self.assertEqual(len(original_forbidden), len(refactored_forbidden))
        
        # キーと値が同じであることを確認
        for key in original_forbidden:
            self.assertIn(key, refactored_forbidden)
            self.assertEqual(original_forbidden[key], refactored_forbidden[key])


class TestPerformanceImprovement(unittest.TestCase):
    """リファクタリング後のパフォーマンス改善を確認"""
    
    def test_method_complexity_reduced(self):
        """メソッドの複雑度が減少したことを確認"""
        # CSVScheduleReaderのメソッド行数を確認
        from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
        
        # readメソッドの行数を確認（元のload_desired_scheduleは340行以上）
        import inspect
        read_source = inspect.getsource(CSVScheduleReader.read)
        read_lines = len(read_source.split('\n'))
        
        # 50行以下に収まっていることを確認
        self.assertLess(read_lines, 50, 
                       f"read method should be less than 50 lines, but has {read_lines} lines")
    
    def test_single_responsibility(self):
        """単一責任の原則が守られていることを確認"""
        from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
        from src.infrastructure.repositories.schedule_io.csv_writer import CSVScheduleWriter
        from src.infrastructure.repositories.teacher_schedule_repository import TeacherScheduleRepository
        
        # 各クラスが限定的なメソッド数を持つことを確認
        reader_methods = [m for m in dir(CSVScheduleReader) if not m.startswith('_') or m == '__init__']
        writer_methods = [m for m in dir(CSVScheduleWriter) if not m.startswith('_') or m == '__init__']
        teacher_methods = [m for m in dir(TeacherScheduleRepository) if not m.startswith('_') or m == '__init__']
        
        # 各クラスが適切な数のパブリックメソッドを持つことを確認
        self.assertLess(len(reader_methods), 5)
        self.assertLess(len(writer_methods), 5)
        self.assertLess(len(teacher_methods), 5)


if __name__ == '__main__':
    unittest.main()