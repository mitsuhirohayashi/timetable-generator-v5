# CSVScheduleRepositoryリファクタリングガイド

## 概要

巨大化したCSVScheduleRepository（1494行）を責務ごとに分割し、保守性とテスタビリティを向上させました。

## リファクタリング前後の構造

### Before（単一の巨大クラス）
```
CSVScheduleRepository (1494行)
├── スケジュール読み込み
├── スケジュール書き込み
├── 5組同期処理
├── 交流学級同期処理
├── 制約違反検証・修正
├── 教師別時間割生成
└── その他の処理
```

### After（責務ごとに分割）
```
CSVScheduleRepositoryRefactored（ファサード）
├── CSVScheduleReader（読み込み専用）
├── CSVScheduleWriter（書き込み専用）
├── ScheduleSynchronizationService（同期処理）
├── ScheduleValidationService（検証・修正）
├── TeacherScheduleRepository（教師別時間割）
└── TeacherAbsenceLoader（教師不在情報）
```

## 主な改善点

### 1. 単一責任の原則（SRP）
- 各クラスが単一の責務のみを持つ
- クラスのサイズが大幅に削減（最大でも200行程度）

### 2. テスタビリティの向上
- 各コンポーネントを独立してテスト可能
- モックを使用した単体テストが容易

### 3. 保守性の向上
- 変更の影響範囲が限定的
- コードの理解が容易

### 4. 拡張性の向上
- 新しい機能の追加が容易
- 既存コードへの影響を最小限に

## 移行方法

### Step 1: 並行稼働（現在のフェーズ）
```python
# 既存のコードはそのまま動作
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository

# 新しいコードも利用可能
from src.infrastructure.repositories.csv_repository_refactored import CSVScheduleRepositoryRefactored
```

### Step 2: 段階的移行
```python
# 移行フラグを使用
USE_REFACTORED_REPO = True

if USE_REFACTORED_REPO:
    from src.infrastructure.repositories.csv_repository_refactored import CSVScheduleRepositoryRefactored as CSVScheduleRepository
else:
    from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
```

### Step 3: 完全移行
```python
# すべての参照を新しい実装に変更
from src.infrastructure.repositories.csv_repository_refactored import CSVScheduleRepositoryRefactored as CSVScheduleRepository
```

## 使用例

### 基本的な使用方法（互換性を維持）
```python
# リファクタリング前と同じインターフェース
repo = CSVScheduleRepositoryRefactored(base_path=path_config.data_dir)

# スケジュール読み込み
schedule = repo.load_desired_schedule("input.csv", school)

# スケジュール保存
repo.save_schedule(schedule, "output.csv")

# 教師別時間割保存
repo.save_teacher_schedule(schedule, school, "teacher_schedule.csv")
```

### 個別コンポーネントの使用（新機能）
```python
# 読み込みのみ必要な場合
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
reader = CSVScheduleReader()
schedule = reader.read(file_path, school)

# 同期処理のみ必要な場合
from src.infrastructure.services.schedule_synchronization_service import ScheduleSynchronizationService
sync_service = ScheduleSynchronizationService()
sync_service.synchronize_initial_schedule(schedule, school)

# 検証のみ必要な場合
from src.infrastructure.services.schedule_validation_service import ScheduleValidationService
validation_service = ScheduleValidationService()
stats = validation_service.validate_and_fix_schedule(schedule, school)
```

## テスト方法

### 互換性テスト
```bash
python -m pytest tests/test_csv_repository_refactoring.py::TestCSVRepositoryRefactoring
```

### パフォーマンステスト
```bash
python -m pytest tests/test_csv_repository_refactoring.py::TestPerformanceImprovement
```

### 統合テスト
```bash
# 既存の統合テストがそのまま動作することを確認
python main.py generate --max-iterations 200
```

## 注意事項

1. **後方互換性**: 既存のインターフェースは維持されているため、即座の変更は不要
2. **段階的移行**: 急いで全体を移行する必要はない
3. **テスト**: 移行前に十分なテストを実施すること

## 今後の改善案

1. **イベント駆動アーキテクチャ**: スケジュール変更時のイベント発行
2. **キャッシング**: 頻繁にアクセスされるデータのキャッシュ
3. **非同期処理**: 大規模データ処理の非同期化
4. **プラグインシステム**: 新しい制約や処理の動的追加