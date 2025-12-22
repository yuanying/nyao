# レイヤー5: デプロイメントレイヤー（Deployment Layer）

## 概要

アプリケーションのコンテナ化、Kubernetes環境へのデプロイ設定を提供します。

## 実装優先度

**最終** - すべての機能実装後にデプロイ設定を行う

## 依存関係

- **依存先**: すべてのアプリケーションコード
- **依存元**: なし（最上層レイヤー）

## コンポーネント

### 1. Dockerfile

#### 目的

アプリケーションをDockerコンテナとしてパッケージ化します。

#### Dockerfile

```dockerfile
# ベースイメージ
FROM python:3.12-slim

# 作業ディレクトリ
WORKDIR /app

# uvのインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 依存関係ファイルのコピー
COPY pyproject.toml uv.lock ./

# 依存関係のインストール
RUN uv sync --frozen --no-dev

# アプリケーションコードのコピー
COPY nyao/ ./nyao/

# 非rootユーザーの作成
RUN useradd -m -u 1000 nyao && \
    chown -R nyao:nyao /app

# 非rootユーザーに切り替え
USER nyao

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# アプリケーション起動
CMD ["uv", "run", "python", "-m", "nyao.main"]
```

#### マルチステージビルド（最適化版）

```dockerfile
# ビルドステージ
FROM python:3.12-slim AS builder

WORKDIR /app

# uvのインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 依存関係のインストール
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 実行ステージ
FROM python:3.12-slim

WORKDIR /app

# uvのコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 依存関係のコピー
COPY --from=builder /app/.venv /app/.venv

# アプリケーションコードのコピー
COPY nyao/ ./nyao/

# 非rootユーザーの作成
RUN useradd -m -u 1000 nyao && \
    chown -R nyao:nyao /app

USER nyao

# 環境変数（Pythonのバッファリング無効化）
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["uv", "run", "python", "-m", "nyao.main"]
```

#### .dockerignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt
.pytest_cache/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Git
.git/
.gitignore

# Documentation
*.md
docs/

# Tests
tests/
.coverage

# CI/CD
.github/

# Environment
.env
.env.local

# Kubernetes
k8s/
```

---

### 2. Kubernetes Manifests

#### 目的

Kubernetes環境でアプリケーションをデプロイするための設定を提供します。

#### ディレクトリ構成

```
k8s/
├── base/
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── secret.yaml
│   └── configmap.yaml
└── overlays/
    ├── development/
    │   └── kustomization.yaml
    └── production/
        └── kustomization.yaml
```

#### namespace.yaml

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: nyao
  labels:
    app: nyao
```

#### secret.yaml

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: nyao-secrets
  namespace: nyao
type: Opaque
stringData:
  SLACK_BOT_TOKEN: "xoxb-your-bot-token"
  SLACK_APP_TOKEN: "xapp-your-app-token"
  OPENAI_API_KEY: "sk-your-openai-key"
  # または
  # ANTHROPIC_API_KEY: "sk-ant-your-anthropic-key"
```

> **注意**: 実際の運用では、`stringData`ではなく外部のシークレット管理ツール（Sealed Secrets、External Secrets等）を使用することを推奨します。

#### configmap.yaml

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nyao-config
  namespace: nyao
data:
  SLACK_CHANNEL_IDS: "C123456,C789012"
  LITELLM_MODEL: "gpt-4"
  BOT_RESPONSE_DELAY: "60"
  BOT_PERSONA: "友達のようなカジュアルな口調で話す"
  LOG_LEVEL: "INFO"
```

#### deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nyao
  namespace: nyao
  labels:
    app: nyao
spec:
  replicas: 1  # Phase 1ではシングルインスタンス
  selector:
    matchLabels:
      app: nyao
  template:
    metadata:
      labels:
        app: nyao
    spec:
      containers:
      - name: nyao
        image: nyao:latest  # 実際のイメージタグに置き換え
        imagePullPolicy: IfNotPresent

        # 環境変数（ConfigMapとSecretから）
        envFrom:
        - configMapRef:
            name: nyao-config
        - secretRef:
            name: nyao-secrets

        # リソース制限
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"

        # ヘルスチェック
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import sys; sys.exit(0)"
          initialDelaySeconds: 30
          periodSeconds: 60
          timeoutSeconds: 10
          failureThreshold: 3

        readinessProbe:
          exec:
            command:
            - python
            - -c
            - "import sys; sys.exit(0)"
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3

      # セキュリティ設定
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000

      # 再起動ポリシー
      restartPolicy: Always
```

#### Kustomization（開発環境）

```yaml
# k8s/overlays/development/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: nyao-dev

bases:
  - ../../base

namePrefix: dev-

images:
  - name: nyao
    newName: nyao
    newTag: dev-latest

configMapGenerator:
  - name: nyao-config
    behavior: merge
    literals:
      - LOG_LEVEL=DEBUG
```

#### Kustomization（本番環境）

```yaml
# k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: nyao

bases:
  - ../../base

images:
  - name: nyao
    newName: your-registry/nyao
    newTag: v1.0.0

replicas:
  - name: nyao
    count: 1

configMapGenerator:
  - name: nyao-config
    behavior: merge
    literals:
      - LOG_LEVEL=INFO
```

---

### 3. デプロイスクリプト

#### 目的

デプロイを自動化し、一貫性のあるデプロイプロセスを提供します。

#### deploy.sh

```bash
#!/bin/bash
set -e

# カラー出力
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 環境変数
ENVIRONMENT=${1:-development}
NAMESPACE="nyao"

if [ "$ENVIRONMENT" = "development" ]; then
    NAMESPACE="nyao-dev"
fi

echo -e "${GREEN}=== Nyao Deployment ===${NC}"
echo -e "Environment: ${YELLOW}${ENVIRONMENT}${NC}"
echo -e "Namespace: ${YELLOW}${NAMESPACE}${NC}"

# Docker イメージのビルド
echo -e "\n${GREEN}Building Docker image...${NC}"
docker build -t nyao:${ENVIRONMENT}-latest .

# Kubernetes マニフェストの適用
echo -e "\n${GREEN}Applying Kubernetes manifests...${NC}"
kubectl apply -k k8s/overlays/${ENVIRONMENT}

# デプロイメントの監視
echo -e "\n${GREEN}Waiting for deployment to complete...${NC}"
kubectl rollout status deployment/nyao -n ${NAMESPACE} --timeout=5m

# Pod の状態確認
echo -e "\n${GREEN}Checking pod status...${NC}"
kubectl get pods -n ${NAMESPACE} -l app=nyao

echo -e "\n${GREEN}Deployment completed successfully!${NC}"
```

#### undeploy.sh

```bash
#!/bin/bash
set -e

ENVIRONMENT=${1:-development}
NAMESPACE="nyao"

if [ "$ENVIRONMENT" = "development" ]; then
    NAMESPACE="nyao-dev"
fi

echo -e "${YELLOW}=== Undeploying Nyao ===${NC}"
echo -e "Environment: ${YELLOW}${ENVIRONMENT}${NC}"
echo -e "Namespace: ${YELLOW}${NAMESPACE}${NC}"

kubectl delete -k k8s/overlays/${ENVIRONMENT}

echo -e "${GREEN}Undeployment completed!${NC}"
```

---

### 4. メインアプリケーション

#### 目的

すべてのコンポーネントを統合し、アプリケーションのエントリーポイントを提供します。

#### nyao/main.py

**NyaoBotクラス**:
- `__init__()`: すべてのコンポーネントを初期化
  - Slack連携: SlackConnectionManager, EventReceiver, MessageSender, ThreadHistoryFetcher
  - LLM連携: LLMConnectionManager, PromptManager, LLMCaller
  - サービス: ResponseJudgeService, ResponseGeneratorService, ContextManagerService, ResponseDelayController
- `start()`: アプリケーションを起動
  - イベントハンドラの登録
  - Slack接続開始
  - クリーンアップループ起動
- `stop()`: アプリケーションを停止
- `_handle_message(event, say)`: メッセージイベントハンドラ
  - メッセージをコンテキストに追加
  - 応答チェックをスケジュール
- `_handle_reaction(event)`: リアクションイベントハンドラ
- `_check_and_respond(message)`: 応答チェックと応答送信
  - 応答判定
  - コンテキスト取得
  - 応答生成
  - 応答送信
- `_cleanup_loop()`: 定期クリーンアップループ（5分ごと）

**main関数**:
- ロギング設定
- NyaoBotインスタンス作成
- シグナルハンドラ設定（SIGTERM, SIGINT）
- アプリケーション起動

---

## 実装タスク

### タスク1: Dockerfile作成

- [ ] `Dockerfile`の作成
- [ ] `.dockerignore`の作成
- [ ] ローカルでのビルドテスト
- [ ] イメージサイズの最適化

### タスク2: Kubernetes Manifests作成

- [ ] `k8s/base/`配下のマニフェスト作成
- [ ] `k8s/overlays/development/`の作成
- [ ] `k8s/overlays/production/`の作成
- [ ] Secret管理の検討

### タスク3: デプロイスクリプト作成

- [ ] `deploy.sh`の作成
- [ ] `undeploy.sh`の作成
- [ ] 実行権限の付与
- [ ] デプロイテスト

### タスク4: メインアプリケーション作成

- [ ] `nyao/main.py`の実装
- [ ] イベントハンドラの統合
- [ ] シグナルハンドリング
- [ ] エラーハンドリング
- [ ] ローカルでの動作テスト

## テスト戦略

### ローカルテスト

```bash
# Dockerビルドテスト
docker build -t nyao:test .

# ローカル実行テスト
docker run --env-file .env nyao:test

# リソース使用量の確認
docker stats
```

### Kubernetesテスト

```bash
# 開発環境デプロイ
./deploy.sh development

# ログ確認
kubectl logs -f -n nyao-dev -l app=nyao

# リソース確認
kubectl top pod -n nyao-dev

# アンデプロイ
./undeploy.sh development
```

## 完了条件

- [ ] Dockerイメージが正常にビルドできること
- [ ] ローカルでコンテナが起動すること
- [ ] Kubernetesにデプロイできること
- [ ] Pod が正常に起動すること
- [ ] ログが正しく出力されること
- [ ] Slack APIに接続できること
- [ ] メッセージの受信・送信が動作すること
- [ ] シグナルハンドリングが動作すること（SIGTERM/SIGINTで正常終了）

## 運用上の注意点

### Secret管理

本番環境では、以下のツールの使用を推奨します：
- **Sealed Secrets**: GitOpsフレンドリーなSecret管理
- **External Secrets Operator**: 外部のシークレット管理サービスとの連携
- **SOPS**: ファイルベースのSecret暗号化

### モニタリング

以下のメトリクスを監視することを推奨します：
- Pod のCPU/メモリ使用率
- 応答時間
- エラー率
- LLM API呼び出し回数とコスト

### ログ管理

ログは標準出力に出力され、Kubernetesのログ収集機能で収集されます：
```bash
# リアルタイムログ
kubectl logs -f -n nyao -l app=nyao

# 過去のログ
kubectl logs -n nyao -l app=nyao --since=1h
```

## 参考資料

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Kustomize Documentation](https://kustomize.io/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
