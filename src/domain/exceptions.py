"""時間割生成システムのカスタム例外定義

エラーハンドリングを改善するための専用例外クラス群
"""


class TimetableGenerationError(Exception):
    """時間割生成の基底例外クラス"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConstraintViolationError(TimetableGenerationError):
    """制約違反が解決できない場合の例外"""
    def __init__(self, message: str, violations: list = None, details: dict = None):
        super().__init__(message, details)
        self.violations = violations or []


class DataLoadingError(TimetableGenerationError):
    """データ読み込み失敗時の例外"""
    def __init__(self, message: str, file_path: str = None, details: dict = None):
        super().__init__(message, details)
        self.file_path = file_path


class ConfigurationError(TimetableGenerationError):
    """設定が無効な場合の例外"""
    def __init__(self, message: str, config_key: str = None, details: dict = None):
        super().__init__(message, details)
        self.config_key = config_key


class ScheduleAssignmentError(TimetableGenerationError):
    """スケジュール割り当て失敗時の例外"""
    def __init__(self, message: str, time_slot=None, class_ref=None, subject=None, details: dict = None):
        super().__init__(message, details)
        self.time_slot = time_slot
        self.class_ref = class_ref
        self.subject = subject


class PhaseExecutionError(TimetableGenerationError):
    """生成フェーズ実行失敗時の例外"""
    def __init__(self, message: str, phase_name: str = None, details: dict = None):
        super().__init__(message, details)
        self.phase_name = phase_name


class ResourceConflictError(TimetableGenerationError):
    """リソース競合時の例外（教師重複、体育館使用など）"""
    def __init__(self, message: str, resource_type: str = None, conflicting_classes: list = None, details: dict = None):
        super().__init__(message, details)
        self.resource_type = resource_type
        self.conflicting_classes = conflicting_classes or []


class SubjectAssignmentException(TimetableGenerationError):
    """科目割り当てエラー"""
    pass


class FixedSubjectModificationException(TimetableGenerationError):
    """固定科目変更エラー"""
    pass


class InvalidAssignmentException(TimetableGenerationError):
    """無効な割り当てエラー"""
    pass