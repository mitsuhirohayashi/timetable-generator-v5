#!/usr/bin/env python3
"""Ultrathink時間割リファクタリング - 根本的な問題解決"""

import sys
from pathlib import Path
import subprocess
import platform
import logging
import json
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import shutil
from datetime import datetime

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.infrastructure.config.path_config import path_config

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UltrathinkRefactoring:
    """時間割システムの根本的リファクタリング"""
    
    def __init__(self):
        self.project_root = project_root
        self.backup_dir = path_config.data_dir / "output" / "backup"
        self.backup_dir.mkdir(exist_ok=True)
        
        # 分析結果を保存
        self.analysis_results = {
            "current_violations": {},
            "root_causes": [],
            "recommendations": [],
            "strategy": {}
        }
    
    def refactor_timetable_system(self):
        """時間割システムをリファクタリング"""
        logger.info("=== Ultrathink時間割リファクタリング開始 ===\n")
        logger.info("目標：根本的な問題を解決し、制約違反を最小化\n")
        
        # フェーズ1: 現状分析
        logger.info("フェーズ1: 現状分析...")
        self._analyze_current_state()
        
        # フェーズ2: バックアップ作成
        logger.info("\nフェーズ2: 現在の時間割をバックアップ...")
        backup_path = self._backup_current_schedule()
        logger.info(f"  バックアップ作成: {backup_path}")
        
        # フェーズ3: 戦略決定
        logger.info("\nフェーズ3: 最適な生成戦略を決定...")
        strategy = self._determine_strategy()
        
        # フェーズ4: 設定最適化
        logger.info("\nフェーズ4: システム設定を最適化...")
        self._optimize_system_settings()
        
        # フェーズ5: 新規時間割生成
        logger.info("\nフェーズ5: 最適化された設定で新規時間割を生成...")
        success = self._generate_new_schedule(strategy)
        
        if success:
            # フェーズ6: 結果検証
            logger.info("\nフェーズ6: 生成結果を検証...")
            improvements = self._verify_results()
            
            # フェーズ7: 最終調整
            logger.info("\nフェーズ7: 最終調整...")
            self._final_adjustments()
            
            # 完了レポート
            self._generate_completion_report(improvements)
        else:
            logger.error("\n時間割生成に失敗しました。バックアップから復元します...")
            self._restore_from_backup(backup_path)
        
        # 完了音を鳴らす
        self._play_completion_sound()
    
    def _analyze_current_state(self):
        """現在の状態を分析"""
        # 制約違反チェックスクリプトを実行
        result = subprocess.run(
            ["python3", "scripts/analysis/check_violations.py"],
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        if result.returncode == 0:
            output = result.stdout
            
            # 違反数を抽出
            import re
            violation_match = re.search(r'❌ (\d+) 件の制約違反', output)
            if violation_match:
                total_violations = int(violation_match.group(1))
                self.analysis_results["current_violations"]["total"] = total_violations
            
            # 違反タイプ別に分析
            if "教師重複制約違反" in output:
                teacher_match = re.search(r'【教師重複制約違反】\((\d+)件\)', output)
                if teacher_match:
                    self.analysis_results["current_violations"]["teacher_conflicts"] = int(teacher_match.group(1))
            
            if "体育館使用制約違反" in output:
                gym_match = re.search(r'【体育館使用制約違反】\((\d+)件\)', output)
                if gym_match:
                    self.analysis_results["current_violations"]["gym_conflicts"] = int(gym_match.group(1))
            
            if "日内重複制約違反" in output:
                daily_match = re.search(r'【日内重複制約違反】\((\d+)件\)', output)
                if daily_match:
                    self.analysis_results["current_violations"]["daily_duplicates"] = int(daily_match.group(1))
        
        # 根本原因を特定
        self._identify_root_causes()
    
    def _identify_root_causes(self):
        """根本原因を特定"""
        violations = self.analysis_results["current_violations"]
        
        if violations.get("teacher_conflicts", 0) > 30:
            self.analysis_results["root_causes"].append(
                "教師配置の最適化不足：同一教師が同時に複数クラスを担当"
            )
            self.analysis_results["recommendations"].append(
                "教師スケジュール管理の強化"
            )
        
        if violations.get("gym_conflicts", 0) > 20:
            self.analysis_results["root_causes"].append(
                "体育館リソースの競合：同時に多数のクラスが体育を実施"
            )
            self.analysis_results["recommendations"].append(
                "体育の時間配置を分散化"
            )
        
        if violations.get("daily_duplicates", 0) > 20:
            self.analysis_results["root_causes"].append(
                "日内スケジューリングの問題：同じ日に同じ科目が重複"
            )
            self.analysis_results["recommendations"].append(
                "日内重複チェックの強化"
            )
    
    def _backup_current_schedule(self) -> Path:
        """現在の時間割をバックアップ"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"output_backup_{timestamp}.csv"
        
        current_output = path_config.data_dir / "output" / "output.csv"
        backup_path = self.backup_dir / backup_filename
        
        if current_output.exists():
            shutil.copy2(current_output, backup_path)
        
        return backup_path
    
    def _determine_strategy(self) -> Dict:
        """最適な生成戦略を決定"""
        strategy = {
            "algorithm": "ultrathink",  # UltraOptimized algorithm
            "priorities": [],
            "optimizations": [],
            "constraints": []
        }
        
        # 問題に応じて優先順位を設定
        violations = self.analysis_results["current_violations"]
        
        if violations.get("teacher_conflicts", 0) > 20:
            strategy["priorities"].append("teacher_schedule_optimization")
            strategy["optimizations"].append("--optimize-workload")
        
        if violations.get("gym_conflicts", 0) > 10:
            strategy["priorities"].append("gym_usage_optimization")
            strategy["optimizations"].append("--optimize-gym-usage")
        
        if violations.get("daily_duplicates", 0) > 10:
            strategy["priorities"].append("daily_balance_optimization")
            strategy["constraints"].append("strict_daily_duplicate_check")
        
        # 5組の時数表記を使用
        strategy["optimizations"].append("--use-support-hours")
        
        self.analysis_results["strategy"] = strategy
        logger.info(f"  決定した戦略: {json.dumps(strategy, ensure_ascii=False, indent=2)}")
        
        return strategy
    
    def _optimize_system_settings(self):
        """システム設定を最適化"""
        # 一時的な設定ファイルを作成
        config_optimizations = {
            "max_iterations": 500,  # より多くの反復
            "constraint_weights": {
                "teacher_conflict": 100,
                "gym_usage": 80,
                "daily_duplicate": 70,
                "exchange_sync": 60,
                "grade5_sync": 60,
                "standard_hours": 30
            },
            "optimization_params": {
                "enable_smart_swap": True,
                "enable_lookahead": True,
                "enable_backtrack": True,
                "parallel_search": True
            }
        }
        
        # 設定を一時ファイルに保存
        temp_config_path = self.project_root / "temp_optimization_config.json"
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            json.dump(config_optimizations, f, ensure_ascii=False, indent=2)
        
        logger.info("  最適化設定を作成しました")
    
    def _generate_new_schedule(self, strategy: Dict) -> bool:
        """新規時間割を生成"""
        # コマンドを構築
        cmd = ["python3", "main.py", "generate"]
        
        # 最適化オプションを追加
        cmd.extend(strategy.get("optimizations", []))
        
        # 実行
        logger.info(f"  実行コマンド: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        if result.returncode == 0:
            logger.info("  ✅ 時間割生成成功")
            if result.stdout:
                # 生成結果の要約を表示
                lines = result.stdout.strip().split('\n')
                for line in lines[-10:]:  # 最後の10行を表示
                    if line.strip():
                        logger.info(f"    {line}")
            return True
        else:
            logger.error("  ❌ 時間割生成失敗")
            if result.stderr:
                logger.error(f"  エラー: {result.stderr}")
            return False
    
    def _verify_results(self) -> Dict:
        """生成結果を検証"""
        # 新しい時間割の違反をチェック
        result = subprocess.run(
            ["python3", "scripts/analysis/check_violations.py"],
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        improvements = {
            "before": self.analysis_results["current_violations"],
            "after": {},
            "improvement_rate": 0
        }
        
        if result.returncode == 0:
            output = result.stdout
            
            # 新しい違反数を抽出
            import re
            violation_match = re.search(r'❌ (\d+) 件の制約違反', output)
            if violation_match:
                new_violations = int(violation_match.group(1))
                improvements["after"]["total"] = new_violations
                
                # 改善率を計算
                old_violations = improvements["before"].get("total", 0)
                if old_violations > 0:
                    improvement_rate = (old_violations - new_violations) / old_violations * 100
                    improvements["improvement_rate"] = improvement_rate
                    logger.info(f"  改善率: {improvement_rate:.1f}%")
                    logger.info(f"  違反数: {old_violations} → {new_violations}")
        
        return improvements
    
    def _final_adjustments(self):
        """最終調整"""
        # 残存する違反に対して軽微な修正を実行
        logger.info("  残存違反の微調整を実行...")
        
        # 80%修正スクリプトを実行（軽微な調整のみ）
        result = subprocess.run(
            ["python3", "scripts/fixes/practical_80_percent_fix.py"],
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        if result.returncode == 0:
            logger.info("  ✅ 最終調整完了")
        else:
            logger.warning("  ⚠️ 最終調整で一部エラー")
    
    def _restore_from_backup(self, backup_path: Path):
        """バックアップから復元"""
        output_path = path_config.data_dir / "output" / "output.csv"
        if backup_path.exists():
            shutil.copy2(backup_path, output_path)
            logger.info(f"  バックアップから復元しました: {backup_path}")
    
    def _generate_completion_report(self, improvements: Dict):
        """完了レポートを生成"""
        logger.info("\n" + "="*60)
        logger.info("=== リファクタリング完了レポート ===")
        logger.info("="*60)
        
        logger.info("\n【問題分析】")
        for cause in self.analysis_results["root_causes"]:
            logger.info(f"  • {cause}")
        
        logger.info("\n【実施した最適化】")
        for opt in self.analysis_results["strategy"].get("optimizations", []):
            logger.info(f"  • {opt}")
        
        logger.info("\n【改善結果】")
        before = improvements.get("before", {})
        after = improvements.get("after", {})
        
        logger.info(f"  総違反数: {before.get('total', 'N/A')} → {after.get('total', 'N/A')}")
        logger.info(f"  改善率: {improvements.get('improvement_rate', 0):.1f}%")
        
        logger.info("\n【推奨事項】")
        for rec in self.analysis_results["recommendations"]:
            logger.info(f"  • {rec}")
        
        # レポートをファイルに保存
        report_path = self.project_root / "docs" / "reports" / "ultrathink_refactoring_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Ultrathink時間割リファクタリングレポート\n\n")
            f.write(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## 問題分析\n")
            for cause in self.analysis_results["root_causes"]:
                f.write(f"- {cause}\n")
            f.write("\n## 改善結果\n")
            f.write(f"- 総違反数: {before.get('total', 'N/A')} → {after.get('total', 'N/A')}\n")
            f.write(f"- 改善率: {improvements.get('improvement_rate', 0):.1f}%\n")
        
        logger.info(f"\n詳細レポートを保存: {report_path}")
    
    def _play_completion_sound(self):
        """完了音を鳴らす"""
        logger.info("\n🔔 リファクタリング完了！")
        
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                # 成功音を2回鳴らす
                subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
                subprocess.run(["sleep", "0.3"])
                subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
            elif system == "Linux":
                subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"])
            elif system == "Windows":
                import winsound
                winsound.MessageBeep()
                winsound.MessageBeep()
        except Exception as e:
            logger.info(f"[音声通知エラー: {e}]")
        
        # ターミナルベルも鳴らす
        print("\a\a")  # 2回鳴らす


def main():
    """メイン処理"""
    refactoring = UltrathinkRefactoring()
    refactoring.refactor_timetable_system()


if __name__ == "__main__":
    main()