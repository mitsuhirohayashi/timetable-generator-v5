"""時間割操作の共通ユーティリティ"""

import pandas as pd
from typing import Optional, List, Tuple


class ScheduleUtils:
    """時間割操作のための共通ユーティリティクラス"""
    
    # 固定科目のリスト（一元管理）
    FIXED_SUBJECTS = [
        "欠", "YT", "道", "道徳", "学", "学活", "学総", 
        "総", "総合", "行", "行事", "テスト", "技家", ""
    ]
    
    # 自立活動関連科目
    JIRITSU_SUBJECTS = ["自立", "日生", "生単", "作業"]
    
    @staticmethod
    def get_cell(df: pd.DataFrame, day: str, period: str) -> Optional[int]:
        """指定された曜日と時限のセル位置（列番号）を取得
        
        Args:
            df: 時間割DataFrame
            day: 曜日（"月", "火", "水", "木", "金"）
            period: 時限（"1", "2", "3", "4", "5", "6"）
            
        Returns:
            列番号（1-indexed）またはNone
        """
        days = df.iloc[0, 1:].tolist()
        periods = df.iloc[1, 1:].tolist()
        
        for i, (d, p) in enumerate(zip(days, periods)):
            if d == day and str(p) == str(period):
                return i + 1
        return None
    
    @staticmethod
    def get_class_row(df: pd.DataFrame, class_name: str) -> Optional[int]:
        """指定されたクラスの行番号を取得
        
        Args:
            df: 時間割DataFrame
            class_name: クラス名（例: "1年1組"）
            
        Returns:
            行番号（0-indexed）またはNone
        """
        for i in range(2, len(df)):
            if df.iloc[i, 0] == class_name:
                return i
        return None
    
    @staticmethod
    def is_fixed_subject(subject: str) -> bool:
        """固定科目かどうかを判定
        
        Args:
            subject: 科目名
            
        Returns:
            固定科目の場合True
        """
        if pd.isna(subject):
            return True
        return subject in ScheduleUtils.FIXED_SUBJECTS
    
    @staticmethod
    def is_jiritsu_activity(subject: str) -> bool:
        """自立活動関連科目かどうかを判定
        
        Args:
            subject: 科目名
            
        Returns:
            自立活動関連科目の場合True
        """
        if pd.isna(subject):
            return False
        return subject in ScheduleUtils.JIRITSU_SUBJECTS
    
    @staticmethod
    def is_exchange_class(class_name: str) -> bool:
        """交流学級かどうかを判定
        
        Args:
            class_name: クラス名
            
        Returns:
            交流学級（6組または7組）の場合True
        """
        return "6組" in class_name or "7組" in class_name
    
    @staticmethod
    def is_grade5_class(class_name: str) -> bool:
        """5組クラスかどうかを判定
        
        Args:
            class_name: クラス名
            
        Returns:
            5組の場合True
        """
        return "5組" in class_name
    
    @staticmethod
    def get_day_subjects(df: pd.DataFrame, class_name: str, day: str) -> List[str]:
        """指定クラスの指定曜日の科目リストを取得
        
        Args:
            df: 時間割DataFrame
            class_name: クラス名
            day: 曜日
            
        Returns:
            科目のリスト（固定科目と空文字列を除く）
        """
        class_row = ScheduleUtils.get_class_row(df, class_name)
        if not class_row:
            return []
        
        subjects = []
        for period in range(1, 7):
            col = ScheduleUtils.get_cell(df, day, str(period))
            if col:
                subject = df.iloc[class_row, col]
                if pd.notna(subject) and subject != "" and not ScheduleUtils.is_fixed_subject(subject):
                    subjects.append(subject)
        
        return subjects
    
    @staticmethod
    def would_cause_daily_duplicate(df: pd.DataFrame, class_name: str, subject: str, day: str) -> bool:
        """日内重複が発生するかチェック
        
        Args:
            df: 時間割DataFrame
            class_name: クラス名
            subject: 科目名
            day: 曜日
            
        Returns:
            重複する場合True
        """
        day_subjects = ScheduleUtils.get_day_subjects(df, class_name, day)
        return subject in day_subjects
    
    @staticmethod
    def get_exchange_class_pairs() -> List[Tuple[str, str]]:
        """交流学級と親学級のペアリストを取得
        
        Returns:
            (交流学級, 親学級)のタプルのリスト
        """
        return [
            ("1年6組", "1年1組"),
            ("1年7組", "1年2組"),
            ("2年6組", "2年3組"),
            ("2年7組", "2年2組"),
            ("3年6組", "3年3組"),
            ("3年7組", "3年2組"),
        ]
    
    @staticmethod
    def get_grade5_classes() -> List[str]:
        """5組クラスのリストを取得
        
        Returns:
            5組クラスのリスト
        """
        return ["1年5組", "2年5組", "3年5組"]