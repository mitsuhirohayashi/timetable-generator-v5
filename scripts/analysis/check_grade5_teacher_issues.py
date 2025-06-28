#!/usr/bin/env python3
"""5組の教師配置問題をチェック"""
import csv
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# output.csvを読み込み
with open('data/output/output.csv', 'r', encoding='utf-8-sig') as f:
    lines = list(csv.reader(f))

# 5組の教師配置問題を確認
print('=== 5組の教師配置問題を確認 ===')
print()

days = ['月', '火', '水', '木', '金']
periods = [1, 2, 3, 4, 5, 6]

# teacher_subject_mapping.csvから正しい教師を取得
correct_teachers = {
    '国': '寺田',
    '社': '蒲地',
    '数': '梶永',
    '理': '智田',
    '音': '塚本',
    '美': '金子み',
    '保': '野口',
    '技': '林',
    '家': '金子み',
    '英': '林田',
    '道': '金子み',
    '学': '金子み',
    '総': '金子み',
    'YT': '金子み',
    '学総': '金子み',
    '自立': '金子み',
    '日生': '金子み',
    '作業': '金子み',
    '生単': '金子み',
}

# 5組のデータを抽出して問題を特定
for i, line in enumerate(lines):
    if line and line[0] in ['1年5組', '2年5組', '3年5組']:
        class_name = line[0]
        print(f'\n{class_name}:')
        for j in range(1, 31):  # 月1〜金6
            if j < len(line) and line[j]:
                subject = line[j]
                day_idx = (j - 1) // 6
                period_idx = (j - 1) % 6
                time_slot = f'{days[day_idx]}{periods[period_idx]}'
                
                # 正しい教師を取得
                correct_teacher = correct_teachers.get(subject, '不明')
                
                # 金子み先生以外が担当すべき科目
                if correct_teacher != '金子み' and subject not in ['', '-']:
                    print(f'  {time_slot}: {subject} → {correct_teacher}先生が担当すべき')

# 金子み先生の重複をチェック
print('\n\n=== 金子み先生の教師重複をチェック ===')
kaneko_schedule = {}  # (day, period) -> [classes]

for i, line in enumerate(lines[2:], 2):  # ヘッダーをスキップ
    if not line or not line[0]:
        continue
    
    class_name = line[0]
    
    # 各時限をチェック
    for j in range(1, 31):  # 月1〜金6
        if j < len(line) and line[j]:
            subject = line[j]
            day_idx = (j - 1) // 6
            period_idx = (j - 1) % 6
            time_key = (days[day_idx], periods[period_idx])
            
            # 金子み先生が担当する科目かチェック
            if subject in ['美', '家', '道', '学', '総', 'YT', '学総', '自立', '日生', '作業', '生単']:
                if time_key not in kaneko_schedule:
                    kaneko_schedule[time_key] = []
                kaneko_schedule[time_key].append((class_name, subject))

# 重複をチェック
for (day, period), classes in sorted(kaneko_schedule.items(), key=lambda x: (days.index(x[0][0]), x[0][1])):
    if len(classes) > 1:
        # 5組の合同授業を除外
        grade5_classes = [c for c, s in classes if '5組' in c]
        non_grade5_classes = [c for c, s in classes if '5組' not in c]
        
        if non_grade5_classes and grade5_classes:
            print(f'\n{day}{period}校時: 金子み先生が重複')
            for c, s in classes:
                print(f'  - {c}: {s}')