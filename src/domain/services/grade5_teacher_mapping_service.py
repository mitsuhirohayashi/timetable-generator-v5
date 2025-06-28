"""5組の教師マッピングサービス

teacher_subject_mapping.csvに基づいて5組の各教科の正しい教師を提供
"""
from typing import Dict, Optional
import logging


class Grade5TeacherMappingService:
    """5組の教師マッピングサービス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 5組の教科別教師マッピング（teacher_subject_mapping.csvより）
        self.grade5_teacher_mapping = {
            "国": "寺田",
            "社": "蒲地",
            "数": "梶永",
            "理": "智田",
            "音": "塚本",
            "美": "金子み",
            "保": "野口",
            "技": "林",
            "家": "金子み",
            "英": "林田",
            "道": "金子み",
            "学": "金子み",
            "総": "金子み",
            "YT": "金子み",
            "学総": "金子み",
            "自立": "金子み",
            "日生": "金子み",
            "作業": "金子み",
            "生単": "金子み",
        }
        
        # 5組のクラス
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
    
    def get_teacher_for_subject(self, subject: str) -> Optional[str]:
        """5組の特定教科の教師を取得
        
        Args:
            subject: 教科名
            
        Returns:
            教師名（見つからない場合はNone）
        """
        return self.grade5_teacher_mapping.get(subject)
    
    def is_grade5_class(self, class_name: str) -> bool:
        """指定されたクラスが5組かどうか判定"""
        return class_name in self.grade5_classes
    
    def validate_teacher_assignment(self, class_name: str, subject: str, teacher_name: str) -> bool:
        """5組の教師割り当てが正しいか検証
        
        Args:
            class_name: クラス名
            subject: 教科名
            teacher_name: 教師名
            
        Returns:
            正しい割り当てならTrue
        """
        # 5組以外は常にTrue
        if not self.is_grade5_class(class_name):
            return True
        
        # 5組の場合、正しい教師かチェック
        expected_teacher = self.get_teacher_for_subject(subject)
        if expected_teacher is None:
            self.logger.warning(f"5組の教科 {subject} に対する教師マッピングが見つかりません")
            return False
        
        if teacher_name != expected_teacher:
            self.logger.warning(
                f"5組の教師割り当て違反: {class_name} の {subject} は "
                f"{expected_teacher}先生が担当すべきですが、{teacher_name}先生が割り当てられています"
            )
            return False
        
        return True
    
    def get_all_grade5_teachers(self) -> Dict[str, str]:
        """5組の全ての教科-教師マッピングを取得"""
        return self.grade5_teacher_mapping.copy()
    
    def log_grade5_teacher_info(self):
        """5組の教師情報をログ出力"""
        self.logger.info("=== 5組の教師配置 ===")
        for subject, teacher in sorted(self.grade5_teacher_mapping.items()):
            self.logger.info(f"  {subject}: {teacher}先生")