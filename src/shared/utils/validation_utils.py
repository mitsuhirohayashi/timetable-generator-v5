"""バリデーションの共通ユーティリティ

各種バリデーション処理の共通実装を提供します。
"""
import re
from typing import Any, Optional, List, Dict, Union, Callable
from datetime import datetime


class ValidationUtils:
    """バリデーションユーティリティ"""
    
    # 固定科目のセット
    FIXED_SUBJECTS = {"欠", "YT", "道", "学", "総", "学総", "行", "テスト", "技家"}
    
    # 有効な曜日
    VALID_DAYS = ["月", "火", "水", "木", "金"]
    
    # 有効な時限
    VALID_PERIODS = list(range(1, 7))
    
    @staticmethod
    def is_fixed_subject(subject_name: str) -> bool:
        """固定科目かどうかを判定
        
        Args:
            subject_name: 科目名
            
        Returns:
            固定科目の場合True
        """
        return subject_name in ValidationUtils.FIXED_SUBJECTS
    
    @staticmethod
    def is_valid_day(day: str) -> bool:
        """有効な曜日かどうかを判定
        
        Args:
            day: 曜日
            
        Returns:
            有効な曜日の場合True
        """
        return day in ValidationUtils.VALID_DAYS
    
    @staticmethod
    def is_valid_period(period: int) -> bool:
        """有効な時限かどうかを判定
        
        Args:
            period: 時限
            
        Returns:
            有効な時限の場合True
        """
        return period in ValidationUtils.VALID_PERIODS
    
    @staticmethod
    def is_valid_class_reference(grade: int, class_number: int) -> bool:
        """有効なクラス参照かどうかを判定
        
        Args:
            grade: 学年
            class_number: クラス番号
            
        Returns:
            有効なクラス参照の場合True
        """
        # 通常学級
        if 1 <= grade <= 3 and 1 <= class_number <= 3:
            return True
        
        # 5組（特別支援学級）
        if 1 <= grade <= 3 and class_number == 5:
            return True
        
        # 交流学級（6組、7組）
        if 1 <= grade <= 3 and class_number in [6, 7]:
            return True
        
        return False
    
    @staticmethod
    def normalize_subject_name(subject_name: str) -> str:
        """科目名を正規化
        
        Args:
            subject_name: 科目名
            
        Returns:
            正規化された科目名
        """
        # 前後の空白を削除
        subject_name = subject_name.strip()
        
        # 科目名の正規化マッピング
        normalization_map = {
            "国語": "国",
            "算数": "数",
            "数学": "数",
            "英語": "英",
            "理科": "理",
            "社会": "社",
            "音楽": "音",
            "美術": "美",
            "保健体育": "保",
            "体育": "保",
            "技術": "技",
            "家庭": "家",
            "技術・家庭": "技家",
            "道徳": "道",
            "総合": "総",
            "総合的な学習の時間": "総",
            "学活": "学",
            "学級活動": "学",
            "学年総合": "学総",
            "特別活動": "YT",
            "自立活動": "自立",
            "日常生活": "日生",
            "作業学習": "作業",
            "行事": "行",
            "欠課": "欠"
        }
        
        # 正規化
        for long_name, short_name in normalization_map.items():
            if subject_name == long_name:
                return short_name
        
        return subject_name
    
    @staticmethod
    def validate_teacher_name(teacher_name: str) -> bool:
        """教師名が有効かどうかを判定
        
        Args:
            teacher_name: 教師名
            
        Returns:
            有効な教師名の場合True
        """
        if not teacher_name or not teacher_name.strip():
            return False
        
        # 特殊な教師名（システム用）
        system_teachers = {
            "欠", "YT担当", "道担当", "学担当", 
            "総担当", "学総担当", "行担当", "欠課先生"
        }
        
        if teacher_name in system_teachers:
            return True
        
        # 通常の教師名（日本語の名前を想定）
        # 最低1文字以上、漢字・ひらがな・カタカナ・英数字を含む
        pattern = r'^[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\w\s]+$'
        return bool(re.match(pattern, teacher_name)) and len(teacher_name) >= 1
    
    @staticmethod
    def validate_time_range(
        start_day: str,
        start_period: int,
        end_day: str,
        end_period: int
    ) -> bool:
        """時間範囲が有効かどうかを判定
        
        Args:
            start_day: 開始曜日
            start_period: 開始時限
            end_day: 終了曜日
            end_period: 終了時限
            
        Returns:
            有効な時間範囲の場合True
        """
        if not ValidationUtils.is_valid_day(start_day):
            return False
        if not ValidationUtils.is_valid_day(end_day):
            return False
        if not ValidationUtils.is_valid_period(start_period):
            return False
        if not ValidationUtils.is_valid_period(end_period):
            return False
        
        # 曜日の順序
        day_order = {day: i for i, day in enumerate(ValidationUtils.VALID_DAYS)}
        
        # 開始が終了より後の場合は無効
        if day_order[start_day] > day_order[end_day]:
            return False
        elif day_order[start_day] == day_order[end_day]:
            if start_period > end_period:
                return False
        
        return True
    
    @staticmethod
    def validate_csv_row(
        row: Dict[str, str],
        required_fields: List[str],
        optional_fields: Optional[List[str]] = None
    ) -> tuple[bool, Optional[str]]:
        """CSV行のバリデーション
        
        Args:
            row: CSV行（辞書）
            required_fields: 必須フィールド
            optional_fields: オプションフィールド
            
        Returns:
            (有効かどうか, エラーメッセージ)
        """
        # 必須フィールドのチェック
        for field in required_fields:
            if field not in row:
                return False, f"必須フィールド '{field}' が見つかりません"
            if not row[field].strip():
                return False, f"必須フィールド '{field}' が空です"
        
        # 不明なフィールドのチェック
        all_fields = set(required_fields)
        if optional_fields:
            all_fields.update(optional_fields)
        
        unknown_fields = set(row.keys()) - all_fields
        if unknown_fields:
            # 警告レベル（エラーにはしない）
            pass
        
        return True, None
    
    @staticmethod
    def clean_string(value: str) -> str:
        """文字列をクリーニング
        
        Args:
            value: 入力文字列
            
        Returns:
            クリーニングされた文字列
        """
        # 前後の空白を削除
        value = value.strip()
        
        # 全角スペースを半角に変換
        value = value.replace('　', ' ')
        
        # 連続する空白を1つに
        value = re.sub(r'\s+', ' ', value)
        
        # 制御文字を削除
        value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
        
        return value