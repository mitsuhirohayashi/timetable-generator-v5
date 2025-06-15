"""リファクタリング版CSVScheduleRepository - ファサードパターンで各責務を統合"""
import logging
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.value_objects.time_slot import TimeSlot, ClassReference
from ..config.path_config import path_config
from .schedule_io.csv_reader import CSVScheduleReader
from .schedule_io.csv_writer import CSVScheduleWriter
from .teacher_schedule_repository import TeacherScheduleRepository
from ..services.schedule_synchronization_service import ScheduleSynchronizationService
from ..services.schedule_validation_service import ScheduleValidationService
from .teacher_absence_loader import TeacherAbsenceLoader


class CSVScheduleRepositoryRefactored:
    """リファクタリング版スケジュールリポジトリ - 各責務を専門クラスに委譲"""
    
    def __init__(
        self,
        base_path: Path = Path("."),
        use_enhanced_features: bool = False,
        use_support_hours: bool = False
    ):
        """初期化
        
        Args:
            base_path: ベースパス
            use_enhanced_features: 拡張機能を使用するか
            use_support_hours: 特別支援時数表記を使用するか
        """
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        self.use_enhanced_features = use_enhanced_features
        self.use_support_hours = use_support_hours
        
        # 責務ごとのコンポーネントを初期化
        self.reader = CSVScheduleReader()
        self.writer = CSVScheduleWriter(use_support_hours)
        self.teacher_schedule_repo = TeacherScheduleRepository(use_enhanced_features)
        self.absence_loader = TeacherAbsenceLoader()
        self.sync_service = ScheduleSynchronizationService(
            self.absence_loader.is_teacher_absent
        )
        self.validation_service = ScheduleValidationService(self.absence_loader)
        
        # 読み込んだ制約情報
        self._forbidden_cells = {}
    
    def save_schedule(self, schedule: Schedule, filename: str = "output.csv") -> None:
        """スケジュールをCSVファイルに保存"""
        file_path = self._resolve_output_path(filename)
        self.writer.write(schedule, file_path)
    
    def load_desired_schedule(
        self,
        filename: str = "input.csv",
        school: Optional[School] = None
    ) -> Schedule:
        """希望時間割をCSVファイルから読み込み"""
        file_path = self._resolve_input_path(filename)
        
        # 基本的な読み込み
        schedule = self.reader.read(file_path, school)
        
        # 制約情報を保存
        self._forbidden_cells = self.reader.get_forbidden_cells()
        
        if school:
            # Grade5Unitに教師不在チェッカーを設定
            schedule.grade5_unit.set_teacher_absence_checker(
                self.absence_loader.is_teacher_absent
            )
            
            # 初期同期処理
            self.sync_service.synchronize_initial_schedule(
                schedule, school, self._forbidden_cells
            )
            
            # 制約違反の検証と修正
            self.validation_service.validate_and_fix_schedule(
                schedule, school, self._forbidden_cells
            )
        
        return schedule
    
    def save_teacher_schedule(
        self,
        schedule: Schedule,
        school: School,
        filename: str = "teacher_schedule.csv"
    ) -> None:
        """教師別時間割をCSVファイルに保存"""
        self.teacher_schedule_repo.save_teacher_schedule(
            schedule, school, filename
        )
    
    def get_forbidden_cells(self) -> Dict[Tuple[TimeSlot, ClassReference], Set[str]]:
        """読み込んだCSVファイルから抽出した非○○制約を取得"""
        return self._forbidden_cells
    
    def _resolve_output_path(self, filename: str) -> Path:
        """出力ファイルパスを解決"""
        if filename.startswith("/"):
            return Path(filename)
        elif str(path_config.output_dir) in filename:
            return Path(filename)
        elif filename.startswith("data/"):
            return path_config.base_dir / filename
        elif filename == "output.csv":
            return path_config.default_output_csv
        else:
            return path_config.get_output_path(filename)
    
    def _resolve_input_path(self, filename: str) -> Path:
        """入力ファイルパスを解決"""
        if filename.startswith("/"):
            return Path(filename)
        elif filename.startswith("data/"):
            if str(self.base_path).endswith("/data") or str(self.base_path) == "data":
                return self.base_path.parent / filename
            else:
                return Path(filename)
        else:
            return self.base_path / filename


class CSVSchoolRepository:
    """学校データのCSV入出力を担当（既存のまま）"""
    
    def __init__(self, base_path: Path = Path(".")):
        from .csv_repository import CSVSchoolRepository as OriginalRepo
        self._original = OriginalRepo(base_path)
    
    def load_standard_hours(self, filename: str = "base_timetable.csv"):
        """標準時数データをCSVから読み込み"""
        return self._original.load_standard_hours(filename)
    
    def load_school_data(self, base_timetable_file: str = "base_timetable.csv"):
        """学校の基本データを読み込んでSchoolエンティティを構築"""
        return self._original.load_school_data(base_timetable_file)