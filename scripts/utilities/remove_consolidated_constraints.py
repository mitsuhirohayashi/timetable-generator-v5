#!/usr/bin/env python3
"""
未使用の統合制約システムを削除するスクリプト

consolidated制約システムは作成されたが実際には使用されていないため、
混乱を避けるために削除します。
"""

import os
import shutil
from pathlib import Path

def main():
    """メイン処理"""
    base_dir = Path(__file__).resolve().parent.parent.parent
    
    # 削除対象
    targets_to_remove = [
        # consolidatedディレクトリ
        base_dir / "src/domain/constraints/consolidated",
        
        # consolidated constraint loader
        base_dir / "src/infrastructure/config/consolidated_constraint_loader.py",
        
        # 関連ドキュメント（もしあれば）
        base_dir / "docs/consolidated_constraints_design.md",
    ]
    
    print("=== 未使用の統合制約システムの削除 ===")
    print("\n以下のファイル/ディレクトリを削除します：")
    
    removed_count = 0
    
    for target in targets_to_remove:
        if target.exists():
            print(f"  - {target.relative_to(base_dir)}")
            
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            
            removed_count += 1
    
    if removed_count == 0:
        print("\n削除対象が見つかりませんでした。")
    else:
        print(f"\n{removed_count}個のファイル/ディレクトリを削除しました。")
        print("\n現在の制約システム（個別制約ファイル）は引き続き使用されます。")
        
        # 削除後の確認
        print("\n=== 削除後の制約ファイル一覧 ===")
        constraints_dir = base_dir / "src/domain/constraints"
        constraint_files = sorted([f for f in constraints_dir.glob("*.py") if f.name not in ["__init__.py", "__pycache__"]])
        
        print(f"制約ファイル数: {len(constraint_files)}")
        for f in constraint_files:
            print(f"  - {f.name}")

if __name__ == "__main__":
    main()