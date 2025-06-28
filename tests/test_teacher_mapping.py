#!/usr/bin/env python3
"""教師マッピングのテスト"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

# 必要なインポート
from src.infrastructure.config.path_config import path_config
import csv

# teacher_subject_mapping.csvを直接読み込んでテスト
mapping_file = path_config.get_config_path("teacher_subject_mapping.csv")
print(f"マッピングファイル: {mapping_file}")
print(f"ファイル存在: {mapping_file.exists()}")

# CSVを読み込み
mapping = {}
with open(mapping_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['教員名'] and row['教科'] and row['学年'] and row['クラス']:
            grade = int(row['学年'])
            class_num = int(row['クラス'])
            subject = row['教科']
            teacher = row['教員名']
            key = (subject, grade, class_num)
            mapping[key] = teacher
            print(f"  {subject} {grade}-{class_num} → {teacher}")

print(f"\n合計{len(mapping)}件のマッピングを読み込みました")

# テスト: 3年3組の数学
test_key = ("数", 3, 3)
if test_key in mapping:
    print(f"\nテスト: 3年3組の数学 → {mapping[test_key]}")
else:
    print(f"\nテスト: 3年3組の数学 → 見つかりません")