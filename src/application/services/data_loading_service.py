"""データローディングサービス - データの読み込みを一元管理"""
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional

from ...domain.entities.school import School
from ...domain.entities.schedule import Schedule
from ...domain.interfaces.repositories import IScheduleRepository, ISchoolRepository
from ...infrastructure.di_container import get_container
from .followup_processor import FollowUpProcessor
from ...infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from ...infrastructure.parsers.followup_parser import FollowUpPromptParser


class DataLoadingService:
    """データ読み込みを管理するサービス
    
    学校データ、スケジュール、Follow-upデータなどの
    読み込みロジックを集約します。
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.container = get_container()
        self.followup_processor = FollowUpProcessor()
        # Get path manager from DI container
        from ...infrastructure.di_container import get_path_manager
        self.path_manager = get_path_manager()
        
    def load_school_data(self, data_dir: Path) -> Tuple[School, bool]:
        """学校データを読み込む
        
        Returns:
            (School, use_enhanced_features): 学校データと拡張機能フラグ
        """
        self.logger.info("学校データを読み込み中...")
        
        school_repo = self.container.resolve(ISchoolRepository)
        school = school_repo.load_school_data()
        
        # 拡張機能の判定（5組が存在するか）
        use_enhanced_features = any("5組" in str(class_ref) for class_ref in school.get_all_classes())
        
        if use_enhanced_features:
            self.logger.info("5組を検出しました - 拡張機能を有効化")
        
        self.logger.info(f"学校データ読み込み完了: {len(school.get_all_classes())}クラス, {len(school.get_all_teachers())}教師")
        
        return school, use_enhanced_features
    
    def load_initial_schedule(
        self, 
        data_dir: Path,
        desired_timetable_file: str,
        start_empty: bool = False,
        validate: bool = True
    ) -> Optional[Schedule]:
        """初期スケジュールを読み込む
        
        Args:
            data_dir: データディレクトリ
            desired_timetable_file: 希望時間割ファイル名
            start_empty: 空のスケジュールから開始するか
            validate: 読み込み時に検証を行うか
            
        Returns:
            初期スケジュール（空から開始の場合はNone）
        """
        if start_empty:
            self.logger.info("空のスケジュールから開始します")
            return None
        
        schedule_repo = self.container.resolve(IScheduleRepository)
        desired_file = data_dir / "input" / desired_timetable_file
        
        if desired_file.exists():
            self.logger.info(f"初期スケジュールを読み込み中: {desired_file}")
            try:
                schedule = schedule_repo.load(str(desired_file))
                assignment_count = len(schedule.get_all_assignments())
                self.logger.info(f"初期スケジュール読み込み完了: {assignment_count}件の割り当て")
                
                # 初期スケジュールの検証を実行
                if validate:
                    self._validate_initial_schedule(schedule, data_dir)
                
                return schedule
            except Exception as e:
                self.logger.warning(f"初期スケジュール読み込みエラー: {e}")
                self.logger.info("空のスケジュールから開始します")
                return None
        else:
            self.logger.info(f"初期スケジュールファイルが見つかりません: {desired_file}")
            self.logger.info("空のスケジュールから開始します")
            return None
    
    def load_weekly_requirements(
        self,
        data_dir: Path,
        school: School,
        schedule: Schedule = None
    ) -> Tuple[dict, Dict[str, list]]:
        """週次要望とFollow-upデータを読み込む
        
        Returns:
            (weekly_requirements, teacher_absences): 週次要望と教師不在情報
        """
        self.logger.info("週次要望とFollow-upデータを読み込み中...")
        
        followup_file = data_dir / "input" / "Follow-up.csv"
        weekly_requirements = {}
        teacher_absences = {}
        
        if not followup_file.exists():
            self.logger.warning(f"Follow-upファイルが見つかりません: {followup_file}")
            return weekly_requirements, teacher_absences
        
        try:
            # 自然言語パーサーを使用
            natural_parser = NaturalFollowUpParser(self.path_manager.input_dir)
            
            result = natural_parser.parse_file("Follow-up.csv")
            
            # 教師不在情報を抽出
            if "teacher_absences" in result:
                # NaturalFollowUpParserはリストを返す
                for absence in result["teacher_absences"]:
                    if hasattr(absence, 'teacher_name'):
                        teacher = absence.teacher_name
                        if teacher not in teacher_absences:
                            teacher_absences[teacher] = []
                        # 終日不在の場合
                        if not absence.periods:
                            for period in range(1, 7):
                                teacher_absences[teacher].append((absence.day, period))
                        else:
                            for period in absence.periods:
                                teacher_absences[teacher].append((absence.day, period))
            
            # その他の週次要望を抽出
            weekly_requirements = {
                'test_periods': result.get('test_periods', []),
                'meeting_changes': result.get('meeting_changes', []),
                'special_requests': result.get('special_requests', [])
            }
            
            self.logger.info(f"週次要望読み込み完了: 教師不在{len(teacher_absences)}件")
            
        except Exception as e:
            self.logger.error(f"Follow-upデータ読み込みエラー: {e}")
            # 旧形式のパーサーにフォールバック
            try:
                self.logger.info("旧形式のパーサーで再試行中...")
                prompt_parser = FollowUpPromptParser(self.path_manager.input_dir)
                requirements = prompt_parser.parse_requirements("Follow-up.csv")
                
                # Extract teacher absences from requirements
                for req in requirements:
                    if req.requirement_type.value in ['教員不在', '教員利用不可']:
                        # Parse teacher absence from requirement
                        # This is a simplified extraction - may need more sophisticated parsing
                        self.logger.info(f"Found teacher absence requirement: {req.content}")
                    
            except Exception as fallback_error:
                self.logger.error(f"フォールバックも失敗: {fallback_error}")
        
        return weekly_requirements, teacher_absences
    
    def get_repositories(self, data_dir: Path) -> Tuple[ISchoolRepository, IScheduleRepository]:
        """リポジトリインスタンスを取得
        
        Returns:
            (school_repo, schedule_repo): 学校とスケジュールのリポジトリ
        """
        return (
            self.container.resolve(ISchoolRepository),
            self.container.resolve(IScheduleRepository)
        )
    
    def _validate_initial_schedule(self, schedule: Schedule, data_dir: Path) -> None:
        """初期スケジュールの制約違反を検証して警告を表示
        
        Args:
            schedule: 検証対象のスケジュール
            data_dir: データディレクトリ
        """
        self.logger.info("=== 初期スケジュールの検証を開始 ===")
        
        try:
            # 学校データを読み込み（検証用）
            school, _ = self.load_school_data(data_dir)
            
            # 統一制約システムを使用して検証
            from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
            from ..services.constraint_registration_service import ConstraintRegistrationService
            
            constraint_system = UnifiedConstraintSystem()
            constraint_service = ConstraintRegistrationService()
            
            # 制約を登録
            constraint_service.register_all_constraints(
                constraint_system,
                data_dir,
                {}  # 教師不在情報は一旦空で
            )
            
            # 検証実行
            validation_result = constraint_system.validate_schedule(schedule, school)
            
            if not validation_result.is_valid:
                violation_count = len(validation_result.violations)
                self.logger.warning(f"⚠️  初期スケジュールに{violation_count}件の制約違反があります")
                
                # 違反の種類別に集計
                violation_types = {}
                for violation in validation_result.violations:
                    violation_type = violation.constraint_name
                    if violation_type not in violation_types:
                        violation_types[violation_type] = 0
                    violation_types[violation_type] += 1
                
                # 違反の概要を表示
                self.logger.warning("【初期スケジュールの制約違反内訳】")
                for vtype, count in sorted(violation_types.items(), key=lambda x: x[1], reverse=True):
                    self.logger.warning(f"  - {vtype}: {count}件")
                
                # 特に重要な違反を詳細表示（最初の5件）
                self.logger.warning("【主な違反の詳細】")
                for i, violation in enumerate(validation_result.violations[:5]):
                    self.logger.warning(f"  {i+1}. {violation.message}")
                
                if violation_count > 5:
                    self.logger.warning(f"  ... 他 {violation_count - 5} 件")
                
                self.logger.warning("=" * 60)
                self.logger.warning("⚠️  注意: 初期スケジュールに違反があるため、")
                self.logger.warning("    生成結果の品質が低下する可能性があります")
                self.logger.warning("=" * 60)
            else:
                self.logger.info("✅ 初期スケジュールの検証完了: 違反なし")
                
        except Exception as e:
            self.logger.error(f"初期スケジュール検証中にエラー: {e}")
            # 検証エラーは警告に留め、処理は継続する