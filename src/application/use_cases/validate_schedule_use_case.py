"""スケジュール検証ユースケース"""
import logging
from pathlib import Path
from typing import List

from .request_models import ValidateScheduleRequest, ValidateScheduleResult
from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from ...infrastructure.di_container import (
    get_container,
    get_path_manager,
    get_followup_parser,
    get_configuration_reader
)
from ...domain.interfaces.repositories import (
    IScheduleRepository,
    ISchoolRepository
)
from ..services.followup_processor import FollowUpProcessor
from ...infrastructure.parsers.basics_parser import BasicsParser


class ValidateScheduleUseCase:
    """スケジュール検証ユースケース
    
    既存のスケジュールファイルを読み込み、制約違反を検証する
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.path_manager = get_path_manager()
        self.constraint_system = UnifiedConstraintSystem()
        self.followup_processor = FollowUpProcessor()
        
    def execute(self, request: ValidateScheduleRequest) -> ValidateScheduleResult:
        """スケジュールを検証"""
        try:
            # パス設定
            schedule_file = request.data_directory / request.schedule_file
            
            # リポジトリ取得
            container = get_container()
            school_repo = container.resolve(ISchoolRepository)
            schedule_repo = container.resolve(IScheduleRepository)
            
            # 学校データ読み込み
            school = school_repo.load_school_data()
            
            # スケジュール読み込み
            if not schedule_file.exists():
                return ValidateScheduleResult(
                    is_valid=False,
                    violations=[f"Schedule file not found: {schedule_file}"],
                    violations_count=1,
                    message=f"スケジュールファイルが見つかりません: {schedule_file}"
                )
            
            schedule = schedule_repo.load(str(schedule_file))
            
            # Follow-upファイルの処理
            followup_file = request.data_directory / "input" / "Follow-up.csv"
            teacher_absences = {}
            
            if followup_file.exists():
                parser = get_followup_parser()
                
                # 教師不在情報を取得
                parsed_absences = parser.parse_teacher_absences()
                
                # パーサーから取得したデータを変換
                for teacher_name, time_slots in parsed_absences.items():
                    if teacher_name not in teacher_absences:
                        teacher_absences[teacher_name] = []
                    for time_slot in time_slots:
                        teacher_absences[teacher_name].append((time_slot.day, time_slot.period))
                self.logger.info(f"教師不在情報を読み込みました: {len(teacher_absences)}件")
            
            # 制約の登録
            self._register_constraints(request.data_directory, teacher_absences)
            
            # 検証実行
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            
            violations = []
            violations_count = len(validation_result.violations)
            
            for violation in validation_result.violations:
                violations.append({
                    'class': str(violation.assignment.class_ref) if violation.assignment else 'N/A',
                    'day': violation.time_slot.day if violation.time_slot else 'N/A',
                    'period': violation.time_slot.period if violation.time_slot else 0,
                    'subject': violation.assignment.subject if violation.assignment else 'N/A',
                    'constraint': violation.constraint_name or 'Unknown',
                    'message': violation.message or violation.description,
                    'priority': violation.severity or 'ERROR'
                })
            
            # 結果を返す
            is_valid = violations_count == 0
            message = "検証成功: 制約違反はありません" if is_valid else f"検証完了: {violations_count}件の制約違反が見つかりました"
            
            return ValidateScheduleResult(
                is_valid=is_valid,
                violations=violations,
                violations_count=violations_count,
                message=message
            )
            
        except Exception as e:
            self.logger.error(f"スケジュール検証中にエラーが発生しました: {str(e)}")
            return ValidateScheduleResult(
                is_valid=False,
                violations=[f"Validation error: {str(e)}"],
                violations_count=1,
                message=f"検証エラー: {str(e)}"
            )
    
    def _register_constraints(self, data_dir: Path, teacher_absences: dict):
        """制約を登録"""
        # 既存の制約登録ロジックを使用（GenerateScheduleUseCaseから抽出）
        from ...domain.constraints import (
            TeacherAvailabilityConstraint,
            DailySubjectDuplicateConstraint,
            StandardHoursConstraint,
            MondaySixthPeriodConstraint,
            TuesdayPEMultipleConstraint,
            FixedSubjectLockConstraint,
            MeetingLockConstraint,
            TeacherAbsenceConstraint,
            PlacementForbiddenConstraint,
            CellForbiddenSubjectConstraint,
            SubjectValidityConstraint,
            PartTimeTeacherConstraint,
            Grade5SameSubjectConstraint
        )
        from ...domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint
        from ...domain.constraints.gym_usage_constraint import GymUsageConstraintRefactored
        
        # Basics.csvからの制約読み込み
        # 注: BasicConstraintは単なるデータクラスであり、domain constraintとは互換性がないため
        # ここでは読み込むがregister_constraintには渡さない
        # 実際の制約は下記の標準制約で実装されている
        basics_file = data_dir / "config" / "basics.csv"
        if basics_file.exists():
            basics_parser = BasicsParser()
            basic_constraints = basics_parser.parse(str(basics_file))
            # BasicConstraintは情報として保持するが、UnifiedConstraintSystemには登録しない
            self.logger.info(f"Basics.csvから{len(basic_constraints)}個の制約定義を読み込みました")
        
        # 標準制約の登録
        standard_constraints = [
            TeacherConflictConstraint(),
            DailySubjectDuplicateConstraint(),
            StandardHoursConstraint(),
            MondaySixthPeriodConstraint(),
            TuesdayPEMultipleConstraint(),
            FixedSubjectLockConstraint(),
            MeetingLockConstraint(),
            PlacementForbiddenConstraint(forbidden_subjects=['道', '道徳', '学', '学活', '総', '総合', '学総']),
            # CellForbiddenSubjectConstraint は入力データから動的に生成される必要があるため除外
            SubjectValidityConstraint(),
            PartTimeTeacherConstraint(),
            Grade5SameSubjectConstraint(),
            GymUsageConstraintRefactored(),
        ]
        
        for constraint in standard_constraints:
            self.constraint_system.register_constraint(constraint)
        
        # 教師不在制約の登録
        if teacher_absences:
            # TeacherAbsenceConstraintは引数なしで呼び出す（DIコンテナから自動的にリポジトリを取得）
            self.constraint_system.register_constraint(
                TeacherAbsenceConstraint()
            )