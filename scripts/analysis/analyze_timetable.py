import pandas as pd

# データ読み込み
df = pd.read_csv('data/output/output.csv')

# ヘッダー処理
days = df.iloc[0, 1:].values
periods = df.iloc[1, 1:].values

# 空行を除外してクラス名と時間割データを取得
valid_rows = ~df.iloc[2:, 0].isna()
df_valid = df.iloc[2:][valid_rows].reset_index(drop=True)

# クラス名をキーとした辞書作成
timetable = {}
for i, class_name in enumerate(df_valid.iloc[:, 0]):
    if not pd.isna(class_name):
        timetable[class_name] = df_valid.iloc[i, 1:].values

print('3. 交流学級と親学級の同期チェック:')
print()

# 交流学級ペア
exchange_pairs = [
    ('1年6組', '1年1組'),
    ('1年7組', '1年2組'),
    ('2年6組', '2年3組'),
    ('2年7組', '2年2組'),
    ('3年6組', '3年3組'),
    ('3年7組', '3年2組')
]

sync_errors = []
for exchange_class, parent_class in exchange_pairs:
    if exchange_class in timetable and parent_class in timetable:
        exchange_data = timetable[exchange_class]
        parent_data = timetable[parent_class]
        
        for i in range(len(exchange_data)):
            ex_subject = str(exchange_data[i])
            par_subject = str(parent_data[i])
            
            # 自立活動の時以外は同じであるべき
            if ex_subject != '自立' and ex_subject != par_subject:
                day = days[i]
                period = periods[i]
                sync_errors.append(f'  - {exchange_class}と{parent_class}: {day}曜{period}限 - {exchange_class}={ex_subject}, {parent_class}={par_subject}')

if sync_errors:
    for error in sync_errors:
        print(error)
else:
    print('  交流学級の同期エラーなし')

print()
print('4. 5組（1年5組、2年5組、3年5組）の同期チェック:')
print()

# 5組のクラス
grade5_classes = ['1年5組', '2年5組', '3年5組']
grade5_data = {cls: timetable.get(cls, []) for cls in grade5_classes if cls in timetable}

grade5_sync_errors = []
if len(grade5_data) == 3:
    base_class = '1年5組'
    base_data = grade5_data[base_class]
    
    for other_class in ['2年5組', '3年5組']:
        other_data = grade5_data[other_class]
        
        for i in range(len(base_data)):
            if base_data[i] != other_data[i]:
                day = days[i]
                period = periods[i]
                grade5_sync_errors.append(f'  - {base_class}と{other_class}: {day}曜{period}限 - {base_class}={base_data[i]}, {other_class}={other_data[i]}')

if grade5_sync_errors:
    for error in grade5_sync_errors:
        print(error)
else:
    print('  5組の同期エラーなし')

print()
print('5. 特殊な制約チェック:')
print()

# 月曜6限は全クラス「欠」であるべき
monday_6th_errors = []
for class_name, data in timetable.items():
    if data[5] != '欠':  # 月曜6限のインデックスは5
        monday_6th_errors.append(f'  - {class_name}: 月曜6限が「{data[5]}」（「欠」であるべき）')

if monday_6th_errors:
    print('月曜6限エラー:')
    for error in monday_6th_errors:
        print(error)
else:
    print('  月曜6限制約OK')

# 火水金の6限はYTであるべき
yt_errors = []
yt_positions = [11, 17, 29]  # 火6, 水6, 金6のインデックス
yt_days = ['火', '水', '金']
for class_name, data in timetable.items():
    for i, pos in enumerate(yt_positions):
        if data[pos] != 'YT':
            yt_errors.append(f'  - {class_name}: {yt_days[i]}曜6限が「{data[pos]}」（「YT」であるべき）')

if yt_errors:
    print()
    print('YT制約エラー:')
    for error in yt_errors:
        print(error)
else:
    print('  YT制約OK')

# 自立活動時の親学級制約チェック
print()
print('自立活動時の親学級制約チェック:')
jiritsu_errors = []
for exchange_class, parent_class in exchange_pairs:
    if exchange_class in timetable and parent_class in timetable:
        exchange_data = timetable[exchange_class]
        parent_data = timetable[parent_class]
        
        for i in range(len(exchange_data)):
            if str(exchange_data[i]) == '自立':
                par_subject = str(parent_data[i])
                if par_subject not in ['数', '英', 'nan', '']:
                    day = days[i]
                    period = periods[i]
                    jiritsu_errors.append(f'  - {exchange_class}が自立の時、{parent_class}は{par_subject}（数か英であるべき）: {day}曜{period}限')

if jiritsu_errors:
    for error in jiritsu_errors:
        print(error)
else:
    print('  自立活動時の親学級制約OK')