# 統合CSVリポジトリ

## 概要
`csv_repository.py`は、CSV形式でのデータ入出力を担当する統合リポジトリです。
以前は3つの別々のファイルに分かれていた機能を1つに統合し、オプション引数で機能を切り替えられるようになりました。

## 統合された旧ファイル
- `csv_repository.py` (ベース機能)
- `csv_repository_enhanced.py` (拡張版)
- `csv_repository_with_support_hours.py` (支援時数対応版)

## 使用方法

### 基本的な使用（従来の機能のみ）
```python
repo = CSVScheduleRepository(base_path)
```

### 拡張機能を有効化
```python
repo = CSVScheduleRepository(
    base_path,
    use_enhanced_features=True  # 5組時数表記、教師マッピングなど
)
```

### 支援時数機能を有効化
```python
repo = CSVScheduleRepository(
    base_path,
    use_support_hours=True  # 特別支援時数表記
)
```

### 全機能を有効化
```python
repo = CSVScheduleRepository(
    base_path,
    use_enhanced_features=True,
    use_support_hours=True
)
```

## 機能詳細

### 基本機能
- スケジュールのCSV入出力
- 希望時間割の読み込み
- 標準時数データの管理
- 教師不在チェック

### 拡張機能 (use_enhanced_features=True)
- 5組時数表記対応
- セル別配置禁止（「非○○」記法）のサポート
- 教師マッピングリポジトリとの連携
- Grade5Unitの高度な同期処理
- 交流学級の自動同期

### 支援時数機能 (use_support_hours=True)
- 特別支援学級の時数コード表記
- Grade5UnitEnhancedの使用
- SpecialSupportHourMappingによる時数管理

## 主要メソッド

### save_schedule()
スケジュールをCSVファイルに保存します。
- 拡張機能有効時: 5組の時数表記を使用
- 支援時数機能有効時: 特別な時数コードで表示

### load_desired_schedule()
希望時間割をCSVから読み込みます。
- 拡張機能有効時: より高度な解析と同期処理を実行

### save_teacher_schedule()
教師別時間割を保存します。
- 拡張機能有効時: 会議情報の行も追加

## 注意事項
- 機能フラグは初期化時にのみ設定可能です
- 複数の機能を同時に有効化することができます
- 後方互換性を維持しているため、既存のコードは変更不要です