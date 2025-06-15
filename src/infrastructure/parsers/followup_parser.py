"""Follow-up.csv解析パーサー"""
import csv
import logging
from pathlib import Path
from typing import List, Optional

from ...domain.value_objects.weekly_requirement import (
    WeeklyRequirement, RequirementType, Priority
)


class FollowUpPromptParser:
    """Follow-up.csvファイルの解析を担当"""
    
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
    
    def parse_requirements(self, filename: str = "Follow-up.csv") -> List[WeeklyRequirement]:
        """Follow-up.csvから週次要望を解析"""
        file_path = self.base_path / filename
        requirements = []
        
        if not file_path.exists():
            self.logger.warning(f"Follow-up prompt file not found: {file_path}")
            return requirements
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, 2):  # ヘッダー行を除いて2行目から
                    try:
                        requirement = self._parse_requirement_row(row)
                        if requirement:
                            requirements.append(requirement)
                            self.logger.debug(f"要望読み込み: {requirement}")
                    except Exception as e:
                        self.logger.warning(f"行{row_num}の解析に失敗: {e}")
                        continue
            
            self.logger.info(f"週次要望を読み込みました: {len(requirements)}件 from {file_path}")
            return requirements
            
        except Exception as e:
            self.logger.error(f"Follow-up prompt読み込みエラー: {e}")
            return requirements
    
    def _parse_requirement_row(self, row: dict) -> Optional[WeeklyRequirement]:
        """CSVの1行から要望オブジェクトを作成"""
        try:
            # 必須フィールドの検証
            required_fields = ['要望タイプ', '対象', '条件', '内容', '優先度']
            for field in required_fields:
                if field not in row or not row[field].strip():
                    self.logger.warning(f"必須フィールドが空です: {field}")
                    return None
            
            # 要望タイプの解析
            req_type_str = row['要望タイプ'].strip()
            requirement_type = None
            for req_type in RequirementType:
                if req_type.value == req_type_str:
                    requirement_type = req_type
                    break
            
            if not requirement_type:
                self.logger.warning(f"不明な要望タイプ: {req_type_str}")
                return None
            
            # 優先度の解析
            priority_str = row['優先度'].strip()
            priority = None
            for prio in Priority:
                if prio.value == priority_str:
                    priority = prio
                    break
            
            if not priority:
                self.logger.warning(f"不明な優先度: {priority_str}")
                priority = Priority.MEDIUM  # デフォルト
            
            return WeeklyRequirement(
                requirement_type=requirement_type,
                target=row['対象'].strip(),
                condition=row['条件'].strip(), 
                content=row['内容'].strip(),
                priority=priority,
                note=row.get('備考', '').strip()
            )
            
        except Exception as e:
            self.logger.error(f"要望行の解析エラー: {e}")
            return None
    
    def group_requirements_by_type(self, requirements: List[WeeklyRequirement]) -> dict:
        """要望をタイプ別にグループ化"""
        grouped = {}
        for req in requirements:
            req_type = req.requirement_type
            if req_type not in grouped:
                grouped[req_type] = []
            grouped[req_type].append(req)
        
        return grouped
    
    def get_high_priority_requirements(self, requirements: List[WeeklyRequirement]) -> List[WeeklyRequirement]:
        """高優先度の要望のみを抽出"""
        return [req for req in requirements if req.priority == Priority.HIGH]
    
    def validate_requirements(self, requirements: List[WeeklyRequirement]) -> List[str]:
        """要望の妥当性を検証"""
        errors = []
        
        for req in requirements:
            # 矛盾する要望の検出
            if req.requirement_type in [RequirementType.TEACHER_UNAVAILABLE, RequirementType.TEACHER_UNAVAILABLE_ALT]:
                if "利用不可" not in req.content and "不在" not in req.content:
                    errors.append(f"教員不在要望の内容が不正: {req}")
            
            elif req.requirement_type == RequirementType.HOURS_ADJUSTMENT:
                if not any(op in req.content for op in ['+', '-']):
                    errors.append(f"時間増減要望の内容が不正: {req}")
        
        return errors