"""高度なCSPアルゴリズム用の設定ローダー"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from src.domain.value_objects.time_slot import ClassReference
from ...shared.mixins.logging_mixin import LoggingMixin


@dataclass
class AdvancedCSPConfig:
    """高度なCSPアルゴリズムの設定"""
    exchange_parent_mappings: Dict[ClassReference, ClassReference]
    grade5_classes: List[ClassReference]
    fixed_subjects: List[str]
    jiritsu_subjects: List[str]
    parent_subjects_for_jiritsu: List[str]
    main_subjects: List[str]
    skill_subjects: List[str]
    excluded_sync_subjects: List[str]
    weekdays: List[str]
    periods_min: int
    periods_max: int
    monday_period_6: str
    yt_days: Dict[str, int]
    pe_preferred_day: str
    main_subjects_preferred_periods: List[int]
    skill_subjects_preferred_periods: List[int]
    max_iterations: int
    swap_attempts: int
    temperature: float
    # CSP特有のパラメータ
    backtrack_limit: int = 10000
    local_search_iterations: int = 500
    tabu_tenure: int = 10
    timeout_seconds: Optional[int] = None
    enable_constraint_propagation: bool = True
    enable_arc_consistency: bool = True
    search_strategy: str = "most_constrained_first"
    value_ordering_strategy: str = "least_constraining_value"
    priority_weights: Dict[str, float] = None
    optimization_phases: List[str] = None


class AdvancedCSPConfigLoader(LoggingMixin):
    """高度なCSP設定ローダー"""
    
    def __init__(self, config_path: Optional[Path] = None):
        super().__init__()
        self.config_path = config_path or Path("data/config/advanced_csp_config.json")
        
    def load(self) -> AdvancedCSPConfig:
        """設定ファイルを読み込んでAdvancedCSPConfigオブジェクトを返す"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 交流学級マッピングを変換
            exchange_mappings = {}
            for exchange, parent in data['exchange_parent_mappings'].items():
                exchange_parts = exchange.split('-')
                parent_parts = parent.split('-')
                exchange_ref = ClassReference(int(exchange_parts[0]), int(exchange_parts[1]))
                parent_ref = ClassReference(int(parent_parts[0]), int(parent_parts[1]))
                exchange_mappings[exchange_ref] = parent_ref
            
            # 5組クラスを変換
            grade5_classes = []
            for class_str in data['grade5_classes']:
                parts = class_str.split('-')
                grade5_classes.append(ClassReference(int(parts[0]), int(parts[1])))
            
            return AdvancedCSPConfig(
                exchange_parent_mappings=exchange_mappings,
                grade5_classes=grade5_classes,
                fixed_subjects=data['fixed_subjects'],
                jiritsu_subjects=data['jiritsu_subjects'],
                parent_subjects_for_jiritsu=data['parent_subjects_for_jiritsu'],
                main_subjects=data['main_subjects'],
                skill_subjects=data['skill_subjects'],
                excluded_sync_subjects=data['excluded_sync_subjects'],
                weekdays=data['weekdays'],
                periods_min=data['periods']['min'],
                periods_max=data['periods']['max'],
                monday_period_6=data['special_constraints']['monday_period_6'],
                yt_days=data['special_constraints']['yt_days'],
                pe_preferred_day=data['subject_preferences']['pe_preferred_day'],
                main_subjects_preferred_periods=data['subject_preferences']['main_subjects_preferred_periods'],
                skill_subjects_preferred_periods=data['subject_preferences']['skill_subjects_preferred_periods'],
                max_iterations=data['optimization']['max_iterations'],
                swap_attempts=data['optimization']['swap_attempts'],
                temperature=data['optimization']['temperature'],
                # CSP特有のパラメータ（JSONに存在しない場合はデフォルト値を使用）
                backtrack_limit=data.get('csp', {}).get('backtrack_limit', 10000),
                local_search_iterations=data.get('csp', {}).get('local_search_iterations', 500),
                tabu_tenure=data.get('csp', {}).get('tabu_tenure', 10),
                timeout_seconds=data.get('csp', {}).get('timeout_seconds', None),
                enable_constraint_propagation=data.get('csp', {}).get('enable_constraint_propagation', True),
                enable_arc_consistency=data.get('csp', {}).get('enable_arc_consistency', True),
                search_strategy=data.get('csp', {}).get('search_strategy', "most_constrained_first"),
                value_ordering_strategy=data.get('csp', {}).get('value_ordering_strategy', "least_constraining_value"),
                priority_weights=data.get('csp', {}).get('priority_weights', {"CRITICAL": 1000.0, "HIGH": 100.0, "MEDIUM": 10.0, "LOW": 1.0}),
                optimization_phases=data.get('csp', {}).get('optimization_phases', ["jiritsu", "grade5", "core_subjects", "skill_subjects", "fill_remaining"])
            )
            
        except FileNotFoundError:
            self.logger.warning(f"設定ファイル {self.config_path} が見つかりません。デフォルト設定を使用します。")
            return self._create_default_config()
        except Exception as e:
            self.logger.error(f"設定ファイルの読み込みエラー: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> AdvancedCSPConfig:
        """デフォルト設定を作成"""
        return AdvancedCSPConfig(
            exchange_parent_mappings={
                ClassReference(1, 6): ClassReference(1, 1),
                ClassReference(1, 7): ClassReference(1, 2),
                ClassReference(2, 6): ClassReference(2, 3),
                ClassReference(2, 7): ClassReference(2, 2),
                ClassReference(3, 6): ClassReference(3, 3),
                ClassReference(3, 7): ClassReference(3, 2)
            },
            grade5_classes=[
                ClassReference(1, 5),
                ClassReference(2, 5),
                ClassReference(3, 5)
            ],
            fixed_subjects=["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"],
            jiritsu_subjects=["自立", "日生", "生単", "作業"],
            parent_subjects_for_jiritsu=["数", "英"],
            main_subjects=["国", "数", "英", "理", "社"],
            skill_subjects=["音", "美", "技", "家"],
            excluded_sync_subjects=["保", "保健体育"],
            weekdays=["月", "火", "水", "木", "金"],
            periods_min=1,
            periods_max=6,
            monday_period_6="欠",
            yt_days={"火": 6, "水": 6, "金": 6},
            pe_preferred_day="火",
            main_subjects_preferred_periods=[1, 2, 3],
            skill_subjects_preferred_periods=[4, 5, 6],
            max_iterations=100,
            swap_attempts=21,
            temperature=0.1,
            # CSP特有のパラメータのデフォルト値
            backtrack_limit=10000,
            local_search_iterations=500,
            tabu_tenure=10,
            timeout_seconds=None,
            enable_constraint_propagation=True,
            enable_arc_consistency=True,
            search_strategy="most_constrained_first",
            value_ordering_strategy="least_constraining_value",
            priority_weights={"CRITICAL": 1000.0, "HIGH": 100.0, "MEDIUM": 10.0, "LOW": 1.0},
            optimization_phases=["jiritsu", "grade5", "core_subjects", "skill_subjects", "fill_remaining"]
        )