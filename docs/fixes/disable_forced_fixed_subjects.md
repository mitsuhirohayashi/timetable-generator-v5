# 固定科目の強制配置無効化の修正内容

## 概要
システムがinput.csvの内容を無視して固定科目（欠、YT、学、道、学総、総合など）を強制的に配置する問題を修正しました。

## 修正内容

### 1. fixed_subject_protection_policy.py
- **CRITICAL_FIXED_SLOTS**を空の辞書に変更
  - 以前: 月曜6限=欠、火水金6限=YTなどが定義されていた
  - 修正後: 空の辞書（強制配置ルールなし）

- **enforce_critical_slots()メソッド**を無効化
  - 以前: 固定科目を強制的に配置していた
  - 修正後: 何もせず0を返す（input.csvの内容を尊重）

- **validate_schedule()メソッド**を無効化
  - 以前: 固定科目の配置を検証していた
  - 修正後: 常に空のリストを返す（違反なし）

### 2. csp_orchestrator.py
- **_enforce_and_lock_fixed_subjects()メソッド**から強制配置をコメントアウト
  - 既存の固定科目のロック機能は保持（保護機能は維持）
  - policy.enforce_critical_slots()の呼び出しを削除

### 3. input_data_corrector.py
- **correct_input_schedule()メソッド**から強制配置をコメントアウト
  - _enforce_fixed_subjects()の呼び出しを無効化
  - テスト期間の保護は維持

## 修正の効果

### 修正前の動作
- システムが勝手に月曜6限を「欠」に変更
- 火水金の6限を「YT」に変更
- input.csvの内容を無視して固定科目を強制配置

### 修正後の動作
- input.csvに記載された内容をそのまま尊重
- 既存の固定科目は変更から保護される（保護機能は維持）
- システムが勝手に科目を追加・変更しない

## 注意事項
- 固定科目の**保護機能**は維持されています
- input.csvに既に配置されている固定科目は変更されません
- この修正により、学校側が柔軟に時間割を設定できるようになります

## 関連ファイル
1. `src/domain/policies/fixed_subject_protection_policy.py`
2. `src/domain/services/csp_orchestrator.py`
3. `src/domain/services/input_data_corrector.py`