"""時間割生成アプリケーションサービス"""
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from datetime import datetime

from ..domain.models.timetable import Timetable, TimeSlot, ClassReference, Subject, Teacher
from ..domain.core.constraint_engine import ConstraintEngine, Violation
from ..domain.services.violation_fixer import ViolationFixer
from ..infrastructure.repositories.interfaces import (
    TimetableRepository, 
    SchoolDataRepository,
    ConfigRepository
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """生成設定"""
    max_iterations: int = 200
    use_advanced_csp: bool = True
    enable_soft_constraints: bool = True
    randomness_level: float = 0.3
    optimization_level: str = "high"  # low, medium, high
    

@dataclass
class GenerationResult:
    """生成結果"""
    timetable: Timetable
    violations: List[Violation]
    statistics: Dict[str, any]
    elapsed_time: float
    success: bool
    

class TimetableService:
    """時間割生成・管理サービス"""
    
    def __init__(self,
                 timetable_repo: TimetableRepository,
                 school_repo: SchoolDataRepository,
                 config_repo: ConfigRepository):
        self.timetable_repo = timetable_repo
        self.school_repo = school_repo
        self.config_repo = config_repo
        
        self.constraint_engine = ConstraintEngine()
        self.violation_fixer = ViolationFixer()
        
        self.logger = logging.getLogger(__name__)
    
    def generate_timetable(self, config: Optional[GenerationConfig] = None) -> GenerationResult:
        """時間割を生成"""
        start_time = datetime.now()
        config = config or GenerationConfig()
        
        self.logger.info("=== 時間割生成を開始 ===")
        self.logger.info(f"設定: {config}")
        
        try:
            # 1. 学校データを読み込み
            school_data = self.school_repo.load_school_data()
            
            # 2. 初期時間割を作成または読み込み
            timetable = self._create_initial_timetable(school_data)
            
            # 3. 固定教科をロック
            self._lock_fixed_subjects(timetable, school_data)
            
            # 4. 必須制約を満たすように配置
            self._place_required_assignments(timetable, school_data, config)
            
            # 5. 最適化ループ
            best_timetable = timetable
            best_violations = []
            
            for iteration in range(config.max_iterations):
                # 制約チェック
                violations = self.constraint_engine.check_all(timetable)
                
                if not violations:
                    self.logger.info(f"イテレーション {iteration}: すべての制約を満たしました！")
                    best_timetable = timetable
                    best_violations = []
                    break
                
                # 最良の結果を記録
                if not best_violations or len(violations) < len(best_violations):
                    best_timetable = timetable.clone()
                    best_violations = violations
                
                # 違反を修正
                fix_results = self.violation_fixer.fix_violations(violations, timetable)
                
                self.logger.debug(
                    f"イテレーション {iteration}: "
                    f"違反 {len(violations)}件, "
                    f"修正 {fix_results['fixed']}件"
                )
                
                # 改善がない場合は終了
                if fix_results['fixed'] == 0:
                    self.logger.warning("これ以上の改善ができません")
                    break
                
                # ランダムな摂動を加える（局所最適を避ける）
                if config.randomness_level > 0 and iteration % 10 == 0:
                    self._apply_random_perturbation(timetable, config.randomness_level)
            
            # 6. 結果を作成
            elapsed_time = (datetime.now() - start_time).total_seconds()
            statistics = best_timetable.get_statistics()
            
            result = GenerationResult(
                timetable=best_timetable,
                violations=best_violations,
                statistics=statistics,
                elapsed_time=elapsed_time,
                success=len(best_violations) == 0
            )
            
            # 7. 結果を保存
            self.timetable_repo.save_timetable(best_timetable)
            
            self.logger.info(f"=== 生成完了 ({elapsed_time:.2f}秒) ===")
            self.logger.info(f"違反件数: {len(best_violations)}")
            self.logger.info(f"充足率: {statistics['fill_rate']:.1%}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"時間割生成中にエラーが発生: {e}", exc_info=True)
            raise
    
    def validate_timetable(self, timetable_path: Optional[str] = None) -> Dict[str, any]:
        """時間割を検証"""
        # 時間割を読み込み
        if timetable_path:
            timetable = self.timetable_repo.load_timetable(timetable_path)
        else:
            timetable = self.timetable_repo.load_latest_timetable()
        
        # 学校データを読み込み
        school_data = self.school_repo.load_school_data()
        
        # 制約チェック
        violations = self.constraint_engine.check_all(timetable)
        
        # 統計情報
        statistics = timetable.get_statistics()
        
        # 違反の分類
        violation_summary = {}
        for violation in violations:
            key = f"{violation.type.name} ({violation.priority.name})"
            if key not in violation_summary:
                violation_summary[key] = 0
            violation_summary[key] += 1
        
        return {
            'valid': len(violations) == 0,
            'violations': violations,
            'violation_summary': violation_summary,
            'statistics': statistics
        }
    
    def fix_violations(self, timetable_path: Optional[str] = None) -> GenerationResult:
        """違反を修正"""
        start_time = datetime.now()
        
        # 時間割を読み込み
        if timetable_path:
            timetable = self.timetable_repo.load_timetable(timetable_path)
        else:
            timetable = self.timetable_repo.load_latest_timetable()
        
        # 学校データを読み込み
        school_data = self.school_repo.load_school_data()
        
        # 制約チェック
        violations = self.constraint_engine.check_all(timetable)
        
        if not violations:
            self.logger.info("違反はありません")
            return GenerationResult(
                timetable=timetable,
                violations=[],
                statistics=timetable.get_statistics(),
                elapsed_time=0,
                success=True
            )
        
        self.logger.info(f"{len(violations)}件の違反を修正します")
        
        # 違反を修正
        fix_results = self.violation_fixer.fix_violations(violations, timetable)
        
        # 再チェック
        remaining_violations = self.constraint_engine.check_all(timetable)
        
        # 結果を保存
        if len(remaining_violations) < len(violations):
            self.timetable_repo.save_timetable(timetable, suffix="_fixed")
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        return GenerationResult(
            timetable=timetable,
            violations=remaining_violations,
            statistics=timetable.get_statistics(),
            elapsed_time=elapsed_time,
            success=len(remaining_violations) == 0
        )
    
    def export_timetable(self, timetable: Timetable, format: str = "csv") -> str:
        """時間割をエクスポート"""
        if format == "csv":
            return self.timetable_repo.export_to_csv(timetable)
        elif format == "excel":
            return self.timetable_repo.export_to_excel(timetable)
        elif format == "json":
            return self.timetable_repo.export_to_json(timetable)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _create_initial_timetable(self, school_data: Dict) -> Timetable:
        """初期時間割を作成"""
        # 既存の希望時間割があれば読み込み
        try:
            initial = self.timetable_repo.load_input_timetable()
            self.logger.info("希望時間割を読み込みました")
            return initial
        except:
            self.logger.info("空の時間割から開始します")
            return Timetable()
    
    def _lock_fixed_subjects(self, timetable: Timetable, school_data: Dict):
        """固定教科をロック"""
        fixed_subjects = ["欠", "YT", "道", "道徳", "行"]
        locked_count = 0
        
        for assignment in timetable.get_all_assignments():
            if assignment.subject.name in fixed_subjects:
                timetable.lock_cell(assignment.time_slot, assignment.class_ref)
                locked_count += 1
        
        self.logger.info(f"{locked_count}個の固定教科をロックしました")
    
    def _place_required_assignments(self, timetable: Timetable, 
                                  school_data: Dict, config: GenerationConfig):
        """必須の割り当てを配置"""
        # 実装はドメインサービスに委譲
        # ここでは省略
        pass
    
    def _apply_random_perturbation(self, timetable: Timetable, level: float):
        """ランダムな摂動を加える"""
        import random
        
        # ランダムに選んだ割り当てを交換
        assignments = [a for a in timetable.get_all_assignments() 
                      if not a.subject.is_protected]
        
        if len(assignments) >= 2:
            # ランダムに2つ選択
            a1, a2 = random.sample(assignments, 2)
            
            # 同じクラスの場合のみ交換
            if a1.class_ref == a2.class_ref:
                # 交換を試みる
                timetable.remove(a1.time_slot, a1.class_ref)
                timetable.remove(a2.time_slot, a2.class_ref)
                
                timetable.assign(a1.time_slot, a1.class_ref, a2.subject, a2.teacher)
                timetable.assign(a2.time_slot, a2.class_ref, a1.subject, a1.teacher)