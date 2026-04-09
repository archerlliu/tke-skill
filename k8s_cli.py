#!/usr/bin/env python3
"""
Kubernetes & Helm CLI - 轻量级 K8s 集群内操作命令行工具

封装 kubectl 和 helm 命令，支持通过 TKE API 自动获取 kubeconfig。
依赖：kubectl、helm 二进制（需提前安装）
"""

import argparse
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile


# ========== 临时文件管理 ==========

_temp_files = []


def _cleanup_temp_files():
    """进程退出时清理临时文件"""
    for f in _temp_files:
        try:
            if os.path.exists(f):
                os.unlink(f)
        except OSError:
            pass


atexit.register(_cleanup_temp_files)


# ========== 工具函数 ==========

def check_binary(name):
    """检查命令行工具是否已安装"""
    if not shutil.which(name):
        print(f"错误：未找到 {name} 命令。请先安装 {name}。", file=sys.stderr)
        sys.exit(1)


def resolve_kubeconfig(args):
    """
    解析 kubeconfig 路径，优先级：
    1. --kubeconfig 参数（显式指定文件）
    2. --cluster-id + --region 从 TKE API 自动获取（显式指定集群）
    3. KUBECONFIG 环境变量
    4. ~/.kube/config 默认路径

    设计原则：用户显式指定的参数（1、2）优先于隐式的环境配置（3、4）。
    """
    # 1. --kubeconfig 参数（最高优先级）
    kubeconfig = getattr(args, 'kubeconfig', None)
    if kubeconfig:
        if not os.path.isfile(kubeconfig):
            print(f"错误：kubeconfig 文件不存在: {kubeconfig}", file=sys.stderr)
            sys.exit(1)
        return kubeconfig

    # 2. --cluster-id 指定了 TKE 集群，从 API 自动获取
    cluster_id = getattr(args, 'cluster_id', None)
    region = getattr(args, 'region', None)
    if cluster_id and region:
        return fetch_kubeconfig_from_tke(args)

    # 3. KUBECONFIG 环境变量
    kubeconfig = os.getenv("KUBECONFIG")
    if kubeconfig and os.path.isfile(kubeconfig):
        return kubeconfig

    # 4. ~/.kube/config 默认路径
    default_path = os.path.expanduser("~/.kube/config")
    if os.path.isfile(default_path):
        return default_path

    print("错误：未找到 kubeconfig。请通过以下方式之一提供：\n"
          "  1. --kubeconfig <路径>\n"
          "  2. --cluster-id + --region 自动从 TKE API 获取\n"
          "  3. 设置 KUBECONFIG 环境变量\n"
          "  4. 将 kubeconfig 放到 ~/.kube/config",
          file=sys.stderr)
    sys.exit(1)


def fetch_kubeconfig_from_tke(args):
    """通过 tke_cli.py 从 TKE API 获取 kubeconfig 并写入临时文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tke_cli = os.path.join(script_dir, "tke_cli.py")

    if not os.path.isfile(tke_cli):
        print("错误：未找到 tke_cli.py，无法自动获取 kubeconfig。", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, tke_cli, "kubeconfig",
           "--cluster-id", args.cluster_id,
           "--region", args.region]

    # 传递腾讯云凭证
    secret_id = getattr(args, 'secret_id', None) or os.getenv("TENCENTCLOUD_SECRET_ID")
    secret_key = getattr(args, 'secret_key', None) or os.getenv("TENCENTCLOUD_SECRET_KEY")
    if secret_id:
        cmd.extend(["--secret-id", secret_id])
    if secret_key:
        cmd.extend(["--secret-key", secret_key])

    is_extranet = getattr(args, 'is_extranet', False)
    if is_extranet:
        cmd.append("--is-extranet")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"错误：从 TKE API 获取 kubeconfig 失败: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(result.stdout)
        kubeconfig_content = data.get("Kubeconfig", "")
        if not kubeconfig_content:
            print("错误：TKE API 返回的 kubeconfig 为空。请确认集群端点已开启。", file=sys.stderr)
            sys.exit(1)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"错误：解析 TKE API 返回的 kubeconfig 失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 写入临时文件（进程退出时自动清理）
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.kubeconfig', delete=False, prefix='tke-')
    tmp.write(kubeconfig_content)
    tmp.close()
    os.chmod(tmp.name, 0o600)
    _temp_files.append(tmp.name)
    print(f"[info] 已从 TKE API 自动获取 kubeconfig，临时文件: {tmp.name}", file=sys.stderr)
    return tmp.name


def run_command(cmd, env=None):
    """执行命令并输出结果"""
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.stdout:
        print(result.stdout, end='')
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr)
        sys.exit(result.returncode)
    return result


def build_kubeconfig_args(args):
    """构建 --kubeconfig 参数"""
    kubeconfig = resolve_kubeconfig(args)
    if kubeconfig:
        return ["--kubeconfig", kubeconfig]
    return []


def print_json(data):
    """格式化输出 JSON"""
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ========== K8s 资源操作命令 ==========

def cmd_get(args):
    """查看 K8s 资源"""
    check_binary("kubectl")
    cmd = ["kubectl", "get", args.resource]
    if args.name:
        cmd.append(args.name)
    if args.all_namespaces:
        cmd.append("-A")
    else:
        cmd.extend(["-n", args.namespace])
    if args.output:
        cmd.extend(["-o", args.output])
    if args.selector:
        cmd.extend(["-l", args.selector])
    if args.show_labels:
        cmd.append("--show-labels")
    if args.watch:
        cmd.append("-w")
    if args.sort_by:
        cmd.extend(["--sort-by", args.sort_by])
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_describe(args):
    """详细描述 K8s 资源"""
    check_binary("kubectl")
    cmd = ["kubectl", "describe", args.resource]
    if args.name:
        cmd.append(args.name)
    cmd.extend(["-n", args.namespace])
    if args.selector:
        cmd.extend(["-l", args.selector])
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_apply(args):
    """应用 YAML 资源清单"""
    check_binary("kubectl")
    cmd = ["kubectl", "apply"]
    if args.filename:
        cmd.extend(["-f", args.filename])
    if args.kustomize:
        cmd.extend(["-k", args.kustomize])
    cmd.extend(["-n", args.namespace])
    if args.dry_run:
        cmd.extend(["--dry-run", args.dry_run])
    if args.server_side:
        cmd.append("--server-side")
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_delete(args):
    """删除 K8s 资源"""
    check_binary("kubectl")
    cmd = ["kubectl", "delete", args.resource]
    if args.name:
        cmd.append(args.name)
    cmd.extend(["-n", args.namespace])
    if args.filename:
        cmd.extend(["-f", args.filename])
    if args.selector:
        cmd.extend(["-l", args.selector])
    if args.force:
        cmd.append("--force")
        cmd.extend(["--grace-period", "0"])
    if args.cascade:
        cmd.extend(["--cascade", args.cascade])
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_create(args):
    """快速创建 K8s 资源"""
    check_binary("kubectl")
    cmd = ["kubectl", "create", args.resource, args.name]
    cmd.extend(["-n", args.namespace])
    if args.image:
        cmd.extend(["--image", args.image])
    if args.replicas:
        cmd.extend(["--replicas", str(args.replicas)])
    if args.port:
        cmd.extend(["--port", str(args.port)])
    if args.dry_run:
        cmd.extend(["--dry-run", args.dry_run])
    if args.output:
        cmd.extend(["-o", args.output])
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_events(args):
    """查看 K8s 事件"""
    check_binary("kubectl")
    cmd = ["kubectl", "get", "events"]
    if args.all_namespaces:
        cmd.append("-A")
    else:
        cmd.extend(["-n", args.namespace])
    if args.field_selector:
        cmd.extend(["--field-selector", args.field_selector])
    if args.sort_by:
        cmd.extend(["--sort-by", args.sort_by])
    else:
        cmd.extend(["--sort-by", ".lastTimestamp"])
    if args.watch:
        cmd.append("-w")
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


# ========== Pod 操作命令 ==========

def cmd_logs(args):
    """查看 Pod 日志"""
    check_binary("kubectl")
    cmd = ["kubectl", "logs", args.pod]
    cmd.extend(["-n", args.namespace])
    if args.container:
        cmd.extend(["-c", args.container])
    if args.follow:
        cmd.append("-f")
    if args.previous:
        cmd.append("--previous")
    if args.tail is not None:
        cmd.extend(["--tail", str(args.tail)])
    if args.since:
        cmd.extend(["--since", args.since])
    if args.timestamps:
        cmd.append("--timestamps")
    if args.all_containers:
        cmd.append("--all-containers")
    if args.selector:
        cmd.extend(["-l", args.selector])
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_exec(args):
    """在容器中执行单条命令"""
    check_binary("kubectl")
    cmd = ["kubectl", "exec", args.pod]
    cmd.extend(["-n", args.namespace])
    if args.container:
        cmd.extend(["-c", args.container])
    # --kubeconfig 必须在 -- 之前，否则 kubectl 不识别
    cmd.extend(build_kubeconfig_args(args))
    cmd.append("--")
    cmd.extend(args._exec_command)
    run_command(cmd)


def cmd_top(args):
    """查看资源使用情况"""
    check_binary("kubectl")
    cmd = ["kubectl", "top", args.resource_type]
    if args.name:
        cmd.append(args.name)
    if args.all_namespaces:
        cmd.append("-A")
    else:
        cmd.extend(["-n", args.namespace])
    if args.containers and args.resource_type == "pods":
        cmd.append("--containers")
    if args.sort_by:
        cmd.extend(["--sort-by", args.sort_by])
    if args.selector:
        cmd.extend(["-l", args.selector])
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


# ========== Context / Kubeconfig 管理命令 ==========

def cmd_context_list(args):
    """列出 kubeconfig 中所有 context"""
    check_binary("kubectl")
    cmd = ["kubectl", "config", "get-contexts"]
    cmd.extend(build_kubeconfig_args(args))
    if args.output:
        cmd.extend(["-o", args.output])
    run_command(cmd)


def cmd_context_use(args):
    """切换当前 context"""
    check_binary("kubectl")
    cmd = ["kubectl", "config", "use-context", args.context_name]
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_context_current(args):
    """显示当前 context"""
    check_binary("kubectl")
    cmd = ["kubectl", "config", "current-context"]
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_kubeconfig_add(args):
    """合并外部 kubeconfig 到当前配置"""
    check_binary("kubectl")
    source = args.from_file
    if not os.path.isfile(source):
        print(f"错误：文件不存在: {source}", file=sys.stderr)
        sys.exit(1)

    # 目标 kubeconfig
    target = getattr(args, 'kubeconfig', None) or os.getenv("KUBECONFIG") or os.path.expanduser("~/.kube/config")

    # 使用 KUBECONFIG 环境变量合并多个文件
    merge_env = os.environ.copy()
    merge_env["KUBECONFIG"] = f"{target}:{source}"

    cmd = ["kubectl", "config", "view", "--flatten"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=merge_env)
    if result.returncode != 0:
        print(f"错误：合并 kubeconfig 失败: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)

    if args.dry_run:
        # 仅预览合并结果，不写入文件
        print(result.stdout, end='')
        return

    # 写回目标文件
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with open(target, 'w') as f:
        f.write(result.stdout)
    print(f"已将 {source} 合并到 {target}")


# ========== RBAC 租户管理命令 ==========

def load_rbac_template(template_name, rules_file=None):
    """加载 RBAC 角色模板"""
    import yaml

    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "rbac_templates.yaml")

    if not os.path.isfile(template_path):
        print(f"错误：未找到 RBAC 模板文件: {template_path}", file=sys.stderr)
        sys.exit(1)

    with open(template_path, 'r') as f:
        config = yaml.safe_load(f)

    templates = config.get("templates", {})
    if template_name not in templates:
        valid = ", ".join(templates.keys())
        print(f"错误：未知角色模板 '{template_name}'，可选: {valid}", file=sys.stderr)
        sys.exit(1)

    template = templates[template_name]

    # custom 模板需要 --rules-file
    if template_name == "custom":
        if not rules_file:
            print("错误：custom 模板需要通过 --rules-file 指定自定义规则文件", file=sys.stderr)
            sys.exit(1)
        if not os.path.isfile(rules_file):
            print(f"错误：规则文件不存在: {rules_file}", file=sys.stderr)
            sys.exit(1)
        with open(rules_file, 'r') as f:
            custom_rules = yaml.safe_load(f)
        template["rules"] = custom_rules.get("rules", custom_rules)

    return template


def generate_rbac_yaml(tenant_name, namespace, template):
    """生成租户 RBAC 资源的 YAML 清单"""
    import yaml

    sa_name = f"tke-tenant-{tenant_name}"
    role_name = f"tke-tenant-{tenant_name}-role"
    binding_name = f"tke-tenant-{tenant_name}-binding"

    # 公共 labels，用于识别和查询 TKE Skill 管理的租户资源
    labels = {
        "app.kubernetes.io/managed-by": "tke-skill",
        "tke-skill/tenant": tenant_name,
        "tke-skill/component": "rbac"
    }

    resources = []

    # 1. ServiceAccount
    resources.append({
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": sa_name,
            "namespace": namespace,
            "labels": labels
        }
    })

    if template.get("cluster_role") and template.get("cluster_role_ref"):
        # admin 模式：RoleBinding 绑定内置 ClusterRole
        resources.append({
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {
                "name": binding_name,
                "namespace": namespace,
                "labels": labels
            },
            "subjects": [{
                "kind": "ServiceAccount",
                "name": sa_name,
                "namespace": namespace
            }],
            "roleRef": {
                "kind": "ClusterRole",
                "name": template["cluster_role_ref"],
                "apiGroup": "rbac.authorization.k8s.io"
            }
        })
    else:
        # readonly / developer / custom：创建自定义 Role + RoleBinding
        resources.append({
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {
                "name": role_name,
                "namespace": namespace,
                "labels": labels
            },
            "rules": template.get("rules", [])
        })
        resources.append({
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {
                "name": binding_name,
                "namespace": namespace,
                "labels": labels
            },
            "subjects": [{
                "kind": "ServiceAccount",
                "name": sa_name,
                "namespace": namespace
            }],
            "roleRef": {
                "kind": "Role",
                "name": role_name,
                "apiGroup": "rbac.authorization.k8s.io"
            }
        })

    # 多文档 YAML 输出
    return yaml.dump_all(resources, default_flow_style=False, allow_unicode=True)


def cmd_rbac_create_tenant(args):
    """创建租户（ServiceAccount + Role + RoleBinding）"""
    check_binary("kubectl")

    template = load_rbac_template(args.role, getattr(args, 'rules_file', None))
    yaml_content = generate_rbac_yaml(args.tenant_name, args.namespace, template)

    # 写入临时文件并 kubectl apply
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, prefix='rbac-')
    tmp.write(yaml_content)
    tmp.close()

    try:
        cmd = ["kubectl", "apply", "-f", tmp.name]
        cmd.extend(["-n", args.namespace])
        cmd.extend(build_kubeconfig_args(args))

        if args.dry_run:
            cmd.append(f"--dry-run={args.dry_run}")

        run_command(cmd)
    finally:
        os.unlink(tmp.name)


def cmd_rbac_list_tenants(args):
    """列出所有 TKE Skill 管理的租户"""
    check_binary("kubectl")
    cmd = ["kubectl", "get", "serviceaccount",
           "-l", "app.kubernetes.io/managed-by=tke-skill",
           "-o", "json"]
    if args.all_namespaces:
        cmd.append("-A")
    else:
        cmd.extend(["-n", args.namespace])
    cmd.extend(build_kubeconfig_args(args))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr)
        sys.exit(result.returncode)

    data = json.loads(result.stdout)
    items = data.get("items", [])

    if not items:
        print("未找到 TKE Skill 管理的租户。")
        return

    # 格式化输出
    tenants = []
    for sa in items:
        labels = sa["metadata"].get("labels", {})
        tenants.append({
            "tenant": labels.get("tke-skill/tenant", "unknown"),
            "namespace": sa["metadata"]["namespace"],
            "service_account": sa["metadata"]["name"],
            "created": sa["metadata"].get("creationTimestamp", ""),
        })

    print_json(tenants)


def cmd_rbac_delete_tenant(args):
    """删除租户的所有 RBAC 资源"""
    check_binary("kubectl")

    label_selector = f"tke-skill/tenant={args.tenant_name},app.kubernetes.io/managed-by=tke-skill"

    # 删除顺序：RoleBinding -> Role -> ServiceAccount
    for resource_type in ["rolebinding", "role", "serviceaccount"]:
        cmd = ["kubectl", "delete", resource_type,
               "-l", label_selector,
               "-n", args.namespace]
        cmd.extend(build_kubeconfig_args(args))
        # 不用 run_command，因为某些资源可能不存在（如 admin 没有 Role）
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end='')


def cmd_rbac_get_token(args):
    """获取租户 ServiceAccount 的访问 Token"""
    check_binary("kubectl")

    sa_name = f"tke-tenant-{args.tenant_name}"

    # 使用 kubectl create token（K8s 1.24+）
    cmd = ["kubectl", "create", "token", sa_name,
           "-n", args.namespace]
    if args.duration:
        cmd.extend(["--duration", args.duration])
    cmd.extend(build_kubeconfig_args(args))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"错误：获取 token 失败: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)

    token = result.stdout.strip()

    if args.output == "json":
        print_json({
            "tenant": args.tenant_name,
            "namespace": args.namespace,
            "service_account": sa_name,
            "token": token
        })
    else:
        print(token)


def cmd_prompt_generate(args):
    """为租户生成一键安装 Prompt"""
    check_binary("kubectl")

    sa_name = f"tke-tenant-{args.tenant_name}"

    # 1. 获取 token
    cmd = ["kubectl", "create", "token", sa_name,
           "-n", args.namespace, "--duration", args.duration or "8760h"]
    cmd.extend(build_kubeconfig_args(args))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"错误：获取 token 失败: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)
    token = result.stdout.strip()

    # 2. 获取集群 API Server 地址
    cmd2 = ["kubectl", "config", "view", "--minify", "-o",
            "jsonpath={.clusters[0].cluster.server}"]
    cmd2.extend(build_kubeconfig_args(args))
    result2 = subprocess.run(cmd2, capture_output=True, text=True)
    server = result2.stdout.strip()

    # 3. 获取集群 CA 证书
    cmd3 = ["kubectl", "config", "view", "--minify", "--raw", "-o",
            "jsonpath={.clusters[0].cluster.certificate-authority-data}"]
    cmd3.extend(build_kubeconfig_args(args))
    result3 = subprocess.run(cmd3, capture_output=True, text=True)
    ca_data = result3.stdout.strip()

    # 4. 生成 kubeconfig YAML
    cluster_name = args.cluster_name or "tke-cluster"
    kubeconfig_yaml = f"""apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: {ca_data}
    server: {server}
  name: {cluster_name}
contexts:
- context:
    cluster: {cluster_name}
    namespace: {args.namespace}
    user: {sa_name}
  name: {sa_name}@{cluster_name}
current-context: {sa_name}@{cluster_name}
users:
- name: {sa_name}
  user:
    token: {token}
"""

    # 5. 生成 Prompt
    prompt = f"""# TKE Skill 一键安装 Prompt
# 租户: {args.tenant_name} | 命名空间: {args.namespace} | 集群: {cluster_name}

## 步骤 1：保存 kubeconfig
将以下内容保存到 ~/.kube/tke-tenant-{args.tenant_name}.config：

```yaml
{kubeconfig_yaml}```

## 步骤 2：配置环境变量
```bash
export KUBECONFIG=~/.kube/tke-tenant-{args.tenant_name}.config
```

## 步骤 3：安装 TKE Skill
将 tke-skill 目录复制到你的 AI Agent 的 Skill 目录中（如 ~/.codebuddy/skills/tke/）。

## 步骤 4：验证连接
```bash
python k8s_cli.py get pods -n {args.namespace}
```
"""
    print(prompt)


# ========== 节点诊断命令 ==========

# 默认配置
_NODE_DEBUG_IMAGE = "busybox"
_NODE_DEBUG_NAMESPACE = "default"
_ATOP_LOG_DIR = "/var/log/atop"


def _node_debug_run(node, exec_cmd, args, timeout=60):
    """
    在节点 debug pod 中执行单条命令，返回 (stdout, stderr, returncode)。
    流程：kubectl debug node/<node> --attach=false 创建 pod
          -> 从 stderr 解析 pod 名 -> wait Ready -> exec -> 删除 pod。
    """
    check_binary("kubectl")
    image = getattr(args, 'image', None) or _NODE_DEBUG_IMAGE
    namespace = getattr(args, 'namespace', None) or _NODE_DEBUG_NAMESPACE
    kubeconfig_args = build_kubeconfig_args(args)

    # 1. 创建 debug pod（非交互）
    # pod 名称由 kubectl 自动生成，从 stderr 解析：
    #   "Creating debugging pod node-debugger-<node>-<suffix> ..."
    create_cmd = [
        "kubectl", "debug", f"node/{node}",
        "--image", image,
        "-n", namespace,
        "--attach=false",
        "--profile=general",
    ] + kubeconfig_args + [
        "--", "sleep", str(timeout + 60),
    ]

    print(f"[info] 在节点 {node} 上创建 debug pod...", file=sys.stderr)
    result = subprocess.run(create_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"错误：创建 debug pod 失败:\n{result.stderr.strip()}",
              file=sys.stderr)
        sys.exit(result.returncode)

    # 从 stderr 解析 pod 名称
    # 输出示例：Creating debugging pod node-debugger-<node>-<suffix> with ...
    actual_pod = None
    for line in (result.stdout + result.stderr).splitlines():
        if "Creating debugging pod" in line:
            parts = line.split()
            # 格式：Creating debugging pod <pod-name> with ...
            for i, part in enumerate(parts):
                if part == "pod" and i + 1 < len(parts):
                    actual_pod = parts[i + 1]
                    break
        if actual_pod:
            break

    if not actual_pod:
        print("错误：无法从输出中解析 debug pod 名称。\n"
              f"kubectl 输出：{result.stdout}\n{result.stderr}",
              file=sys.stderr)
        sys.exit(1)

    print(f"[info] debug pod: {actual_pod}，等待就绪...", file=sys.stderr)

    try:
        # 2. 等待 pod Running（用 jsonpath poll，debug pod 没有 readiness probe）
        import time
        deadline = time.time() + timeout
        pod_running = False
        while time.time() < deadline:
            status_cmd = [
                "kubectl", "get", f"pod/{actual_pod}",
                "-n", namespace,
                "-o", "jsonpath={.status.phase}",
            ] + kubeconfig_args
            status_result = subprocess.run(
                status_cmd, capture_output=True, text=True
            )
            if status_result.stdout.strip() == "Running":
                pod_running = True
                break
            time.sleep(2)
        if not pod_running:
            print(f"错误：等待 debug pod 就绪超时（{timeout}s）",
                  file=sys.stderr)
            sys.exit(1)

        # 3. exec 执行命令（宿主机文件系统挂载在 /host）
        exec_full_cmd = [
            "kubectl", "exec", actual_pod,
            "-n", namespace,
            "--",
        ] + exec_cmd + kubeconfig_args

        print(f"[info] 执行诊断命令...", file=sys.stderr)
        exec_result = subprocess.run(
            exec_full_cmd, capture_output=True, text=True
        )
        return exec_result.stdout, exec_result.stderr, exec_result.returncode
    finally:
        # 4. 清理 debug pod
        del_cmd = [
            "kubectl", "delete", "pod", actual_pod,
            "-n", namespace, "--ignore-not-found",
        ] + kubeconfig_args
        subprocess.run(del_cmd, capture_output=True, text=True)
        print(f"[info] 已清理 debug pod: {actual_pod}", file=sys.stderr)


def cmd_node_debug_shell(args):
    """进入节点交互式 shell（提示用户手动执行）"""
    node = args.node
    image = getattr(args, 'image', None) or _NODE_DEBUG_IMAGE
    kubeconfig_str = ""
    kubeconfig = resolve_kubeconfig(args)
    if kubeconfig:
        kubeconfig_str = f" --kubeconfig {kubeconfig}"

    print(f"""
[提示] 交互式 shell 需在终端直接执行以下命令：

  kubectl debug node/{node} -it --image={image}{kubeconfig_str}

进入容器后，宿主机文件系统挂载在 /host，可执行：
  chroot /host         # 切换到宿主机根目录
  dmesg -T             # 内核日志
  journalctl -u kubelet -n 100
  crictl ps            # 容器状态
  cat /var/log/atop/atop_$(date +%Y%m%d)  # atop 日志
""")


def cmd_node_debug_dmesg(args):
    """查看节点内核日志（dmesg）"""
    node = args.node
    tail = getattr(args, 'tail', None)
    # 宿主机文件系统在 /host，通过 chroot 执行 dmesg
    cmd = ["chroot", "/host", "dmesg", "-T"]
    if tail:
        cmd += ["|", "tail", "-n", str(tail)]
        # 避免 shell=True，改用 sh -c
        cmd = ["chroot", "/host", "sh", "-c",
               f"dmesg -T | tail -n {tail}"]
    stdout, stderr, rc = _node_debug_run(node, cmd, args)
    if stdout:
        print(stdout, end='')
    if rc != 0 and stderr:
        print(stderr, end='', file=sys.stderr)
        sys.exit(rc)


def cmd_node_debug_kubelet_logs(args):
    """查看节点 kubelet 日志"""
    node = args.node
    tail = getattr(args, 'tail', 100)
    since = getattr(args, 'since', None)

    journalctl_cmd = f"journalctl -u kubelet -n {tail} --no-pager"
    if since:
        journalctl_cmd += f" --since '{since}'"
    cmd = ["chroot", "/host", "sh", "-c", journalctl_cmd]

    stdout, stderr, rc = _node_debug_run(node, cmd, args)
    if stdout:
        print(stdout, end='')
    if rc != 0 and stderr:
        print(stderr, end='', file=sys.stderr)
        sys.exit(rc)


def cmd_node_debug_crictl(args):
    """查看节点容器运行时状态（crictl ps）"""
    node = args.node
    all_containers = getattr(args, 'all_containers', False)

    crictl_cmd = "crictl ps"
    if all_containers:
        crictl_cmd += " -a"
    cmd = ["chroot", "/host", "sh", "-c", crictl_cmd]

    stdout, stderr, rc = _node_debug_run(node, cmd, args)
    if stdout:
        print(stdout, end='')
    if rc != 0 and stderr:
        print(stderr, end='', file=sys.stderr)
        sys.exit(rc)


def cmd_node_debug_atop(args):
    """获取节点 atop 日志文件（二进制，通过 kubectl cp 传输）"""
    import datetime
    check_binary("kubectl")
    node = args.node
    atop_dir = getattr(args, 'atop_dir', None) or _ATOP_LOG_DIR
    date_str = getattr(args, 'date', None)
    output_file = getattr(args, 'output_file', None)
    image = getattr(args, 'image', None) or _NODE_DEBUG_IMAGE
    namespace = getattr(args, 'namespace', None) or _NODE_DEBUG_NAMESPACE
    kubeconfig_args = build_kubeconfig_args(args)

    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y%m%d")

    atop_path = f"{atop_dir}/atop_{date_str}"
    local_out = output_file or f"atop_{node.replace('/', '-')}_{date_str}.log"

    print(f"[info] 读取节点 {node} 的 atop 日志: {atop_path}",
          file=sys.stderr)

    # 1. 创建 debug pod
    create_cmd = [
        "kubectl", "debug", f"node/{node}",
        "--image", image,
        "-n", namespace,
        "--attach=false",
        "--profile=general",
    ] + kubeconfig_args + ["--", "sleep", "120"]

    result = subprocess.run(create_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"错误：创建 debug pod 失败: {result.stderr.strip()}",
              file=sys.stderr)
        sys.exit(result.returncode)

    actual_pod = None
    for line in (result.stdout + result.stderr).splitlines():
        if "Creating debugging pod" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "pod" and i + 1 < len(parts):
                    actual_pod = parts[i + 1]
                    break
        if actual_pod:
            break

    if not actual_pod:
        print("错误：无法解析 debug pod 名称。", file=sys.stderr)
        sys.exit(1)

    print(f"[info] debug pod: {actual_pod}，等待就绪...", file=sys.stderr)

    try:
        # 2. 等待 Running
        import time
        deadline = time.time() + 60
        while time.time() < deadline:
            s = subprocess.run(
                ["kubectl", "get", f"pod/{actual_pod}",
                 "-n", namespace, "-o", "jsonpath={.status.phase}"]
                + kubeconfig_args,
                capture_output=True, text=True
            )
            if s.stdout.strip() == "Running":
                break
            time.sleep(2)
        else:
            print("错误：等待 debug pod 就绪超时。", file=sys.stderr)
            sys.exit(1)

        # 3. 先检查文件是否存在
        check = subprocess.run(
            ["kubectl", "exec", actual_pod, "-n", namespace, "--",
             "sh", "-c", f"test -f /host{atop_path} && echo ok || echo missing"]
            + kubeconfig_args,
            capture_output=True, text=True
        )
        if check.stdout.strip() != "ok":
            print(f"错误：节点上文件不存在: {atop_path}", file=sys.stderr)
            sys.exit(1)

        # 4. kubectl cp 直接拷贝二进制文件（保留完整内容）
        src = f"{namespace}/{actual_pod}:/host{atop_path}"
        cp_cmd = ["kubectl", "cp", src, local_out] + kubeconfig_args
        print(f"[info] 通过 kubectl cp 下载二进制日志...", file=sys.stderr)
        cp_result = subprocess.run(cp_cmd, capture_output=True, text=True)
        if cp_result.returncode != 0:
            print(f"错误：拷贝失败: {cp_result.stderr.strip()}",
                  file=sys.stderr)
            sys.exit(1)

        import os
        size = os.path.getsize(local_out)
        print(f"[info] atop 日志已保存到: {local_out} ({size} bytes)")

    finally:
        subprocess.run(
            ["kubectl", "delete", "pod", actual_pod,
             "-n", namespace, "--ignore-not-found"] + kubeconfig_args,
            capture_output=True, text=True
        )
        print(f"[info] 已清理 debug pod: {actual_pod}", file=sys.stderr)


def cmd_node_debug_diagnose(args):
    """一键诊断节点（汇总 dmesg + kubelet 日志 + crictl 状态）"""
    node = args.node
    separator = "=" * 60

    sections = [
        ("dmesg（最近 50 行）",
         ["chroot", "/host", "sh", "-c", "dmesg -T | tail -n 50"]),
        ("kubelet 日志（最近 50 行）",
         ["chroot", "/host", "sh", "-c",
          "journalctl -u kubelet -n 50 --no-pager"]),
        ("容器运行时状态（crictl ps）",
         ["chroot", "/host", "sh", "-c", "crictl ps 2>/dev/null || "
          "echo 'crictl 不可用'"]),
        ("磁盘使用（df -h）",
         ["chroot", "/host", "sh", "-c", "df -h"]),
        ("内存使用（free -h）",
         ["chroot", "/host", "sh", "-c", "free -h"]),
    ]

    print(f"\n{separator}")
    print(f"  节点诊断报告: {node}")
    print(f"{separator}\n")

    for title, cmd in sections:
        print(f"\n--- {title} ---")
        stdout, stderr, rc = _node_debug_run(node, cmd, args)
        if stdout:
            print(stdout, end='')
        elif stderr:
            print(f"[warn] {stderr.strip()}", file=sys.stderr)


def cmd_node_debug_cleanup(args):
    """清理所有遗留的节点 debug pod"""
    check_binary("kubectl")
    namespace = getattr(args, 'namespace', None) or _NODE_DEBUG_NAMESPACE
    kubeconfig_args = build_kubeconfig_args(args)

    # kubectl debug node 创建的 pod 名称以 node-debugger- 开头
    list_cmd = [
        "kubectl", "get", "pods",
        "-n", namespace,
        "--field-selector=status.phase!=Running",
        "-o", "jsonpath={.items[*].metadata.name}",
    ] + kubeconfig_args

    result = subprocess.run(list_cmd, capture_output=True, text=True)
    # 同时列出 Running 的 debug pod（名称包含 node-debugger）
    list_all_cmd = [
        "kubectl", "get", "pods",
        "-n", namespace,
        "-o", "jsonpath={.items[*].metadata.name}",
    ] + kubeconfig_args
    result_all = subprocess.run(list_all_cmd, capture_output=True, text=True)

    all_pods = result_all.stdout.split()
    debug_pods = [p for p in all_pods if "node-debugger" in p or
                  p.startswith("node-debug-")]

    if not debug_pods:
        print("未找到遗留的 node debug pod。")
        return

    print(f"找到 {len(debug_pods)} 个 debug pod：{', '.join(debug_pods)}")
    del_cmd = [
        "kubectl", "delete", "pod",
    ] + debug_pods + ["-n", namespace] + kubeconfig_args
    run_command(del_cmd)
    print("清理完成。")


# ========== Helm 操作命令 ==========

def cmd_helm_install(args):
    """安装 Helm Chart"""
    check_binary("helm")
    cmd = ["helm", "install", args.release, args.chart]
    cmd.extend(["-n", args.namespace])
    if args.create_namespace:
        cmd.append("--create-namespace")
    if args.values:
        for v in args.values:
            cmd.extend(["-f", v])
    if args.set:
        for s in args.set:
            cmd.extend(["--set", s])
    if args.version:
        cmd.extend(["--version", args.version])
    if args.repo:
        cmd.extend(["--repo", args.repo])
    if args.wait:
        cmd.append("--wait")
    if args.timeout:
        cmd.extend(["--timeout", args.timeout])
    if args.dry_run:
        cmd.append("--dry-run")
    if args.atomic:
        cmd.append("--atomic")
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_helm_upgrade(args):
    """升级 Helm Release"""
    check_binary("helm")
    cmd = ["helm", "upgrade", args.release, args.chart]
    cmd.extend(["-n", args.namespace])
    if args.install:
        cmd.append("--install")
    if args.values:
        for v in args.values:
            cmd.extend(["-f", v])
    if args.set:
        for s in args.set:
            cmd.extend(["--set", s])
    if args.version:
        cmd.extend(["--version", args.version])
    if args.repo:
        cmd.extend(["--repo", args.repo])
    if args.wait:
        cmd.append("--wait")
    if args.timeout:
        cmd.extend(["--timeout", args.timeout])
    if args.dry_run:
        cmd.append("--dry-run")
    if args.atomic:
        cmd.append("--atomic")
    if args.reuse_values:
        cmd.append("--reuse-values")
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_helm_uninstall(args):
    """卸载 Helm Release"""
    check_binary("helm")
    cmd = ["helm", "uninstall", args.release]
    cmd.extend(["-n", args.namespace])
    if args.keep_history:
        cmd.append("--keep-history")
    if args.wait:
        cmd.append("--wait")
    if args.timeout:
        cmd.extend(["--timeout", args.timeout])
    if args.dry_run:
        cmd.append("--dry-run")
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_helm_list(args):
    """列出 Helm Release"""
    check_binary("helm")
    cmd = ["helm", "list"]
    if args.all_namespaces:
        cmd.append("-A")
    else:
        cmd.extend(["-n", args.namespace])
    if args.all:
        cmd.append("--all")
    if args.output:
        cmd.extend(["-o", args.output])
    if args.filter:
        cmd.extend(["--filter", args.filter])
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


def cmd_helm_status(args):
    """查看 Helm Release 状态"""
    check_binary("helm")
    cmd = ["helm", "status", args.release]
    cmd.extend(["-n", args.namespace])
    if args.output:
        cmd.extend(["-o", args.output])
    if args.show_resources:
        cmd.append("--show-resources")
    cmd.extend(build_kubeconfig_args(args))
    run_command(cmd)


# ========== 主入口 ==========

def main():
    # 公共参数
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--kubeconfig", help="kubeconfig 文件路径")
    common_parser.add_argument("-n", "--namespace", default="default", help="命名空间（默认 default）")
    common_parser.add_argument("--cluster-id", dest="cluster_id", help="TKE 集群 ID（用于自动获取 kubeconfig）")
    common_parser.add_argument("--region", default="ap-guangzhou", help="地域（配合 --cluster-id 使用，默认 ap-guangzhou）")
    common_parser.add_argument("--secret-id", dest="secret_id", help="腾讯云 SecretId（配合 --cluster-id 使用）")
    common_parser.add_argument("--secret-key", dest="secret_key", help="腾讯云 SecretKey（配合 --cluster-id 使用）")
    common_parser.add_argument(
        "--is-extranet", dest="is_extranet", action="store_true",
        help="使用外网 kubeconfig（配合 --cluster-id 使用）")

    parser = argparse.ArgumentParser(
        description="Kubernetes & Helm CLI - 轻量级 K8s 集群内操作工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python k8s_cli.py get pods -n default
  python k8s_cli.py logs my-pod -n default --tail 100
  python k8s_cli.py apply -f deployment.yaml
  python k8s_cli.py helm-install my-release bitnami/nginx -n default
  python k8s_cli.py get pods --cluster-id cls-xxx --region ap-guangzhou
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ---- K8s 资源操作 ----

    # get
    p = subparsers.add_parser("get", parents=[common_parser], help="查看 K8s 资源")
    p.add_argument("resource", help="资源类型（如 pods, deployments, services, nodes 等）")
    p.add_argument("name", nargs="?", help="资源名称（可选，不指定则列出所有）")
    p.add_argument("-o", "--output", help="输出格式（wide, yaml, json, name 等）")
    p.add_argument("-l", "--selector", help="标签选择器")
    p.add_argument("-A", "--all-namespaces", dest="all_namespaces", action="store_true", help="查看所有命名空间")
    p.add_argument("--show-labels", dest="show_labels", action="store_true", help="显示标签")
    p.add_argument("-w", "--watch", action="store_true", help="持续监听变化")
    p.add_argument("--sort-by", dest="sort_by", help="排序字段（如 .metadata.creationTimestamp）")
    p.set_defaults(func=cmd_get)

    # describe
    p = subparsers.add_parser("describe", parents=[common_parser], help="详细描述 K8s 资源")
    p.add_argument("resource", help="资源类型")
    p.add_argument("name", nargs="?", help="资源名称（可选）")
    p.add_argument("-l", "--selector", help="标签选择器")
    p.set_defaults(func=cmd_describe)

    # apply
    p = subparsers.add_parser("apply", parents=[common_parser], help="应用 YAML 资源清单")
    p.add_argument("-f", "--filename", help="YAML 文件路径或 URL")
    p.add_argument("-k", "--kustomize", help="Kustomize 目录路径")
    p.add_argument("--dry-run", dest="dry_run", choices=["client", "server"], help="试运行模式")
    p.add_argument("--server-side", dest="server_side", action="store_true", help="服务端 apply")
    p.set_defaults(func=cmd_apply)

    # delete
    p = subparsers.add_parser("delete", parents=[common_parser], help="删除 K8s 资源")
    p.add_argument("resource", help="资源类型")
    p.add_argument("name", nargs="?", help="资源名称")
    p.add_argument("-f", "--filename", help="YAML 文件路径")
    p.add_argument("-l", "--selector", help="标签选择器")
    p.add_argument("--force", action="store_true", help="强制删除")
    p.add_argument("--cascade", choices=["background", "orphan", "foreground"], help="级联删除策略")
    p.set_defaults(func=cmd_delete)

    # create
    p = subparsers.add_parser("create", parents=[common_parser], help="快速创建 K8s 资源")
    p.add_argument("resource", help="资源类型（如 deployment, service, configmap 等）")
    p.add_argument("name", help="资源名称")
    p.add_argument("--image", help="容器镜像（创建 deployment 时使用）")
    p.add_argument("--replicas", type=int, help="副本数")
    p.add_argument("--port", type=int, help="端口")
    p.add_argument("--dry-run", dest="dry_run", choices=["client", "server"], help="试运行模式")
    p.add_argument("-o", "--output", help="输出格式")
    p.set_defaults(func=cmd_create)

    # events
    p = subparsers.add_parser("events", parents=[common_parser], help="查看 K8s 事件")
    p.add_argument("-A", "--all-namespaces", dest="all_namespaces", action="store_true", help="查看所有命名空间")
    p.add_argument("--field-selector", dest="field_selector", help="字段选择器（如 involvedObject.name=my-pod）")
    p.add_argument("--sort-by", dest="sort_by", help="排序字段（默认 .lastTimestamp）")
    p.add_argument("-w", "--watch", action="store_true", help="持续监听")
    p.set_defaults(func=cmd_events)

    # ---- Pod 操作 ----

    # logs
    p = subparsers.add_parser("logs", parents=[common_parser], help="查看 Pod 日志")
    p.add_argument("pod", help="Pod 名称")
    p.add_argument("-c", "--container", help="容器名称（多容器 Pod 时指定）")
    p.add_argument("-f", "--follow", action="store_true", help="实时跟踪日志")
    p.add_argument("--previous", action="store_true", help="查看上一个容器的日志（排查崩溃原因）")
    p.add_argument("--tail", type=int, help="显示最后 N 行")
    p.add_argument("--since", help="显示指定时间段内的日志（如 1h, 30m, 2h30m）")
    p.add_argument("--timestamps", action="store_true", help="显示时间戳")
    p.add_argument("--all-containers", dest="all_containers", action="store_true", help="显示所有容器日志")
    p.add_argument("-l", "--selector", help="标签选择器（查看匹配 Pod 的日志）")
    p.set_defaults(func=cmd_logs)

    # exec（注意：容器命令通过 -- 分隔，在 main() 中手动拆分后存入 _exec_command）
    p = subparsers.add_parser("exec", parents=[common_parser], help="在容器中执行命令")
    p.add_argument("pod", help="Pod 名称")
    p.add_argument("-c", "--container", help="容器名称")
    p.set_defaults(func=cmd_exec)

    # top
    p = subparsers.add_parser("top", parents=[common_parser], help="查看资源使用情况")
    p.add_argument("resource_type", choices=["pods", "nodes"], help="资源类型（pods 或 nodes）")
    p.add_argument("name", nargs="?", help="资源名称（可选）")
    p.add_argument("-A", "--all-namespaces", dest="all_namespaces", action="store_true", help="查看所有命名空间")
    p.add_argument("--containers", action="store_true", help="显示容器级别的资源用量（仅 pods）")
    p.add_argument("--sort-by", dest="sort_by", choices=["cpu", "memory"], help="排序方式")
    p.add_argument("-l", "--selector", help="标签选择器")
    p.set_defaults(func=cmd_top)

    # ---- Context / Kubeconfig 管理 ----

    # context-list
    p = subparsers.add_parser("context-list", parents=[common_parser], help="列出所有 context")
    p.add_argument("-o", "--output", choices=["name"], help="输出格式（name 只输出名称）")
    p.set_defaults(func=cmd_context_list)

    # context-use
    p = subparsers.add_parser("context-use", parents=[common_parser], help="切换当前 context")
    p.add_argument("context_name", help="要切换到的 context 名称")
    p.set_defaults(func=cmd_context_use)

    # context-current
    p = subparsers.add_parser("context-current", parents=[common_parser], help="显示当前 context")
    p.set_defaults(func=cmd_context_current)

    # kubeconfig-add
    p = subparsers.add_parser("kubeconfig-add", parents=[common_parser], help="合并外部 kubeconfig")
    p.add_argument("--from-file", dest="from_file", required=True, help="要合并的 kubeconfig 文件路径")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="仅预览合并结果，不写入文件")
    p.set_defaults(func=cmd_kubeconfig_add)

    # ---- RBAC 租户管理 ----

    # rbac-create-tenant
    p = subparsers.add_parser("rbac-create-tenant", parents=[common_parser], help="创建租户（SA + Role + RoleBinding）")
    p.add_argument("tenant_name", help="租户名称")
    p.add_argument("--role", required=True, choices=["readonly", "developer", "admin", "custom"], help="角色模板")
    p.add_argument("--rules-file", dest="rules_file", help="自定义规则文件路径（仅 custom 角色需要）")
    p.add_argument("--dry-run", dest="dry_run", choices=["client", "server"], help="试运行模式")
    p.set_defaults(func=cmd_rbac_create_tenant)

    # rbac-list-tenants
    p = subparsers.add_parser("rbac-list-tenants", parents=[common_parser], help="列出所有管理的租户")
    p.add_argument("-A", "--all-namespaces", dest="all_namespaces", action="store_true", help="查看所有命名空间")
    p.set_defaults(func=cmd_rbac_list_tenants)

    # rbac-delete-tenant
    p = subparsers.add_parser("rbac-delete-tenant", parents=[common_parser], help="删除租户 RBAC 资源")
    p.add_argument("tenant_name", help="租户名称")
    p.set_defaults(func=cmd_rbac_delete_tenant)

    # rbac-get-token
    p = subparsers.add_parser("rbac-get-token", parents=[common_parser], help="获取租户 Token")
    p.add_argument("tenant_name", help="租户名称")
    p.add_argument("--duration", help="Token 有效期（如 8760h、720h，默认由 K8s 控制）")
    p.add_argument("-o", "--output", choices=["json"], help="输出格式")
    p.set_defaults(func=cmd_rbac_get_token)

    # prompt-generate
    p = subparsers.add_parser("prompt-generate", parents=[common_parser], help="为租户生成一键安装 Prompt")
    p.add_argument("tenant_name", help="租户名称")
    p.add_argument("--cluster-name", dest="cluster_name", help="集群显示名称（默认 tke-cluster）")
    p.add_argument("--duration", help="Token 有效期（默认 8760h）")
    p.set_defaults(func=cmd_prompt_generate)

    # ---- Helm 操作 ----

    # helm-install
    p = subparsers.add_parser("helm-install", parents=[common_parser], help="安装 Helm Chart")
    p.add_argument("release", help="Release 名称")
    p.add_argument("chart", help="Chart 名称或路径（如 bitnami/nginx 或 ./mychart）")
    p.add_argument("-f", "--values", nargs="*", help="values 文件路径（可多个）")
    p.add_argument("--set", nargs="*", help="覆盖 values（如 image.tag=v1.0）")
    p.add_argument("--version", help="Chart 版本")
    p.add_argument("--repo", help="Chart 仓库 URL")
    p.add_argument("--create-namespace", dest="create_namespace", action="store_true", help="自动创建命名空间")
    p.add_argument("--wait", action="store_true", help="等待所有资源就绪")
    p.add_argument("--timeout", help="超时时间（如 5m0s）")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="试运行")
    p.add_argument("--atomic", action="store_true", help="失败时自动回滚")
    p.set_defaults(func=cmd_helm_install)

    # helm-upgrade
    p = subparsers.add_parser("helm-upgrade", parents=[common_parser], help="升级 Helm Release")
    p.add_argument("release", help="Release 名称")
    p.add_argument("chart", help="Chart 名称或路径")
    p.add_argument("-f", "--values", nargs="*", help="values 文件路径")
    p.add_argument("--set", nargs="*", help="覆盖 values")
    p.add_argument("--version", help="Chart 版本")
    p.add_argument("--repo", help="Chart 仓库 URL")
    p.add_argument("--install", action="store_true", help="如果 Release 不存在则安装")
    p.add_argument("--wait", action="store_true", help="等待所有资源就绪")
    p.add_argument("--timeout", help="超时时间")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="试运行")
    p.add_argument("--atomic", action="store_true", help="失败时自动回滚")
    p.add_argument("--reuse-values", dest="reuse_values", action="store_true", help="复用上次的 values")
    p.set_defaults(func=cmd_helm_upgrade)

    # helm-uninstall
    p = subparsers.add_parser("helm-uninstall", parents=[common_parser], help="卸载 Helm Release")
    p.add_argument("release", help="Release 名称")
    p.add_argument("--keep-history", dest="keep_history", action="store_true", help="保留发布历史")
    p.add_argument("--wait", action="store_true", help="等待删除完成")
    p.add_argument("--timeout", help="超时时间")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="试运行")
    p.set_defaults(func=cmd_helm_uninstall)

    # helm-list
    p = subparsers.add_parser("helm-list", parents=[common_parser], help="列出 Helm Release")
    p.add_argument("-A", "--all-namespaces", dest="all_namespaces", action="store_true", help="查看所有命名空间")
    p.add_argument("--all", action="store_true", help="显示所有状态的 Release")
    p.add_argument("-o", "--output", choices=["table", "json", "yaml"], help="输出格式")
    p.add_argument("--filter", help="按名称过滤（支持正则）")
    p.set_defaults(func=cmd_helm_list)

    # helm-status
    p = subparsers.add_parser("helm-status", parents=[common_parser], help="查看 Helm Release 状态")
    p.add_argument("release", help="Release 名称")
    p.add_argument("-o", "--output", choices=["table", "json", "yaml"], help="输出格式")
    p.add_argument("--show-resources", dest="show_resources", action="store_true", help="显示关联的 K8s 资源")
    p.set_defaults(func=cmd_helm_status)

    # 解析并执行
    # exec 特殊处理：在 argparse 解析前，手动拆分 -- 后的容器命令
    # 这样 argparse 只解析 -- 前的参数，避免 REMAINDER 吞掉 --kubeconfig 等选项
    argv = sys.argv[1:]
    exec_command = []
    if len(argv) > 0 and argv[0] == "exec":
        if "--" in argv:
            sep_idx = argv.index("--")
            exec_command = argv[sep_idx + 1:]  # -- 后面的部分
            argv = argv[:sep_idx]              # -- 前面的部分

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # exec 命令：将拆分出的容器命令挂到 args 上
    if args.command == "exec":
        args._exec_command = exec_command
        if not exec_command:
            print("错误：请指定要执行的命令，如：exec my-pod -n default -- ls /app", file=sys.stderr)
            sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)
    except (subprocess.SubprocessError, json.JSONDecodeError,
            OSError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
