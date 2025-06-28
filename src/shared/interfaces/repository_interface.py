"""リポジトリの共通インターフェース

データアクセス層の共通インターフェースを定義します。
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Dict, Any

# エンティティの型変数
T = TypeVar('T')


class RepositoryInterface(ABC, Generic[T]):
    """リポジトリの基本インターフェース
    
    データの永続化と取得を抽象化します。
    """
    
    @abstractmethod
    def find_by_id(self, id: Any) -> Optional[T]:
        """IDによってエンティティを検索
        
        Args:
            id: エンティティのID
            
        Returns:
            エンティティまたはNone
        """
        pass
    
    @abstractmethod
    def find_all(self) -> List[T]:
        """全てのエンティティを取得
        
        Returns:
            エンティティのリスト
        """
        pass
    
    @abstractmethod
    def save(self, entity: T) -> T:
        """エンティティを保存
        
        Args:
            entity: 保存するエンティティ
            
        Returns:
            保存されたエンティティ
        """
        pass
    
    @abstractmethod
    def delete(self, id: Any) -> bool:
        """エンティティを削除
        
        Args:
            id: 削除するエンティティのID
            
        Returns:
            削除に成功した場合True
        """
        pass
    
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """条件によってエンティティを検索
        
        Args:
            criteria: 検索条件
            
        Returns:
            条件に一致するエンティティのリスト
        """
        # デフォルト実装（オーバーライド可能）
        raise NotImplementedError("find_by_criteriaは実装されていません")
    
    def exists(self, id: Any) -> bool:
        """エンティティが存在するかチェック
        
        Args:
            id: エンティティのID
            
        Returns:
            存在する場合True
        """
        return self.find_by_id(id) is not None
    
    def count(self) -> int:
        """エンティティの総数を取得
        
        Returns:
            エンティティの総数
        """
        return len(self.find_all())
    
    def save_all(self, entities: List[T]) -> List[T]:
        """複数のエンティティを一括保存
        
        Args:
            entities: 保存するエンティティのリスト
            
        Returns:
            保存されたエンティティのリスト
        """
        return [self.save(entity) for entity in entities]
    
    def delete_all(self, ids: List[Any]) -> int:
        """複数のエンティティを一括削除
        
        Args:
            ids: 削除するエンティティのIDリスト
            
        Returns:
            削除されたエンティティ数
        """
        count = 0
        for id in ids:
            if self.delete(id):
                count += 1
        return count


class ReadOnlyRepositoryInterface(ABC, Generic[T]):
    """読み取り専用リポジトリのインターフェース
    
    データの取得のみを提供します。
    """
    
    @abstractmethod
    def find_by_id(self, id: Any) -> Optional[T]:
        """IDによってエンティティを検索"""
        pass
    
    @abstractmethod
    def find_all(self) -> List[T]:
        """全てのエンティティを取得"""
        pass
    
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """条件によってエンティティを検索"""
        raise NotImplementedError("find_by_criteriaは実装されていません")
    
    def exists(self, id: Any) -> bool:
        """エンティティが存在するかチェック"""
        return self.find_by_id(id) is not None
    
    def count(self) -> int:
        """エンティティの総数を取得"""
        return len(self.find_all())


class CachedRepositoryInterface(RepositoryInterface[T]):
    """キャッシュ機能を持つリポジトリのインターフェース
    
    キャッシュを使用してパフォーマンスを向上させます。
    """
    
    @abstractmethod
    def invalidate_cache(self, id: Optional[Any] = None) -> None:
        """キャッシュを無効化
        
        Args:
            id: 特定のエンティティのキャッシュのみ無効化する場合のID
        """
        pass
    
    @abstractmethod
    def preload_cache(self) -> None:
        """キャッシュを事前読み込み"""
        pass