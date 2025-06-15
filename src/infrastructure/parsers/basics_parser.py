"""basics.csvの制約定義を読み込むパーサー"""
from pathlib import Path
from typing import List, Dict, Any
import csv
from dataclasses import dataclass


@dataclass
class BasicConstraint:
    """basics.csvから読み込んだ制約を表現"""
    constraint_type: str  # 制約タイプ
    target: str          # 対象
    condition: str       # 条件
    content: str         # 内容
    priority: str        # 優先度


class BasicsParser:
    """basics.csvの制約定義を読み込むパーサー"""
    
    def parse(self, file_path: Path) -> List[BasicConstraint]:
        """basics.csvファイルを読み込んで制約リストを返す
        
        Args:
            file_path: basics.csvのパス
            
        Returns:
            BasicConstraintのリスト
        """
        constraints = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                constraint = BasicConstraint(
                    constraint_type=row['制約タイプ'],
                    target=row['対象'],
                    condition=row['条件'],
                    content=row['内容'],
                    priority=row['優先度']
                )
                constraints.append(constraint)
                
        return constraints
    
    def get_fixed_subjects(self, constraints: List[BasicConstraint]) -> List[str]:
        """固定教科のリストを取得
        
        Args:
            constraints: 制約リスト
            
        Returns:
            固定教科名のリスト
        """
        fixed_subjects = []
        for constraint in constraints:
            if constraint.constraint_type == '固定教科':
                fixed_subjects.append(constraint.target)
        return fixed_subjects
    
    def get_placement_forbidden_subjects(self, constraints: List[BasicConstraint]) -> List[str]:
        """配置禁止教科のリストを取得
        
        Args:
            constraints: 制約リスト
            
        Returns:
            配置禁止教科名のリスト
        """
        forbidden_subjects = []
        for constraint in constraints:
            if constraint.constraint_type == '配置禁止':
                # カンマ区切りまたは中点区切りの教科を分割
                subjects = constraint.target.replace('・', ',').split(',')
                forbidden_subjects.extend([s.strip() for s in subjects])
        return list(set(forbidden_subjects))  # 重複除去
    
    def get_special_processing_rules(self, constraints: List[BasicConstraint]) -> Dict[str, Dict[str, Any]]:
        """特殊処理ルールを取得
        
        Args:
            constraints: 制約リスト
            
        Returns:
            特殊処理ルールの辞書
        """
        rules = {}
        for constraint in constraints:
            if constraint.constraint_type in ['特殊処理', '時間固定', '交流学級処理']:
                if constraint.target not in rules:
                    rules[constraint.target] = []
                rules[constraint.target].append({
                    'type': constraint.constraint_type,
                    'condition': constraint.condition,
                    'content': constraint.content,
                    'priority': constraint.priority
                })
        return rules