"""データ読み込みユースケース

学校データ、初期スケジュール、週次要望などのデータ読み込みを担当する。
"""
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.interfaces.repositories import (
    IScheduleRepository,
    ISchoolRepository,
    ITeacherAbsenceRepository
)
from ...domain.interfaces.followup_parser import IFollowUpParser
from ...application.services.input_data_corrector import InputDataCorrector
from ...infrastructure.di_container import get_input_preprocessor


class DataLoadingUseCase:
    """データ読み込みユースケース
    
    責任：
    - 学校データの読み込み
    - 初期スケジュールの読み込み
    - 週次要望の解析
    - 入力データの前処理
    """
    
    def __init__(
        self,
        school_repository: ISchoolRepository,
        schedule_repository: IScheduleRepository,
        followup_parser: IFollowUpParser,
        teacher_absence_repository: ITeacherAbsenceRepository,
        data_dir: Path
    ):
        """初期化
        
        Args:
            school_repository: 学校データリポジトリ
            schedule_repository: スケジュールリポジトリ
            followup_parser: Follow-upパーサー
            teacher_absence_repository: 教師不在情報リポジトリ
            data_dir: データディレクトリ
        """
        self.school_repository = school_repository
        self.schedule_repository = schedule_repository
        self.followup_parser = followup_parser
        self.teacher_absence_repository = teacher_absence_repository
        self.data_dir = data_dir
        self.logger = logging.getLogger(__name__)
        
        # データ前処理
        self.preprocessor = get_input_preprocessor()
        self.data_corrector = InputDataCorrector()
    
    def execute(self) -> Tuple[School, Schedule, Dict, Dict]:
        """データ読み込みを実行
        
        Returns:
            Tuple[School, Schedule, Dict, Dict]: 学校データ、初期スケジュール、週次要望データ、配置禁止セル
        """
        # 入力データの前処理
        self._preprocess_input_files()
        
        # 学校データの読み込み
        self.logger.info("学校データを読み込み中...")
        school = self.school_repository.load_school_data("base_timetable.csv")
        
        # 初期スケジュールの読み込み
        self.logger.info("初期スケジュールを読み込み中...")
        schedule = self.schedule_repository.load("input/input.csv", school)
        
        # 配置禁止セル（非保・非数・非理）の取得
        forbidden_cells = self.schedule_repository.get_forbidden_cells()
        if forbidden_cells:
            self.logger.info(f"配置禁止セルを{len(forbidden_cells)}件読み込みました")
            for (time_slot, class_ref), subjects in list(forbidden_cells.items())[:3]:
                self.logger.debug(f"  例: {class_ref} {time_slot} - {subjects}")
        else:
            self.logger.warning("配置禁止セルが読み込まれませんでした")
        
        # 入力データの補正
        self.logger.info("入力データを補正中...")
        corrected_count = self.data_corrector.correct_input_data(schedule, school)
        if corrected_count > 0:
            self.logger.info(f"入力データ補正完了: {corrected_count}項目を補正")
        
        # 週次要望の解析
        self.logger.info("週次要望を解析中...")
        followup_data = self._parse_followup_data()
        
        # 教師不在情報の更新
        if followup_data.get("parse_success") and followup_data.get("teacher_absences"):
            self.teacher_absence_repository.update_absences_from_parsed_data(
                followup_data["teacher_absences"]
            )
        
        return school, schedule, followup_data, forbidden_cells
    
    def _preprocess_input_files(self) -> None:
        """入力ファイルの前処理"""
        input_files = [
            self.data_dir / "input" / "input.csv",
            self.data_dir / "input" / "Follow-up.csv"
        ]
        
        for file_path in input_files:
            if file_path.exists():
                self.preprocessor.preprocess_file(file_path)
    
    def _parse_followup_data(self) -> Dict:
        """Follow-upデータの解析"""
        followup_path = self.data_dir / "input" / "Follow-up.csv"
        
        if not followup_path.exists():
            self.logger.warning("Follow-up.csvが見つかりません")
            return {"parse_success": False}
        
        try:
            return self.followup_parser.parse_file("Follow-up.csv")
        except Exception as e:
            self.logger.error(f"Follow-up解析エラー: {e}")
            return {"parse_success": False}