"""教師不在情報を事前に読み込むローダー"""
from typing import Dict, Set, List, Tuple
from pathlib import Path

from ...shared.mixins.logging_mixin import LoggingMixin


class TeacherAbsenceLoader(LoggingMixin):
    """Follow-up.csvから教師不在情報を読み込む"""
    
    def __init__(self, absences=None):
        super().__init__()
        # 外部から不在情報を注入できるように変更
        if absences is not None:
            self.absences = absences
        else:
            self.absences = self._load_default_absences()
        # 恒久的休み情報を統合（実際の不在情報はFollow-up.csvから読み取るため無効化）
        # self._integrate_permanent_absences()
    
    def _load_default_absences(self) -> Dict[str, Dict]:
        """デフォルトの不在情報（互換性のため空のデータを返す）"""
        # 実際の不在情報はFollow-up.csvから読み取るため、空のデータを返す
        return {
            '月': {'all_day': [], 'periods': {}},
            '火': {'all_day': [], 'periods': {}},
            '水': {'all_day': [], 'periods': {}},
            '木': {'all_day': [], 'periods': {}},
            '金': {'all_day': [], 'periods': {}}
        }
    
    def is_teacher_absent(self, teacher: str, day: str, period: int) -> bool:
        """指定された時間帯に教師が不在かチェック"""
        if day not in self.absences:
            return False
        
        day_absences = self.absences[day]
        
        # 終日不在チェック
        if teacher in day_absences['all_day']:
            self.logger.debug(f"{teacher}先生は{day}終日不在")
            return True
        
        # 時限別不在チェック
        if period in day_absences['periods']:
            if teacher in day_absences['periods'][period]:
                self.logger.debug(f"{teacher}先生は{day}{period}限不在")
                return True
        
        return False
    
    def get_absent_teachers(self, day: str, period: int) -> Set[str]:
        """指定された時間帯の不在教師のセットを返す"""
        absent = set()
        
        if day not in self.absences:
            return absent
        
        day_absences = self.absences[day]
        
        # 終日不在の教師
        absent.update(day_absences['all_day'])
        
        # 時限別不在の教師
        if period in day_absences['periods']:
            absent.update(day_absences['periods'][period])
        
        return absent
    
    def get_all_absences(self) -> Dict[str, Dict]:
        """全ての不在情報を返す"""
        return self.absences
    
    def update_absences_from_parsed_data(self, teacher_absences: List) -> None:
        """パースされた不在情報でデータを更新"""
        # 既存のデータをクリア
        for day in self.absences:
            self.absences[day]['all_day'] = []
            self.absences[day]['periods'] = {}
        
        # 引数の型をチェックしてログ出力
        self.logger.debug(f"teacher_absences type: {type(teacher_absences)}")
        if isinstance(teacher_absences, dict):
            # 辞書形式の場合: {teacher: [(day, period), ...]}
            for teacher, absences in teacher_absences.items():
                for day, period in absences:
                    if day not in self.absences:
                        self.absences[day] = {'all_day': [], 'periods': {}}
                    if period not in self.absences[day]['periods']:
                        self.absences[day]['periods'][period] = []
                    if teacher not in self.absences[day]['periods'][period]:
                        self.absences[day]['periods'][period].append(teacher)
                        self.logger.info(f"不在情報を更新: {teacher} - {day}{period}限")
            return
        
        # リスト形式の場合（既存のロジック）
        # パースされたデータから不在情報を構築
        for absence in teacher_absences:
            # dictとオブジェクトの両方に対応
            if isinstance(absence, dict):
                day = absence.get('day')
                teacher_name = absence.get('teacher')
                period = absence.get('period')
                reason = absence.get('reason', '')
            else:
                day = absence.day
                teacher_name = absence.teacher_name
                periods = getattr(absence, 'periods', None)  # periods（複数形）フィールド
                reason = getattr(absence, 'reason', '')
            
            if day not in self.absences:
                self.absences[day] = {'all_day': [], 'periods': {}}
            
            if not periods:  # 終日不在（空リストまたはNone）
                if teacher_name not in self.absences[day]['all_day']:
                    self.absences[day]['all_day'].append(teacher_name)
                    self.logger.info(f"不在情報を更新: {teacher_name} - {day}終日 ({reason})")
            else:  # 時限別不在
                for period in periods:
                    if period not in self.absences[day]['periods']:
                        self.absences[day]['periods'][period] = []
                    if teacher_name not in self.absences[day]['periods'][period]:
                        self.absences[day]['periods'][period].append(teacher_name)
                        self.logger.info(f"不在情報を更新: {teacher_name} - {day}{period}限 ({reason})")
    
    @property
    def teacher_absences(self) -> Dict[str, Set[Tuple[str, int]]]:
        """ConstraintValidatorが期待する形式で教師不在情報を提供
        
        Returns:
            Dict[str, Set[Tuple[str, int]]]: 教師名 -> (曜日, 時限)のセット
        """
        result = {}
        for day, day_absences in self.absences.items():
            # 終日不在
            for teacher in day_absences.get('all_day', []):
                if teacher not in result:
                    result[teacher] = set()
                for period in range(1, 7):
                    result[teacher].add((day, period))
            # 時限別不在
            for period, teachers in day_absences.get('periods', {}).items():
                for teacher in teachers:
                    if teacher not in result:
                        result[teacher] = set()
                    result[teacher].add((day, period))
        return result
    
    def _integrate_permanent_absences(self):
        """恒久的休み情報を統合"""
        from ..config.path_config import path_config
        from .teacher_mapping_repository import TeacherMappingRepository
        
        try:
            # 教師マッピングリポジトリから恒久的休み情報を取得
            teacher_mapping_repo = TeacherMappingRepository(path_config.config_dir)
            teacher_mapping_repo.load_teacher_mapping("teacher_subject_mapping.csv")  # ロードして恒久的休み情報を取得
            permanent_absences = teacher_mapping_repo.get_permanent_absences()
            
            # 恒久的休み情報を統合
            for teacher_name, absences in permanent_absences.items():
                for day, absence_type in absences:
                    if absence_type == '終日':
                        # 終日不在の場合
                        if day not in self.absences:
                            self.absences[day] = {'all_day': [], 'periods': {}}
                        if teacher_name not in self.absences[day]['all_day']:
                            self.absences[day]['all_day'].append(teacher_name)
                            self.logger.info(f"恒久的休みを統合: {teacher_name} - {day}終日")
                    elif absence_type == '午後':
                        # 午後不在の場合
                        if day not in self.absences:
                            self.absences[day] = {'all_day': [], 'periods': {}}
                        for period in [4, 5, 6]:
                            if period not in self.absences[day]['periods']:
                                self.absences[day]['periods'][period] = []
                            if teacher_name not in self.absences[day]['periods'][period]:
                                self.absences[day]['periods'][period].append(teacher_name)
                        self.logger.info(f"恒久的休みを統合: {teacher_name} - {day}午後")
        except Exception as e:
            self.logger.warning(f"恒久的休み情報の統合に失敗: {e}")