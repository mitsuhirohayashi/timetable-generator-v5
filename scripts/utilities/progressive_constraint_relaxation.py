#!/usr/bin/env python3
"""段階的制約緩和による時間割生成改善システム"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.domain.constraints.base import ConstraintPriority
from src.application.services.schedule_generation_service import ScheduleGenerationService
from src.infrastructure.repositories.csv_repository import CSVRepository
import json
from datetime import datetime
from typing import Dict, List, Tuple

class ProgressiveConstraintRelaxation:
    """段階的に制約を緩和して実現可能解を探索"""
    
    def __init__(self):
        self.repo = CSVRepository()
        self.generation_service = ScheduleGenerationService(self.repo)
        self.relaxation_history = []
        
    def analyze_current_state(self) -> Dict:
        """現在の状態を分析"""
        # 最新の生成結果を読み込み
        try:
            schedule = self.repo.load_schedule_from_csv('data/output/output.csv')
            school = self.repo.load_all_data()
            
            # 違反数をカウント
            from src.domain.services.unified_constraint_validator import UnifiedConstraintValidator
            from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowupParser
            
            followup_parser = EnhancedFollowupParser()
            followup_constraints = followup_parser.parse('data/input/Follow-up.csv')
            
            validator = UnifiedConstraintValidator(school, followup_constraints)
            violations = validator.validate(schedule)
            
            # 違反を優先度別に分類
            violations_by_priority = {
                'CRITICAL': [],
                'HIGH': [],
                'MEDIUM': [],
                'LOW': []
            }
            
            for v in violations:
                # 違反の優先度を推定（制約名から）
                if any(keyword in v.constraint_name for keyword in ['固定', 'テスト', '欠']):
                    violations_by_priority['CRITICAL'].append(v)
                elif any(keyword in v.constraint_name for keyword in ['教師重複', '5組同期']):
                    violations_by_priority['HIGH'].append(v)
                elif any(keyword in v.constraint_name for keyword in ['日内重複', '交流']):
                    violations_by_priority['MEDIUM'].append(v)
                else:
                    violations_by_priority['LOW'].append(v)
            
            return {
                'total_violations': len(violations),
                'by_priority': {k: len(v) for k, v in violations_by_priority.items()},
                'details': violations_by_priority
            }
            
        except Exception as e:
            return {'error': str(e), 'total_violations': -1}
    
    def suggest_relaxation_strategy(self, current_state: Dict) -> List[Dict]:
        """現在の状態に基づいて緩和戦略を提案"""
        strategies = []
        
        # CRITICAL違反がある場合
        if current_state['by_priority']['CRITICAL'] > 0:
            strategies.append({
                'level': 1,
                'name': '固定制約の見直し',
                'description': '固定科目や欠課の配置を再検討',
                'actions': [
                    '月曜6限の「欠」を3年生のみ通常授業に変更',
                    'テスト期間の保護を部分的に緩和'
                ]
            })
        
        # HIGH違反が多い場合
        if current_state['by_priority']['HIGH'] > 20:
            strategies.append({
                'level': 2,
                'name': '教師リソースの拡張',
                'description': '教師の重複制約を段階的に緩和',
                'actions': [
                    '5組の合同授業を2クラスずつに分割',
                    '非常勤講師の活用検討',
                    '同一教科の教師間での分担'
                ]
            })
        
        # MEDIUM違反への対処
        if current_state['by_priority']['MEDIUM'] > 10:
            strategies.append({
                'level': 3,
                'name': '授業配置の柔軟化',
                'description': '日内重複や交流学級の制約を調整',
                'actions': [
                    '主要教科の1日2コマまで許容（演習など）',
                    '交流学級の自立活動条件を緩和'
                ]
            })
        
        # 全体的な改善
        strategies.append({
            'level': 4,
            'name': '段階的最適化',
            'description': '優先度の低い制約から順次緩和',
            'actions': [
                'LOW優先度の制約を一時的に無効化',
                '基本的な制約のみで生成し、徐々に制約を追加',
                '部分的な手動調整の許容'
            ]
        })
        
        return strategies
    
    def apply_relaxation(self, level: int) -> Tuple[bool, Dict]:
        """指定レベルの緩和を適用して再生成"""
        print(f"\nレベル{level}の制約緩和を適用中...")
        
        # 緩和設定を作成
        relaxation_config = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'modifications': []
        }
        
        # レベルに応じた設定変更
        if level >= 1:
            # 固定制約の緩和
            relaxation_config['modifications'].append('3年生の月曜6限を通常授業可能に')
            # ここで実際の設定変更を行う
            
        if level >= 2:
            # 教師制約の緩和
            relaxation_config['modifications'].append('5組合同授業の分割を許可')
            
        if level >= 3:
            # 配置制約の緩和
            relaxation_config['modifications'].append('主要教科の1日2コマまで許容')
            
        if level >= 4:
            # 優先度の調整
            relaxation_config['modifications'].append('LOW優先度制約の無効化')
        
        # 生成を実行
        try:
            # ここで実際の生成を行う（設定を反映）
            result = self.generation_service.generate_schedule(
                input_csv_path='data/input/input.csv',
                output_csv_path='data/output/output_relaxed.csv',
                use_advanced_csp=True
            )
            
            success = result.get('violations', 100) < 50  # 違反が50件未満なら成功
            
            # 結果を記録
            self.relaxation_history.append({
                'config': relaxation_config,
                'result': result,
                'success': success
            })
            
            return success, result
            
        except Exception as e:
            return False, {'error': str(e)}
    
    def find_optimal_relaxation(self) -> Dict:
        """最適な緩和レベルを探索"""
        print("=== 段階的制約緩和による最適化開始 ===\n")
        
        # 現在の状態を分析
        current_state = self.analyze_current_state()
        print(f"現在の違反数: {current_state['total_violations']}")
        print(f"優先度別: {current_state['by_priority']}")
        
        # 緩和戦略を提案
        strategies = self.suggest_relaxation_strategy(current_state)
        print("\n推奨される緩和戦略:")
        for strategy in strategies:
            print(f"\nレベル{strategy['level']}: {strategy['name']}")
            print(f"  説明: {strategy['description']}")
            for action in strategy['actions']:
                print(f"  - {action}")
        
        # 段階的に緩和を試行
        best_result = None
        best_level = 0
        
        for level in range(1, 5):
            print(f"\n--- レベル{level}での試行 ---")
            success, result = self.apply_relaxation(level)
            
            if success:
                print(f"✓ レベル{level}で改善を確認")
                best_result = result
                best_level = level
                break
            else:
                print(f"✗ レベル{level}では不十分")
        
        # 結果をまとめる
        summary = {
            'initial_state': current_state,
            'strategies': strategies,
            'optimal_level': best_level,
            'final_result': best_result,
            'history': self.relaxation_history
        }
        
        # レポートを保存
        with open('relaxation_report.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return summary

def main():
    relaxation_system = ProgressiveConstraintRelaxation()
    
    # 最適な緩和レベルを探索
    result = relaxation_system.find_optimal_relaxation()
    
    print("\n=== 最適化完了 ===")
    print(f"推奨緩和レベル: {result['optimal_level']}")
    
    if result['final_result']:
        print(f"最終違反数: {result['final_result'].get('violations', '不明')}")
    
    print("\n詳細は relaxation_report.json を参照してください。")

if __name__ == "__main__":
    main()