#!/usr/bin/env python3
"""
主要なコードを1つのファイルにまとめるスクリプト
"""

import os
from pathlib import Path

# 含めたい主要ファイル
IMPORTANT_FILES = [
    "main.py",
    "src/application/services/schedule_generation_service.py",
    "src/domain/services/smart_empty_slot_filler_refactored.py",
    "src/domain/constraints/base.py",
    "src/domain/constraints/basic_constraints.py",
    "src/domain/entities/schedule.py",
    "src/domain/entities/school.py",
    "src/infrastructure/repositories/csv_repository.py",
    "src/infrastructure/config/constraint_loader.py",
]

def create_single_file():
    output = []
    output.append("# 時間割生成システム - 主要コード統合版\n")
    output.append("# このファイルは主要なコードを1つにまとめたものです\n\n")
    
    for file_path in IMPORTANT_FILES:
        if os.path.exists(file_path):
            output.append(f"\n{'='*80}")
            output.append(f"\n# ファイル: {file_path}")
            output.append(f"\n{'='*80}\n")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                output.append(content)
                output.append("\n")
    
    # 出力ファイルに書き込み
    with open("timetable_system_combined.py", 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    print("ファイルを統合しました: timetable_system_combined.py")
    
    # ファイルサイズを確認
    size = os.path.getsize("timetable_system_combined.py")
    print(f"ファイルサイズ: {size:,} bytes ({size/1024:.1f} KB)")

if __name__ == "__main__":
    create_single_file()