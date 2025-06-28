#!/usr/bin/env python3
"""テスト期間情報の源泉を追跡するスクリプト"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# ロギング設定
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def trace_test_period_loading():
    """テスト期間の読み込みプロセスを追跡"""
    
    print("=== テスト期間読み込みプロセスの追跡 ===\n")
    
    # 1. CSPオーケストレーターの初期化を追跡
    print("1. CSPオーケストレーターの初期化")
    from src.application.services.csp_orchestrator import CSPOrchestrator
    
    # オリジナルの_load_test_periods関数を保存
    original_load_test_periods = CSPOrchestrator._load_test_periods
    
    # 追跡用のラッパー関数を作成
    def traced_load_test_periods(self):
        print(f"  [TRACE] _load_test_periods called")
        print(f"  [TRACE] followup_parser type: {type(self.followup_parser)}")
        
        # オリジナルの処理を実行
        try:
            test_periods_list = self.followup_parser.parse_test_periods()
            print(f"  [TRACE] parse_test_periods returned: {test_periods_list}")
            
            for i, test_period in enumerate(test_periods_list):
                print(f"  [TRACE] test_period[{i}]: {test_period}")
                if hasattr(test_period, 'day'):
                    print(f"    - day: {test_period.day}")
                if hasattr(test_period, 'periods'):
                    print(f"    - periods: {test_period.periods}")
                if hasattr(test_period, 'description'):
                    print(f"    - description: {test_period.description}")
                    
            # オリジナルの処理を実行
            original_load_test_periods(self)
            
            print(f"  [TRACE] self.test_periods after loading: {self.test_periods}")
            
        except Exception as e:
            print(f"  [TRACE] Exception in _load_test_periods: {e}")
            import traceback
            traceback.print_exc()
    
    # メソッドを置き換え
    CSPOrchestrator._load_test_periods = traced_load_test_periods
    
    # 2. CSPオーケストレーターのインスタンスを作成
    print("\n2. CSPオーケストレーターのインスタンス作成")
    orchestrator = CSPOrchestrator()
    
    print(f"\n最終的なtest_periods: {orchestrator.test_periods}")
    
    # 3. TestPeriodProtectorの初期化も追跡
    print("\n3. TestPeriodProtectorの初期化")
    from src.domain.services.core.test_period_protector import TestPeriodProtector
    
    # オリジナルの_load_test_periods関数を保存
    original_tpp_load_test_periods = TestPeriodProtector._load_test_periods
    
    def traced_tpp_load_test_periods(self):
        print(f"  [TRACE TPP] _load_test_periods called")
        print(f"  [TRACE TPP] followup_parser type: {type(self.followup_parser)}")
        
        try:
            # パーサーを使用してテスト期間を解析
            test_periods = self.followup_parser.parse_test_periods()
            print(f"  [TRACE TPP] parse_test_periods returned: {test_periods}")
            
            for test_period_info in test_periods:
                # TestPeriodオブジェクトから曜日と時限を抽出
                day = test_period_info.day
                for period in test_period_info.periods:
                    print(f"  [TRACE TPP] Adding test period: {day}曜{period}限")
                    # 重複ログを防ぐため、新規追加時のみログ出力
                    if (day, period) not in self.test_periods:
                        print(f"  [TRACE TPP] テスト期間追加: {day}曜{period}限")
                    self.test_periods.add((day, period))
            
            # 特別な指示からテスト期間を抽出（補完処理）
            special_instructions = self.followup_parser.get_special_instructions()
            print(f"  [TRACE TPP] special_instructions: {special_instructions}")
            
        except Exception as e:
            print(f"  [TRACE TPP] Exception: {e}")
            import traceback
            traceback.print_exc()
    
    # メソッドを置き換え
    TestPeriodProtector._load_test_periods = traced_tpp_load_test_periods
    
    # TestPeriodProtectorのインスタンスを作成
    protector = TestPeriodProtector()
    print(f"\nTestPeriodProtector test_periods: {protector.test_periods}")

if __name__ == "__main__":
    trace_test_period_loading()