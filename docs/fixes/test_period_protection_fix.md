# テスト期間保護機能の修正案

## 問題の概要
Follow-up.csvに記載されている「テストなので時間割の変更をしないでください」が機能せず、テスト期間中の時間割が変更されてしまう。

## 根本原因
1. **読み込み順序の問題**: input.csvの内容を読み込んだ後でテスト期間保護を試みている
2. **TestPeriodProtectorの実装不完全**: テスト期間の解析が部分的にしか実装されていない
3. **初期スケジュール生成時の問題**: テスト期間を考慮せずに通常の時間割を配置している

## 解決策

### 1. 即時対応（実装済み）
TestPeriodProtectorの`_load_test_periods`メソッドを修正し、テスト期間を正しく読み込むように改善。

### 2. 推奨される修正
```python
# CSPOrchestratorの修正案
def generate(self, school: School, max_iterations: int = 200,
             initial_schedule: Optional[Schedule] = None) -> Schedule:
    
    # 1. テスト期間情報を最初に読み込む
    protector = TestPeriodProtector()
    test_periods = protector.test_periods
    
    # 2. initial_scheduleを読み込む際、テスト期間はスキップ
    if initial_schedule:
        # テスト期間以外のみ読み込む
        filtered_schedule = self._filter_non_test_periods(initial_schedule, test_periods)
        schedule = filtered_schedule
    else:
        schedule = Schedule()
    
    # 3. テスト期間のセルを事前にロック
    protector.protect_test_periods(schedule, school)
```

### 3. より根本的な解決
input.csv自体にテスト期間の時間割を含めるか、別ファイルで管理する：
- `test_schedule.csv`: テスト期間専用の時間割
- `regular_schedule.csv`: 通常期間の時間割

## 現在の状況
- 月曜1-3限、火曜1-3限、水曜1-2限がテスト期間
- これらの時間は元の内容を保持すべき
- 現在は通常の授業に置き換えられてしまっている

## 次のアクション
1. CSPOrchestratorでテスト期間の事前ロックを実装
2. input.csv読み込み時にテスト期間をスキップする処理を追加
3. テスト期間の明示的な管理方法を検討