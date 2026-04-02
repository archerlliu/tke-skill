**English** | [中文](README_CN.md)

# TKE Skill

Tencent Cloud TKE (Tencent Kubernetes Engine) full-stack operations Skill. No MCP Server required — manage TKE clusters, operate K8s resources, deploy Helm Charts, and manage TCR image registries directly through AI Coding Agents.

Supports OpenClaw, CodeBuddy, Claude Code, Gemini CLI, and other mainstream AI Coding Agents.

## Capabilities

| Category | Capabilities | Tool |
|----------|-------------|------|
| Cluster Management | List clusters, view status, node pool management | tke_cli.py |
| Cluster Management | Get kubeconfig, enable/disable endpoints | tke_cli.py |
| K8s Resources | Deploy Deployment/Service, view/delete resources, apply YAML | k8s_cli.py |
| Pod Operations | List Pods, view logs, exec commands, view resource usage | k8s_cli.py |
| Troubleshooting | View Events, describe resources | k8s_cli.py |
| Helm | Install/upgrade/uninstall Charts, view status | k8s_cli.py |
| Context Management | List/switch/merge kubeconfig contexts, multi-cluster management | k8s_cli.py |
| RBAC Tenant Mgmt | Create/list/delete tenants, get tokens, generate onboarding prompts | k8s_cli.py |
| Image Registry | Query/create/delete TCR instances, namespaces, repos, and images | tke_cli.py |

## Prerequisites

```bash
# Tencent Cloud SDK (cluster management + TCR image registry)
pip install tencentcloud-sdk-python-tke tencentcloud-sdk-python-tcr

# RBAC tenant management requires PyYAML
pip install pyyaml

# K8s operations require kubectl and helm (install as needed)
# kubectl: https://kubernetes.io/docs/tasks/tools/
# helm: https://helm.sh/docs/intro/install/
```

## Credential Configuration

### Tencent Cloud Credentials (for tke_cli.py)

Two methods are supported (CLI arguments take precedence):

**Method 1: Environment Variables (Recommended)**
```bash
export TENCENTCLOUD_SECRET_ID=YourSecretId
export TENCENTCLOUD_SECRET_KEY=YourSecretKey
```

**Method 2: CLI Arguments**
```bash
python tke_cli.py clusters --secret-id AKIDxxx --secret-key xxxxx --region ap-guangzhou
```

### Kubeconfig (for k8s_cli.py)

Four-level priority (auto-resolved):
1. `--kubeconfig` argument specifying file path
2. `KUBECONFIG` environment variable
3. `~/.kube/config` default path
4. `--cluster-id` + `--region` to auto-fetch from TKE API (seamless, no manual config needed)

## Install Skill

Copy `SKILL.md`, `tke_cli.py`, and `k8s_cli.py` to the Skills directory of your Agent:

### OpenClaw

```bash
mkdir -p skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py skills/tke/
```

### CodeBuddy

```bash
# Project-level (current project only, can be distributed via git)
mkdir -p <your-project>/.codebuddy/skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py <your-project>/.codebuddy/skills/tke/

# User-level (global)
mkdir -p ~/.codebuddy/skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py ~/.codebuddy/skills/tke/
```

### Claude Code

```bash
# Project-level
mkdir -p <your-project>/.claude/skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py <your-project>/.claude/skills/tke/

# User-level
mkdir -p ~/.claude/skills/tke/
cp SKILL.md tke_cli.py k8s_cli.py ~/.claude/skills/tke/
```

### Other Agents

Refer to your Agent's Skill/Prompt loading mechanism. Load `SKILL.md` as a system prompt and ensure `tke_cli.py` and `k8s_cli.py` are executable by the Agent.

## Usage

After installation, in your AI Coding Agent:

- **Auto-trigger**: The Agent will automatically use this Skill when you mention TKE, clusters, K8s, Pods, Helm, etc.
- **Manual trigger**: Type `/tke` followed by your request (supported by some Agents)

### Example Conversations

```
List all clusters in the Guangzhou region
Check the status of cluster cls-xxx
Get the kubeconfig for cluster cls-xxx
Show all Pods in the default namespace
Deploy nginx to the production namespace
View logs for Pod my-app-xxx
Install bitnami/nginx with Helm to the default namespace
List TCR instances and image repositories
```

## Supported Commands

### Cluster Management (tke_cli.py)

| Command | Description | Key Parameters |
|---------|-------------|----------------|
| `clusters` | List clusters | `--cluster-ids`, `--cluster-type`, `--limit` |
| `cluster-status` | Query cluster status | `--cluster-ids` |
| `cluster-level` | Query cluster specs | `--cluster-id` |
| `endpoints` | Query access endpoints | `--cluster-id` (required) |
| `endpoint-status` | Query endpoint status | `--cluster-id` (required), `--is-extranet` |
| `kubeconfig` | Get kubeconfig | `--cluster-id` (required), `--is-extranet` |
| `node-pools` | Query node pools | `--cluster-id` (required), `--limit` |
| `create-endpoint` | Enable access endpoint | `--cluster-id` (required), `--is-extranet`, `--subnet-id` |
| `delete-endpoint` | Disable access endpoint | `--cluster-id` (required), `--is-extranet` |

### TCR Image Registry (tke_cli.py)

| Command | Description | Key Parameters |
|---------|-------------|----------------|
| `tcr-instances` | List TCR instances | `--instance-name`, `--all-instances` |
| `tcr-create-instance` | Create TCR instance | `--registry-name`, `--registry-type` (both required) |
| `tcr-delete-instance` | Delete TCR instance | `--registry-id` (required), `--delete-bucket` |
| `tcr-namespaces` | List TCR namespaces | `--registry-id` (required), `--namespace-name` |
| `tcr-create-ns` | Create TCR namespace | `--registry-id`, `--namespace-name` (both required), `--is-public` |
| `tcr-delete-ns` | Delete TCR namespace | `--registry-id`, `--namespace-name` (both required) |
| `tcr-repos` | List image repositories | `--registry-id` (required), `--namespace-name` |
| `tcr-create-repo` | Create image repository | `--registry-id`, `--namespace-name`, `--repository-name` (all required) |
| `tcr-delete-repo` | Delete image repository | `--registry-id`, `--namespace-name`, `--repository-name` (all required) |
| `tcr-images` | List image versions | `--registry-id`, `--namespace-name`, `--repository-name` (all required) |

### K8s Resource Operations (k8s_cli.py)

| Command | Description | Key Parameters |
|---------|-------------|----------------|
| `get` | View resources | `<resource>`, `-n`, `-o`, `-l`, `-A` |
| `describe` | Describe resources in detail | `<resource>`, `[name]`, `-n` |
| `apply` | Apply YAML manifests | `-f`, `-k`, `--dry-run` |
| `delete` | Delete resources | `<resource>`, `[name]`, `-f`, `-l` |
| `create` | Quick create resources | `<resource>`, `<name>`, `--image` |
| `events` | View events | `-n`, `-A`, `--field-selector` |

### Pod Operations (k8s_cli.py)

| Command | Description | Key Parameters |
|---------|-------------|----------------|
| `logs` | View Pod logs | `<pod>`, `-c`, `--tail`, `--previous`, `-f` |
| `exec` | Execute command in container | `<pod>`, `-c`, `-- <command>` |
| `top` | View resource usage | `pods`/`nodes`, `--sort-by`, `--containers` |

### Context / Kubeconfig Management (k8s_cli.py)

| Command | Description | Key Parameters |
|---------|-------------|----------------|
| `context-list` | List all contexts | `-o name` |
| `context-use` | Switch current context | `<context_name>` |
| `context-current` | Show current context | — |
| `kubeconfig-add` | Merge external kubeconfig | `--from-file` (required), `--dry-run` |

### RBAC Tenant Management (k8s_cli.py)

| Command | Description | Key Parameters |
|---------|-------------|----------------|
| `rbac-create-tenant` | Create tenant (SA + Role + RoleBinding) | `<tenant_name>`, `--role` (required), `--rules-file`, `--dry-run` |
| `rbac-list-tenants` | List managed tenants | `-A`, `-n` |
| `rbac-delete-tenant` | Delete tenant RBAC resources | `<tenant_name>` |
| `rbac-get-token` | Get tenant Token | `<tenant_name>`, `--duration`, `-o json` |
| `prompt-generate` | Generate onboarding Prompt for tenant | `<tenant_name>`, `--cluster-name`, `--duration` |

### Helm Operations (k8s_cli.py)

| Command | Description | Key Parameters |
|---------|-------------|----------------|
| `helm-install` | Install Chart | `<release>`, `<chart>`, `-f`, `--set`, `--atomic` |
| `helm-upgrade` | Upgrade Release | `<release>`, `<chart>`, `-f`, `--set`, `--atomic` |
| `helm-uninstall` | Uninstall Release | `<release>`, `--keep-history` |
| `helm-list` | List Releases | `-A`, `-o`, `--filter` |
| `helm-status` | View Release status | `<release>`, `--show-resources` |

## Standalone CLI Usage

Can also be used as a standalone CLI tool without any AI Agent:

```bash
# Cluster management
python tke_cli.py clusters --region ap-guangzhou
python tke_cli.py cluster-status --region ap-guangzhou --cluster-ids cls-xxx
python tke_cli.py kubeconfig --region ap-guangzhou --cluster-id cls-xxx

# TCR image registry
python tke_cli.py tcr-instances --region ap-guangzhou
python tke_cli.py tcr-create-instance --region ap-guangzhou --registry-name my-tcr --registry-type basic
python tke_cli.py tcr-namespaces --region ap-guangzhou --registry-id tcr-xxx
python tke_cli.py tcr-repos --region ap-guangzhou --registry-id tcr-xxx

# K8s resource operations
python k8s_cli.py get pods -n default
python k8s_cli.py describe pod my-pod -n default
python k8s_cli.py apply -f deployment.yaml -n production
python k8s_cli.py logs my-pod -n default --tail 100
python k8s_cli.py exec my-pod -n default -- ls /app

# Helm operations
python k8s_cli.py helm-install my-release bitnami/nginx -n default --wait
python k8s_cli.py helm-list -A

# Context / Kubeconfig management
python k8s_cli.py context-list
python k8s_cli.py context-use my-cluster-context
python k8s_cli.py kubeconfig-add --from-file /tmp/new-cluster.kubeconfig

# RBAC tenant management
python k8s_cli.py rbac-create-tenant zhangsan --role developer -n team-a
python k8s_cli.py rbac-list-tenants -A
python k8s_cli.py rbac-get-token zhangsan -n team-a --duration 8760h
python k8s_cli.py prompt-generate zhangsan -n team-a

# With TKE cluster (auto-fetch kubeconfig)
python k8s_cli.py get pods --cluster-id cls-xxx --region ap-guangzhou -n default
```
