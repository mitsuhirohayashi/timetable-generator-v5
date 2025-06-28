"""違反の依存関係グラフ"""
from typing import Dict, List, Set
from collections import defaultdict, deque

from ..data_models import Violation


class ViolationGraph:
    """違反の依存関係グラフ
    
    違反間の依存関係を管理し、修正の影響を追跡します。
    """
    
    def __init__(self):
        """初期化"""
        self.violations: Dict[str, Violation] = {}
        self.edges: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_edges: Dict[str, Set[str]] = defaultdict(set)
    
    def add_violation(self, violation: Violation) -> str:
        """違反を追加
        
        Args:
            violation: 違反オブジェクト
            
        Returns:
            違反ID
        """
        vid = f"{violation.type}_{violation.time_slot}_{','.join(str(c) for c in violation.class_refs)}"
        self.violations[vid] = violation
        return vid
    
    def add_dependency(self, from_vid: str, to_vid: str):
        """依存関係を追加
        
        from_vidを解決するとto_vidに影響します。
        
        Args:
            from_vid: 元の違反ID
            to_vid: 影響を受ける違反ID
        """
        self.edges[from_vid].add(to_vid)
        self.reverse_edges[to_vid].add(from_vid)
    
    def get_impact_chain(self, vid: str) -> List[str]:
        """違反を解決した時の影響連鎖を取得
        
        Args:
            vid: 違反ID
            
        Returns:
            影響を受ける違反IDのリスト
        """
        visited = set()
        queue = deque([vid])
        chain = []
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            
            visited.add(current)
            chain.append(current)
            
            for next_vid in self.edges.get(current, []):
                if next_vid not in visited:
                    queue.append(next_vid)
        
        return chain
    
    def get_root_violations(self) -> List[str]:
        """根本原因となる違反を取得
        
        Returns:
            ルート違反IDのリスト
        """
        roots = []
        for vid in self.violations:
            if vid not in self.reverse_edges or not self.reverse_edges[vid]:
                roots.append(vid)
        return roots