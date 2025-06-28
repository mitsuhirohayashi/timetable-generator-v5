"""バリデーション機能を提供するミックスイン

クラスにバリデーション機能を追加するための共通ミックスインです。
"""
from typing import Any, Dict, List, Optional, Callable, Union
from functools import wraps


class ValidationError(Exception):
    """バリデーションエラー"""
    pass


class ValidationMixin:
    """バリデーション機能を提供するミックスイン
    
    使用例:
        class MyClass(ValidationMixin):
            def process_data(self, data: dict):
                self.validate_not_none(data, "data")
                self.validate_type(data, dict, "data")
                self.validate_required_keys(data, ["id", "name"])
    """
    
    def validate_not_none(self, value: Any, name: str) -> Any:
        """値がNoneでないことを検証
        
        Args:
            value: 検証する値
            name: 値の名前（エラーメッセージ用）
            
        Returns:
            検証済みの値
            
        Raises:
            ValidationError: 値がNoneの場合
        """
        if value is None:
            raise ValidationError(f"{name}はNoneにできません")
        return value
    
    def validate_type(
        self,
        value: Any,
        expected_type: Union[type, tuple],
        name: str
    ) -> Any:
        """値の型を検証
        
        Args:
            value: 検証する値
            expected_type: 期待する型（またはタプル）
            name: 値の名前
            
        Returns:
            検証済みの値
            
        Raises:
            ValidationError: 型が一致しない場合
        """
        if not isinstance(value, expected_type):
            type_name = (
                expected_type.__name__ 
                if hasattr(expected_type, '__name__')
                else str(expected_type)
            )
            raise ValidationError(
                f"{name}は{type_name}型である必要があります。"
                f"実際の型: {type(value).__name__}"
            )
        return value
    
    def validate_range(
        self,
        value: Union[int, float],
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        name: str = "value"
    ) -> Union[int, float]:
        """数値の範囲を検証
        
        Args:
            value: 検証する値
            min_value: 最小値（含む）
            max_value: 最大値（含む）
            name: 値の名前
            
        Returns:
            検証済みの値
            
        Raises:
            ValidationError: 範囲外の場合
        """
        if min_value is not None and value < min_value:
            raise ValidationError(
                f"{name}は{min_value}以上である必要があります。"
                f"実際の値: {value}"
            )
        
        if max_value is not None and value > max_value:
            raise ValidationError(
                f"{name}は{max_value}以下である必要があります。"
                f"実際の値: {value}"
            )
        
        return value
    
    def validate_length(
        self,
        value: Union[str, list, dict],
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        name: str = "value"
    ) -> Union[str, list, dict]:
        """長さを検証
        
        Args:
            value: 検証する値
            min_length: 最小長
            max_length: 最大長
            name: 値の名前
            
        Returns:
            検証済みの値
            
        Raises:
            ValidationError: 長さが範囲外の場合
        """
        length = len(value)
        
        if min_length is not None and length < min_length:
            raise ValidationError(
                f"{name}の長さは{min_length}以上である必要があります。"
                f"実際の長さ: {length}"
            )
        
        if max_length is not None and length > max_length:
            raise ValidationError(
                f"{name}の長さは{max_length}以下である必要があります。"
                f"実際の長さ: {length}"
            )
        
        return value
    
    def validate_in_choices(
        self,
        value: Any,
        choices: Union[list, set, tuple],
        name: str = "value"
    ) -> Any:
        """値が選択肢に含まれることを検証
        
        Args:
            value: 検証する値
            choices: 有効な選択肢
            name: 値の名前
            
        Returns:
            検証済みの値
            
        Raises:
            ValidationError: 選択肢に含まれない場合
        """
        if value not in choices:
            raise ValidationError(
                f"{name}は次の選択肢から選ぶ必要があります: {choices}。"
                f"実際の値: {value}"
            )
        return value
    
    def validate_required_keys(
        self,
        data: dict,
        required_keys: List[str],
        name: str = "data"
    ) -> dict:
        """必須キーの存在を検証
        
        Args:
            data: 検証する辞書
            required_keys: 必須キーのリスト
            name: 辞書の名前
            
        Returns:
            検証済みの辞書
            
        Raises:
            ValidationError: 必須キーが存在しない場合
        """
        missing_keys = [key for key in required_keys if key not in data]
        
        if missing_keys:
            raise ValidationError(
                f"{name}に必須キーが不足しています: {missing_keys}"
            )
        
        return data
    
    def validate_custom(
        self,
        value: Any,
        validator: Callable[[Any], bool],
        error_message: str,
        name: str = "value"
    ) -> Any:
        """カスタムバリデーション
        
        Args:
            value: 検証する値
            validator: バリデーション関数（Trueを返すと有効）
            error_message: エラーメッセージ
            name: 値の名前
            
        Returns:
            検証済みの値
            
        Raises:
            ValidationError: バリデーションに失敗した場合
        """
        if not validator(value):
            raise ValidationError(f"{name}: {error_message}")
        return value


def validate_args(**validators):
    """引数をバリデーションするデコレータ
    
    使用例:
        @validate_args(
            x=lambda x: x > 0,
            y=lambda y: isinstance(y, str)
        )
        def calculate(self, x: int, y: str) -> int:
            return x * len(y)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 関数の引数名を取得
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # バリデーションを実行
            for arg_name, validator in validators.items():
                if arg_name in bound_args.arguments:
                    value = bound_args.arguments[arg_name]
                    if not validator(value):
                        raise ValidationError(
                            f"引数 {arg_name} のバリデーションに失敗しました。"
                            f"値: {value}"
                        )
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator