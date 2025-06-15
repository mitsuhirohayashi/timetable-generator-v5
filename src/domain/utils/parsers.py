"""ドメイン共通のパーサー関数"""
from typing import Optional
from ..value_objects.time_slot import ClassReference


def parse_class_reference(class_name: str) -> Optional[ClassReference]:
    """クラス名文字列からClassReferenceを作成
    
    Args:
        class_name: クラス名文字列 (例: "1年1組")
    
    Returns:
        ClassReference: 成功時はClassReferenceオブジェクト、失敗時はNone
    
    Examples:
        >>> parse_class_reference("1年1組")
        ClassReference(grade=1, class_number=1)
        >>> parse_class_reference("2年5組")
        ClassReference(grade=2, class_number=5)
        >>> parse_class_reference("invalid")
        None
    """
    try:
        # "1年1組" -> grade=1, class_number=1
        if "年" in class_name and "組" in class_name:
            parts = class_name.replace("年", ",").replace("組", "").split(",")
            if len(parts) == 2:
                grade = int(parts[0])
                class_number = int(parts[1])
                return ClassReference(grade, class_number)
    except (ValueError, IndexError):
        pass
    
    return None