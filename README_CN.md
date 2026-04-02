[English](README.md) | **中文**

# TKE Skill

腾讯云 TKE 容器服务全栈运维 Skill，无需安装 MCP Server，通过 AI Coding Agent 的 Skill 机制直接管理 TKE 集群、操作 K8s 资源、部署 Helm Chart、管理 TCR 镜像仓库。

支持 OpenClaw、CodeBuddy、Claude Code、Gemini CLI 等主流 AI Coding Agent。

## 能力概览

| 类别 | 能力 | 工具 |
|------|------|------|
| 集群管理 | 列出集群、查看状态、节点池管理 | tke_cli.py |
| 集群管理 | 获取 kubeconfig、开启/关闭端点 | tke_cli.py |
| K8s 资源 | 部署 Deployment/Service、查看/删除资源、应用 YAML | k8s_cli.py |
| Pod 操作 | 列出 Pod、查看日志、exec 执行命令、查看资源用量 | k8s_cli.py |
| 排障 | 查看 Events、describe 资源 | k8s_cli.py |
| Helm | 安装/升级/卸载 Chart、查看状态 | k8s_cli.py |
| Context 管理 | 列出/切换/合并 kubeconfig context，多集群管理 | k8s_cli.py |
| RBAC 租户管理 | 创建/列出/删除租户、获取 Token、生成一键安装 Prompt | k8s_cli.py |
| 镜像仓库 | 查询/创建/删除 TCR 实例、命名空间、仓库、镜像 | tke_cli.py |

## 安装依赖

```bash
# 腾讯云 SDK（集群管理 + TCR 镜像仓库）
pip install tencentcloud-sdk-python-tke tencentcloud-sdk-python-tcr

# RBAC 租户管理需要 PyYAML
pip install pyyaml

# K8s 操作需要 kubectl 和 helm（按需安装）
# kubectl: https://kubernetes.io/docs/tasks/tools/
# helm: https://helm.sh/docs/intro/install/
```

## 凭证配置

### 腾讯云凭证（tke_cli.py 使用）

支持两种方式（命令行参数优先级更高）：

**方式一：环境变量（推荐）**
```bash
export TENCENTCLOUD_SECRET_ID=你的SecretId
export TENCENTCLOUD_SECRET_KEY=你的SecretKey
```

**方式二：命令行参数**
```bash
python tke_cli.py clusters --secret-id AKIDxxx --secret-key xxxxx --region ap-guangzhou
```

### Kubeconfig（k8s_cli.py 使用）

支持四级优先级（自动解析）：
1. `--kubeconfig` 参数指定文件路径
2. `KUBECONFIG` 环境变量
3. `~/.kube/config` 默认路径
4. `--cluster-id` + `--region` 自动从 TKE API 获取（闭环，无需手动配置）

## 安装 Skill

将 `SKILL.md`、`tke_cli.py`、`k8s_cli.py` 复制到你的 Agent 对应的 Skills 目录：

### OpenClaw

```bash
mkdir -p skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py skills/tke/
```

### CodeBuddy

```bash
# 项目级（仅当前项目生效，可随 git 分发）
mkdir -p <你的项目>/.codebuddy/skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py <你的项目>/.codebuddy/skills/tke/

# 用户级（全局生效）
mkdir -p ~/.codebuddy/skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py ~/.codebuddy/skills/tke/
```

### Claude Code

```bash
# 项目级
mkdir -p <你的项目>/.claude/skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py <你的项目>/.claude/skills/tke/

# 用户级
mkdir -p ~/.claude/skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py ~/.claude/skills/tke/
```

### 其他 Agent

请参考对应 Agent 的 Skill/Prompt 加载机制，将 `SKILL.md` 作为系统提示词加载，并确保 `tke_cli.py` 和 `k8s_cli.py` 可被 Agent 执行即可。

## 使用方式

安装后在 AI Coding Agent 中：

- **自动触发**：当你提到 TKE、集群、容器服务、K8s、Pod、Helm 等话题时，Agent 会自动使用此 Skill
- **手动触发**：输入 `/tke` 后跟你的需求（部分 Agent 支持）

### 示例对话

```
帮我查一下广州地域的所有集群
巡检一下集群 cls-xxx 的状态
获取集群 cls-xxx 的 kubeconfig
查看 default 命名空间的所有 Pod
部署一个 nginx 到 production 命名空间
查看 Pod my-app-xxx 的日志
用 Helm 安装 bitnami/nginx 到 default 命名空间
查看 TCR 实例列表和镜像仓库
```

## 支持的命令

### 集群管理（tke_cli.py）

| 命令 | 说明 | 关键参数 |
|------|------|---------|
| `clusters` | 查询集群列表 | `--cluster-ids`, `--cluster-type`, `--limit` |
| `cluster-status` | 查询集群状态 | `--cluster-ids` |
| `cluster-level` | 查询集群规格 | `--cluster-id` |
| `endpoints` | 查询集群访问地址 | `--cluster-id` (必填) |
| `endpoint-status` | 查询端点状态 | `--cluster-id` (必填), `--is-extranet` |
| `kubeconfig` | 获取 kubeconfig | `--cluster-id` (必填), `--is-extranet` |
| `node-pools` | 查询节点池 | `--cluster-id` (必填), `--limit` |
| `create-endpoint` | 开启集群访问端点 | `--cluster-id` (必填), `--is-extranet`, `--subnet-id` |
| `delete-endpoint` | 关闭集群访问端点 | `--cluster-id` (必填), `--is-extranet` |

### TCR 镜像仓库（tke_cli.py）

| 命令 | 说明 | 关键参数 |
|------|------|---------|
| `tcr-instances` | 查询 TCR 实例列表 | `--instance-name`, `--all-instances` |
| `tcr-create-instance` | 创建 TCR 实例 | `--registry-name`, `--registry-type` (均必填) |
| `tcr-delete-instance` | 删除 TCR 实例 | `--registry-id` (必填), `--delete-bucket` |
| `tcr-namespaces` | 查询 TCR 命名空间列表 | `--registry-id` (必填), `--namespace-name` |
| `tcr-create-ns` | 创建 TCR 命名空间 | `--registry-id`, `--namespace-name` (均必填), `--is-public` |
| `tcr-delete-ns` | 删除 TCR 命名空间 | `--registry-id`, `--namespace-name` (均必填) |
| `tcr-repos` | 查询镜像仓库列表 | `--registry-id` (必填), `--namespace-name` |
| `tcr-create-repo` | 创建镜像仓库 | `--registry-id`, `--namespace-name`, `--repository-name` (均必填) |
| `tcr-delete-repo` | 删除镜像仓库 | `--registry-id`, `--namespace-name`, `--repository-name` (均必填) |
| `tcr-images` | 查询镜像版本列表 | `--registry-id`, `--namespace-name`, `--repository-name` (均必填) |

### K8s 资源操作（k8s_cli.py）

| 命令 | 说明 | 关键参数 |
|------|------|---------|
| `get` | 查看资源 | `<resource>`, `-n`, `-o`, `-l`, `-A` |
| `describe` | 详细描述资源 | `<resource>`, `[name]`, `-n` |
| `apply` | 应用 YAML | `-f`, `-k`, `--dry-run` |
| `delete` | 删除资源 | `<resource>`, `[name]`, `-f`, `-l` |
| `create` | 快速创建资源 | `<resource>`, `<name>`, `--image` |
| `events` | 查看事件 | `-n`, `-A`, `--field-selector` |

### Pod 操作（k8s_cli.py）

| 命令 | 说明 | 关键参数 |
|------|------|---------|
| `logs` | 查看 Pod 日志 | `<pod>`, `-c`, `--tail`, `--previous`, `-f` |
| `exec` | 在容器中执行命令 | `<pod>`, `-c`, `-- <command>` |
| `top` | 查看资源使用情况 | `pods`/`nodes`, `--sort-by`, `--containers` |

### Context / Kubeconfig 管理（k8s_cli.py）

| 命令 | 说明 | 关键参数 |
|------|------|--------|
| `context-list` | 列出所有 context | `-o name` |
| `context-use` | 切换当前 context | `<context_name>` |
| `context-current` | 显示当前 context | — |
| `kubeconfig-add` | 合并外部 kubeconfig | `--from-file` (必填), `--dry-run` |

### RBAC 租户管理（k8s_cli.py）

| 命令 | 说明 | 关键参数 |
|------|------|--------|
| `rbac-create-tenant` | 创建租户（SA + Role + RoleBinding） | `<tenant_name>`, `--role` (必填), `--rules-file`, `--dry-run` |
| `rbac-list-tenants` | 列出所有管理的租户 | `-A`, `-n` |
| `rbac-delete-tenant` | 删除租户 RBAC 资源 | `<tenant_name>` |
| `rbac-get-token` | 获取租户 Token | `<tenant_name>`, `--duration`, `-o json` |
| `prompt-generate` | 为租户生成一键安装 Prompt | `<tenant_name>`, `--cluster-name`, `--duration` |

### Helm 操作（k8s_cli.py）

| 命令 | 说明 | 关键参数 |
|------|------|--------|
| `helm-install` | 安装 Chart | `<release>`, `<chart>`, `-f`, `--set`, `--atomic` |
| `helm-upgrade` | 升级 Release | `<release>`, `<chart>`, `-f`, `--set`, `--atomic` |
| `helm-uninstall` | 卸载 Release | `<release>`, `--keep-history` |
| `helm-list` | 列出 Release | `-A`, `-o`, `--filter` |
| `helm-status` | 查看 Release 状态 | `<release>`, `--show-resources` |

## 直接使用 CLI

也可以脱离 AI Agent，直接作为命令行工具使用：

```bash
# 集群管理
python tke_cli.py clusters --region ap-guangzhou
python tke_cli.py cluster-status --region ap-guangzhou --cluster-ids cls-xxx
python tke_cli.py kubeconfig --region ap-guangzhou --cluster-id cls-xxx

# TCR 镜像仓库
python tke_cli.py tcr-instances --region ap-guangzhou
python tke_cli.py tcr-create-instance --region ap-guangzhou --registry-name my-tcr --registry-type basic
python tke_cli.py tcr-namespaces --region ap-guangzhou --registry-id tcr-xxx
python tke_cli.py tcr-repos --region ap-guangzhou --registry-id tcr-xxx

# K8s 资源操作
python k8s_cli.py get pods -n default
python k8s_cli.py describe pod my-pod -n default
python k8s_cli.py apply -f deployment.yaml -n production
python k8s_cli.py logs my-pod -n default --tail 100
python k8s_cli.py exec my-pod -n default -- ls /app

# Helm 操作
python k8s_cli.py helm-install my-release bitnami/nginx -n default --wait
python k8s_cli.py helm-list -A

# Context / Kubeconfig 管理
python k8s_cli.py context-list
python k8s_cli.py context-use my-cluster-context
python k8s_cli.py kubeconfig-add --from-file /tmp/new-cluster.kubeconfig

# RBAC 租户管理
python k8s_cli.py rbac-create-tenant zhangsan --role developer -n team-a
python k8s_cli.py rbac-list-tenants -A
python k8s_cli.py rbac-get-token zhangsan -n team-a --duration 8760h
python k8s_cli.py prompt-generate zhangsan -n team-a

# 使用 TKE 集群（自动获取 kubeconfig）
python k8s_cli.py get pods --cluster-id cls-xxx --region ap-guangzhou -n default
```
