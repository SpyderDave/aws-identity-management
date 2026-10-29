# Sceptre Configuration

This directory is the **Sceptre** configuration tree for the AWS Identity Management
project. [Sceptre](https://docs.sceptre-project.io/) is a thin orchestration layer over AWS
CloudFormation: it reads a tree of YAML config files, resolves their parameters, picks the
matching template from [`templates/`](../templates/), and creates/updates/deletes the resulting
CloudFormation stacks in the right order.

This document explains **how Sceptre config is structured and resolved in this repo** and how it
is driven from GitHub Actions. For the inventory of *what* the core stacks actually deploy
(permission sets, group assignments, templates), see [`core/README.md`](core/README.md). For how
deployments are triggered, see the [top-level README](../README.md).

## The config tree

```text
config/
├── config.yaml      # Top-level StackGroup config (project-wide settings + shared stack_tags)
├── core/            # A StackGroup — core SSO components & org-wide assignments
│   ├── permission-sets.yaml    # A Stack config
│   ├── ssofunctions.yaml       # A Stack config
│   └── <team>-<permission>.yaml  # Stack configs (one per group→permission)
├── nonp/        # A StackGroup — per-account nonp assignments
└── prod/          # A StackGroup — per-account production assignments
    └── product/     # Sub-group — product-specific permission sets
```

Common **stack tags** are defined once in the top-level `config/config.yaml` and inherited by
**every** stack in the tree (see [Project-wide settings](#project-wide-settings-configyaml) below).
CloudFormation **parameters** are declared per stack config, since each template accepts a
different set.

> **Note on shared `{% include %}` files:** earlier revisions kept `stack_tags.txt` and
> `sso-params.txt` at the `config/` root and pulled them in with `{% include '../stack_tags.txt' %}`.
> That pattern **cannot work** in Sceptre: it roots the Jinja2 loader at each config file's *own*
> directory, and Jinja2's `FileSystemLoader` rejects any `..` path segment (raises
> `TemplateNotFound`). The shared tags now live in `config.yaml` (inherited) and parameters are
> inlined in each stack config.

Two kinds of files live here:

- **StackGroup config** — `config.yaml`. There is one per directory level. Settings defined here
  are **inherited** by every stack config beneath it. The top-level `config/config.yaml` therefore
  applies to the whole project.
- **Stack config** — every other `*.yaml` file under a group (e.g. `core/permission-sets.yaml`).
  Each one describes a single CloudFormation stack: which template to use, its parameters, its
  dependencies, and its behaviour on failure.

A folder such as `core/` is a **StackGroup**: Sceptre can act on the whole group at once
(`sceptre launch core`) or on a single stack (`sceptre launch core/permission-sets.yaml`).

## Project-wide settings (`config.yaml`)

```yaml
project_code: aws-identity-management
region: ca-central-1

stack_tags:
    application: sso
    role: org-prod
```

- **`project_code`** – prefixed onto generated CloudFormation stack names, so every stack in this
  project is namespaced under `aws-identity-management-*`.
- **`region`** – the AWS region all stacks deploy into (`ca-central-1`).
- **`stack_tags`** – tags applied to every CloudFormation stack. Defining them here means a single
  edit re-tags the whole project; no per-config include is needed.

Because these live in the top-level StackGroup config, every stack under `config/` inherits them
unless a deeper config overrides them.

## Anatomy of a stack config

A stack config wires a template to its inputs. Using `core/operations-support.yaml` as an example:

```yaml
template_path: core/all-accounts.py          # template under templates/, relative to templates/
sceptre_role_session_duration: 7200           # how long the assumed deploy role stays valid
dependencies:
  - core/permission-sets.yaml                 # stacks that must exist first
ignore: false                                 # whether Sceptre skips this stack
on_failure: ROLLBACK                          # CloudFormation behaviour on a failed create
                                              # (common stack_tags are inherited from config.yaml)
sceptre_user_data:                            # arbitrary data passed to a Python template
  rolearn: {{environment_variable.AWS_ROLE}}
  SSOInstanceId: {{environment_variable.SSOINSTANCEID}}
  SSOInstanceArn: {{environment_variable.SSOINSTANCEARN}}
  SSMPrefix: "/platform/sso/permissionsets/org"
  GroupName: "core-group-01"
  Permission: "OperationsSupport"
```

Key fields used across this repo:

| Key | What it does |
| --- | --- |
| `template_path` | Path to the template **relative to `templates/`**. This repo uses both CloudFormation YAML (`core/sso-permission-sets.yaml`) and Python/troposphere templates (`core/all-accounts.py`). |
| `parameters` | Values passed to **CloudFormation template parameters** (used by the YAML templates, e.g. `permission-sets.yaml`). |
| `sceptre_user_data` | Arbitrary data passed to **Python templates** at generation time (used by the `all-accounts.py` assignment template). |
| `dependencies` | Other stack configs that must be deployed first. Sceptre builds a dependency graph and deploys in order. Every assignment depends on `core/permission-sets.yaml`. |
| `ignore` | When `true`, Sceptre skips this stack during group operations (`launch`/`delete`); set `false` to activate. The core assignment stacks currently all run with `ignore: false`. (Nonp stacks use `obsolete: True` instead to park a retired stack.) |
| `on_failure` | CloudFormation rollback behaviour on a failed create — `ROLLBACK` or `DO_NOTHING`. |
| `sceptre_role_session_duration` | Lifetime (seconds) of the assumed deployment role's session — raised to `7200` for the assignment stacks because they enumerate the whole org. |

## Jinja templating and variable resolution

Sceptre renders every config file through **Jinja2 before parsing the YAML**, which is how this
repo injects secrets at deploy time.

### Shared content: inheritance, not `{% include %}`

Common values are **not** shared via Jinja includes. Sceptre roots the Jinja2 loader at each config
file's *own* directory, and Jinja2's `FileSystemLoader` rejects any `..` segment, so a parent-level
`{% include '../stack_tags.txt' %}` always fails with `TemplateNotFound`. Instead:

- **Stack tags** are defined once in `config/config.yaml` under `stack_tags:` and **inherited** by
  every stack. Editing that one block re-tags the whole project.
- **CloudFormation parameters** are declared in each stack config's `parameters:` block, because
  each template accepts a different set (e.g. the assignment template needs `AssignmentFunction`;
  the permission-set template does not — and CloudFormation rejects undeclared parameters).

### `{{ environment_variable.X }}` for runtime/secret values

```jinja
rolearn: {{environment_variable.AWS_ROLE}}
SSOInstanceId: {{environment_variable.SSOINSTANCEID}}
SSOInstanceArn: {{environment_variable.SSOINSTANCEARN}}
```

The `environment_variable` resolver reads from the **process environment** at deploy time. Nothing
account-specific or secret is committed to the repo — the SSO instance identifiers and deploy role
are provided by the GitHub Environment when the pipeline runs (see below). The expected variables
are:

| Variable | Meaning |
| --- | --- |
| `AWS_ROLE` | ARN of the role assumed in the org-prod account. |
| `SSOINSTANCEID` | IAM Identity Center (Identity Store) instance ID. |
| `SSOINSTANCEARN` | IAM Identity Center instance ARN. |

## How GitHub Actions drives Sceptre

These configs are **not** run by hand in normal operation. The
[`core-deployment.yml`](../.github/workflows/core-deployment.yml) workflow handles deployment, and
it does **not** call Sceptre directly — it delegates to a shared **sceptre-deploy** action
(`your-org/shared-actions/aws/sceptre-deploy@v1`), which wraps Sceptre.

The flow:

1. **Trigger** — a push to `nonp`/`prod` touching `config/core/**` or `templates/core/**`,
   a PR closed against `prod`, or a manual `workflow_dispatch`.
2. **Environment** — the job binds to a GitHub **Environment** (`nonp` or `prod`). This is
   where `AWS_ROLE`, `SSOINSTANCEID`, and `SSOINSTANCEARN` come from as `vars`, and where the
   sceptre-deploy secrets live. These `vars` are exported into the job's environment so that
   `{{ environment_variable.* }}` in the configs resolves correctly.
3. **AWS credentials** — the workflow assumes `vars.AWS_ROLE` via OIDC (`ca-central-1`).
4. **sceptre-deploy → Sceptre** — the sceptre-deploy step runs against the `core` StackGroup with a
   **build stage**:
   - `validate` – render and validate templates/config without changing anything.
   - `build` – create/update the stacks (the actual deploy; forced on automatic pushes).
   - `teardown` – delete the stacks.

So the mental model is: **GitHub Environment supplies the env vars → Jinja resolves them into the
configs → sceptre-deploy runs Sceptre → Sceptre orders the stacks by their `dependencies` and applies
the CloudFormation.**

## Running Sceptre locally (optional)

The pipeline is the supported path, but you can render/inspect configs locally if you have Sceptre
installed and the same environment variables exported:

```bash
export AWS_ROLE=arn:aws:iam::<org-prod-acct>:role/<deploy-role>
export SSOINSTANCEID=<d-xxxxxxxxxx>
export SSOINSTANCEARN=arn:aws:sso:::instance/ssoins-xxxxxxxxxxxx

# Validate everything in the core group without applying:
sceptre validate core

# Show the CloudFormation a single stack would produce:
sceptre generate core/permission-sets.yaml

# Create/update (this changes AWS — prefer the pipeline):
sceptre launch core/permission-sets.yaml
```

> A stack with `ignore: true` (core) or `obsolete: True` (nonp) is skipped by group-level
> commands. Target a stack by path, or clear that flag, to act on one explicitly.

## Adding or changing config

1. Add or edit a stack config under [`core/`](core/) (copy an existing one as a starting point).
2. Reference an existing template in `template_path`, supply `parameters` (CFN templates) or
   `sceptre_user_data` (Python templates), and declare any `dependencies`.
3. Keep secrets/instance values as `{{ environment_variable.* }}` — never hard-code them.
4. Set `ignore: false` when the stack should actually deploy.
5. Merge via the pipeline — `nonp` first to validate in the nonp environment, then
   `prod`. See the [top-level README](../README.md) and [`core/README.md`](core/README.md).
