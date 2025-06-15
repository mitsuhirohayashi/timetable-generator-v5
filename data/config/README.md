# 設定ファイル構成

このディレクトリには、時間割生成システムの共通設定ファイルが格納されています。

## ファイル一覧

### 基本設定
- **base_timetable.csv** - 標準時数データ（各クラス・教科の週あたり授業時間数）
- **basics.csv** - 各種制約条件の定義

### 教科・クラス定義
- **subject_abbreviations.csv** - 教科略号と正式名称の対応表
- **valid_subjects.csv** - 有効な教科のリストと種別
- **class_definitions.csv** - クラスの定義（通常学級、特別支援学級、交流学級）
- **system_constants.csv** - システム定数（有効曜日、時限、クラス番号など）

### 教員・担当情報
- **teacher_subject_mapping.csv** - 教員と担当教科・クラスの対応表
- **teacher_subject_mapping_notes.txt** - 5組国語の特記事項
- **default_teacher_mapping.csv** - 教科ごとのデフォルト教員名

### 制約・ルール
- **fixed_subjects.csv** - 固定教科のリスト（移動・削除不可）
- **time_constraints.csv** - 時間制約（月曜6限は欠など）
- **constraint_priorities.csv** - 制約の優先順位

### 会議・特別ルール
- **meeting_members.csv** - 会議・委員会のメンバー情報
- **non_regular_teacher_slots.csv** - 非常勤講師の授業可能時限
- **exchange_class_mapping.csv** - 交流学級と親学級の対応表
- **jiritsu_rules.csv** - 自立授業の特別ルール

## 使用方法

これらのファイルは、システム起動時に自動的に読み込まれます。
設定を変更する場合は、該当するCSVファイルを編集してください。

### 注意事項
- CSVファイルはUTF-8エンコーディングで保存してください
- ヘッダー行は変更しないでください
- 各ファイルの形式を維持してください

### 毎週の個別データ
毎週の個別データ（欠席教員情報など）は `data/input/` フォルダに格納されます：
- **input.csv** - 初期時間割（希望時間割）
- **Follow-up.csv** - 週次の調整要望（教員不在、特別要望など）