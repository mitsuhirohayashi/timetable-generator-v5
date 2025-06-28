#!/usr/bin/env python3
"""テスト期間情報の源泉を特定するデバッグスクリプト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("=== テスト期間情報の源泉調査 ===\n")
    
    # 1. Follow-up.csvの内容を確認
    print("1. Follow-up.csvの内容確認:")
    followup_path = project_root / "data" / "input" / "Follow-up.csv"
    
    if followup_path.exists():
        with open(followup_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # テスト関連の文言を検索
        test_keywords = ["テスト", "test", "技家", "変更をしない"]
        found_test = False
        
        for keyword in test_keywords:
            if keyword in content:
                print(f"  ✓ '{keyword}' が見つかりました")
                found_test = True
                # 該当行を表示
                for line in content.splitlines():
                    if keyword in line:
                        print(f"    → {line.strip()}")
        
        if not found_test:
            print("  ✗ テスト関連の記載は見つかりませんでした")
    else:
        print("  ✗ Follow-up.csvが存在しません")
    
    # 2. パーサーの動作を確認
    print("\n2. パーサーの動作確認:")
    
    # Natural parser
    from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
    natural_parser = NaturalFollowUpParser(followup_path.parent)
    natural_result = natural_parser.parse_file("Follow-up.csv")
    
    if natural_result["test_periods"]:
        print(f"  Natural Parser: {len(natural_result['test_periods'])}件のテスト期間を検出")
        for tp in natural_result["test_periods"]:
            print(f"    - {tp.day}曜 {tp.periods}時限")
    else:
        print("  Natural Parser: テスト期間なし")
    
    # Enhanced parser
    from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
    enhanced_parser = EnhancedFollowUpParser(followup_path.parent)
    enhanced_result = enhanced_parser.parse_file("Follow-up.csv")
    
    if enhanced_result["test_periods"]:
        print(f"  Enhanced Parser: {len(enhanced_result['test_periods'])}件のテスト期間を検出")
        for tp in enhanced_result["test_periods"]:
            print(f"    - {tp.day}曜 {tp.periods}時限: {tp.description}")
    else:
        print("  Enhanced Parser: テスト期間なし")
    
    # 3. DIコンテナ経由のパーサー
    print("\n3. DIコンテナ経由のパーサー確認:")
    from src.infrastructure.di_container import get_followup_parser
    di_parser = get_followup_parser()
    
    test_periods = di_parser.parse_test_periods()
    if test_periods:
        print(f"  DIコンテナ Parser: {len(test_periods)}件のテスト期間を検出")
        for tp in test_periods:
            if hasattr(tp, 'day') and hasattr(tp, 'periods'):
                print(f"    - {tp.day}曜 {tp.periods}時限")
    else:
        print("  DIコンテナ Parser: テスト期間なし")
    
    # 4. キャッシュファイルの確認
    print("\n4. キャッシュ・一時ファイルの確認:")
    
    # 可能性のあるキャッシュ場所
    cache_locations = [
        project_root / "cache",
        project_root / "temp",
        project_root / ".cache",
        project_root / "data" / "cache",
        project_root / "data" / "temp"
    ]
    
    for cache_dir in cache_locations:
        if cache_dir.exists():
            print(f"  ✓ {cache_dir} が存在します")
            # JSONファイルを探す
            json_files = list(cache_dir.glob("*.json"))
            if json_files:
                for jf in json_files:
                    print(f"    - {jf.name}")
        else:
            print(f"  ✗ {cache_dir} は存在しません")
    
    # 5. 結論
    print("\n=== 結論 ===")
    if found_test:
        print("Follow-up.csvにテスト関連の記載があるため、正常な動作です。")
    else:
        print("Follow-up.csvにテスト関連の記載がないにも関わらず、")
        print("テスト期間が検出されている場合は、以下の可能性があります：")
        print("1. パーサーのバグ（正規表現の誤検出）")
        print("2. 古いキャッシュデータの残存")
        print("3. 他のファイルからの読み込み")

if __name__ == "__main__":
    main()