# アーカイブスクリプト

このディレクトリには、リファクタリングにより統合された古いスクリプトが保存されています。

## 統合後の新しい使い方

### 時間割修正は統合コマンドを使用

```bash
# すべての問題を自動修正（推奨）
python3 main.py fix

# 特定の問題のみ修正
python3 main.py fix --fix-tuesday          # 火曜日の問題のみ
python3 main.py fix --fix-daily-duplicates  # 日内重複のみ
python3 main.py fix --fix-exchange-sync     # 交流学級同期のみ
```

### アーカイブされたスクリプト

#### tuesday_fixes/
火曜日問題に特化した修正スクリプト群：
- `fix_tuesday_conflicts.py`
- `analyze_and_fix_tuesday.py`
- `comprehensive_fix_tuesday.py`
- `smart_tuesday_fix.py`
- `continue_tuesday_fix.py`
- `final_tuesday_fix.py`
- `ultimate_tuesday_fix.py`
- `absolute_tuesday_fix.py`
- `absolute_force_tuesday_fix.py`

これらはすべて `python3 main.py fix --fix-tuesday` に統合されました。

#### comprehensive_fixes/
総合的な修正スクリプト群：
- `comprehensive_fix_all_issues.py`
- `final_comprehensive_fix.py`
- `final_conflict_resolution.py`
- `final_touch_fix.py`
- `integrate_all_fixes.py`
- `ultimate_systematic_fix.py`
- `ultra_comprehensive_fix.py`
- `radical_reconstruction.py`

これらはすべて `python3 main.py fix` に統合されました。

## リファクタリングの成果

1. **重複コードの削除**: 10個以上の類似スクリプトを1つに統合
2. **共通ユーティリティの作成**: `src/domain/utils/schedule_utils.py`
3. **統合サービスの実装**: `src/application/services/schedule_fixer_service.py`
4. **CLIコマンドの追加**: `python3 main.py fix`

## 注意事項

アーカイブされたスクリプトは参考用です。
通常の使用では、統合された新しいコマンドを使用してください。