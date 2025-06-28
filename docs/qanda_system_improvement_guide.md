# 📚 QA管理システム改善ガイド

## 概要

QA.txt管理システムを大幅に改善し、以下の機能を実装しました：

1. **ステータス管理**: 未回答/解決済み/恒久ルール/アーカイブ
2. **視覚的フォーマット**: 絵文字とセクション分けによる見やすい表示
3. **自動整理機能**: 古い質問の自動アーカイブ
4. **メタデータ管理**: JSON形式での詳細情報保存
5. **優先度管理**: 緊急/高/中/低の4段階
6. **カテゴリー分類**: 質問の種類別整理
7. **検索機能**: キーワードやカテゴリーでの検索

## 新しいファイル構成

```
QandA/
├── QA.txt                  # メインの質問管理ファイル（視覚的フォーマット）
├── qa_metadata.json        # 質問の詳細メタデータ
├── QA_backup_*.txt         # 自動バックアップ
└── README.md               # 既存の説明ファイル
```

## 主な改善点

### 1. 視覚的に見やすいフォーマット

新しいQA.txtは以下のセクションで構成：

- **🔴 未回答の質問**: 最優先で対応が必要な質問
- **✅ 解決済みの質問**: 履歴として参照可能
- **📌 恒久的ルール**: システムが常に参照する重要ルール
- **📦 アーカイブ**: 古い解決済み質問（詳細はメタデータ参照）

### 2. ステータス管理

各質問は以下のステータスを持ちます：

| ステータス | 説明 | 表示場所 |
|----------|------|---------|
| 未回答 | 回答待ちの質問 | 🔴 未回答セクション |
| 解決済み | 回答済みの質問 | ✅ 解決済みセクション |
| 恒久ルール | 常に適用されるルール | 📌 恒久的ルールセクション |
| アーカイブ | 30日以上経過した解決済み | 📦 アーカイブ（メタデータのみ） |

### 3. 優先度管理

質問には優先度を設定できます：

- 🔴 緊急 (CRITICAL): 即座に対応が必要
- 🟡 高 (HIGH): 早急な対応が必要
- 🟢 中 (MEDIUM): 通常の優先度
- ⚪ 低 (LOW): 時間がある時に対応

### 4. 自動整理機能

- 30日以上経過した解決済み質問は自動的にアーカイブ
- アーカイブされた質問はメタデータに保存され、検索可能
- QA.txtは常に最新の情報のみを表示

## 使用方法

### 1. 新しい質問の追加

```python
from src.application.services.qanda_service_improved import ImprovedQandAService, QuestionPriority

service = ImprovedQandAService()

# 高優先度の質問を追加
q_id = service.add_question(
    question="井上先生が同時に複数クラスを教えています。どうすればよいですか？",
    priority=QuestionPriority.HIGH,
    category="教師配置",
    context="制約違反が発生しました"
)
```

### 2. 質問への回答

```python
# 質問に回答
service.answer_question(
    question_id=q_id,
    answer="同じ時間に複数クラスは教えられません。どちらかのクラスの時間を変更してください。"
)
```

### 3. 恒久的ルールへの昇格

```python
# 重要な回答を恒久的ルールに昇格
service.promote_to_permanent(question_id=q_id)
```

### 4. エラーからの自動質問生成

```python
# 制約違反から自動的に質問を生成
q_id = service.generate_question_from_error(
    error_type="teacher_conflict",
    error_details={
        'teacher': '井上先生',
        'time_slot': '火曜5限',
        'classes': ['2-1', '2-2']
    }
)
```

### 5. 質問の検索

```python
# キーワードで検索
results = service.search_questions("数学")

# カテゴリーで検索
teacher_questions = service.get_questions_by_category("教師配置")

# ステータスで検索
unanswered = service.get_questions_by_status(QuestionStatus.UNANSWERED)
```

## 移行手順

### 1. 既存のQA.txtのバックアップ

```bash
cp QandA/QA.txt QandA/QA_original_backup.txt
```

### 2. 変換スクリプトの実行

```bash
python3 scripts/utilities/convert_qa_format.py
```

### 3. 新しいQA.txtの確認

```bash
cat QandA/QA_new.txt
```

### 4. 既存ファイルの置き換え

```bash
mv QandA/QA_new.txt QandA/QA.txt
```

### 5. 既存のqanda_service.pyの更新

```python
# src/application/services/qanda_service.py を
# src/application/services/qanda_service_improved.py で置き換える
```

## システムへの統合

### 1. 時間割生成前のチェック

```python
# main.pyやgenerate_schedule.pyに追加
service = ImprovedQandAService()
unanswered = service.get_questions_by_status(QuestionStatus.UNANSWERED)

if unanswered:
    print(f"⚠️ {len(unanswered)} 件の未回答の質問があります")
    for q in unanswered[:5]:  # 最初の5件を表示
        print(f"  {q.priority.value} {q.question}")
    
    # 未回答の質問がある場合は警告
```

### 2. エラー発生時の自動質問追加

```python
# 制約違反やエラー処理部分に追加
try:
    # 時間割生成処理
    pass
except ConstraintViolation as e:
    # エラーから質問を自動生成
    service.generate_question_from_error(
        error_type="constraint_violation",
        error_details={
            'constraint_name': str(type(e).__name__),
            'description': str(e)
        }
    )
```

### 3. 定期的なメンテナンス

```python
# 週次または月次で実行
service = ImprovedQandAService()

# 古い質問をアーカイブ
archived_count = service.archive_old_questions(days=30)
print(f"{archived_count} 件の質問をアーカイブしました")

# 統計情報を表示
stats = service.get_statistics()
print(f"総質問数: {stats['total']}")
print(f"未回答: {stats['unanswered']}")
```

## 注意事項

1. **バックアップ**: QA.txtを編集する前は必ずバックアップが作成されます
2. **互換性**: 新しいシステムは既存のQA.txtを自動的に新フォーマットに変換できます
3. **メタデータ**: qa_metadata.jsonには全ての詳細情報が保存されます
4. **手動編集**: QA.txtを手動で編集する場合は、フォーマットを維持してください

## まとめ

この改善により、QA管理システムは以下のメリットを提供します：

- ✅ 未回答の質問が一目で分かる
- ✅ 重要なルールが常に参照可能
- ✅ 古い情報は自動的に整理
- ✅ エラーから自動的に質問を生成
- ✅ 視覚的に見やすく、管理しやすい

これにより、時間割生成システムの継続的な改善がより効率的に行えるようになります。