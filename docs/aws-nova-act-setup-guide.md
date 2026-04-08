# AWS Nova Act Setup Guide (Console + IAM)

This guide covers what you need from the AWS console, how to set up IAM (users/groups/roles) for Nova Act, **region restrictions**, and step-by-step setup so you can use Nova Act for the dealership agent (e.g. car discovery workflow).

---

## 1. Region and location restrictions

- **Nova Act is only available in one region:** **US East (N. Virginia)** — `us-east-1`.
- There is **no** Nova Act in other regions (e.g. `us-west-2`, `eu-west-1`). Your workflow definitions and runs must be in `us-east-1`.
- **Console:** You must switch the AWS Console to **US East (N. Virginia)** (top-right region selector) to see the Nova Act service.
- **CLI/SDK:** Set `AWS_REGION=us-east-1` or `--region us-east-1` when invoking Nova Act APIs.
- **GovCloud:** Other Nova models exist in GovCloud (US-West); Nova Act GA is **us-east-1** only.

---

## 2. What details you need from the AWS console (for your app)

After setup, your backend will need these (store in env or config, **never in code**):

| What you need | Where to get it | Used for |
|---------------|------------------|----------|
| **AWS Region** | Fixed: `us-east-1` | All Nova Act API calls |
| **AWS Account ID** | Console: click your account name (top right) → “Account ID”, or from ARNs in IAM/Nova Act | ARNs, logging |
| **Workflow definition name** | Nova Act console → **Workflow definitions** → your workflow’s **Name** | Invoking the right workflow when you call `CreateWorkflowRun` |
| **IAM credentials** | IAM user access keys **or** IAM role (e.g. EC2 instance role, Lambda execution role) that has Nova Act permissions | Backend calling Nova Act APIs |

You do **not** need to copy “workflow ARN” for basic invoke: the API takes workflow definition **name** and creates runs under it. ARN is useful for IAM resource-level restrictions.

---

## 3. IAM: What Nova Act supports

- **Identity-based policies:** Yes (attach to user, group, or role).
- **Policy actions:** Prefix `nova-act:*` (e.g. `nova-act:CreateWorkflowRun`, `nova-act:GetWorkflowRun`).
- **Policy resources:** Workflow definitions and workflow runs (ARNs).
- **Resource-based policies:** **No** (you can’t attach a policy to a “workflow” resource to allow another account).
- **Service-linked role:** Yes. Nova Act creates a **service-linked role** (with `NovaActServiceRolePolicy`) when you first use the service; it’s for the service to publish metrics to CloudWatch. You don’t attach this to your users.

**Important:** AWS does **not** ship a managed policy like `AmazonNovaActFullAccess`. You must create a **customer-managed policy** (or inline) that grants the Nova Act actions you need.

---

## 4. Setting up IAM groups (and users/roles) for Nova Act

### Option A: IAM group for “Nova Act console + run workflows” (recommended for hackathon)

Use this if your team members use the **console** to view workflows and runs, and your **backend** uses an IAM user or role to invoke workflows.

**Step 1: Create a customer-managed policy for Nova Act**

1. In AWS Console, go to **IAM** → **Policies** → **Create policy**.
2. Open the **JSON** tab and paste:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "nova-act:*"
            ],
            "Resource": [
                "*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "iam:CreateServiceLinkedRole",
            "Resource": "*",
            "Condition": {
                "StringLike": {
                    "iam:AWSServiceName": "nova-act.amazonaws.com"
                }
            }
        }
    ]
}
```

3. **Next** → Name the policy (e.g. `NovaActFullAccess`) → **Create policy**.

The second statement allows the first use of Nova Act in the account to create the service-linked role; after that it’s not needed for normal runs.

**Step 2: Create an IAM group and attach the policy**

1. **IAM** → **User groups** → **Create group**.
2. Group name: e.g. `NovaActUsers`.
3. Attach the policy you created: search for `NovaActFullAccess` (or whatever you named it) → **Create group**.

**Step 3: Add users (or use a role for the app)**

- **For console access:** IAM → **Users** → select user → **Add to group** → choose `NovaActUsers`. Those users can use the Nova Act console in `us-east-1` and run/list workflows if they have no other restrictions.
- **For backend (e.g. EC2/Lambda):** Prefer an **IAM role** with the same policy attached (e.g. `NovaActExecutionRole`). Attach the role to the EC2 instance or Lambda; no long-term access keys.

**Optional – restrict to one region:** Add a condition so Nova Act is only callable in `us-east-1`:

```json
{
    "Effect": "Allow",
    "Action": ["nova-act:*"],
    "Resource": "*",
    "Condition": {
        "StringEquals": {
            "aws:RequestedRegion": "us-east-1"
        }
    }
}
```

---

### Option B: Least-privilege policy (invoke only, no create/delete)

If you want the **backend** only to run existing workflows and read runs (no create/delete workflow definitions):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "nova-act:CreateWorkflowRun",
                "nova-act:GetWorkflowRun",
                "nova-act:ListWorkflowRuns",
                "nova-act:GetWorkflowDefinition",
                "nova-act:ListWorkflowDefinitions"
            ],
            "Resource": "*"
        }
    ]
}
```

You can restrict `Resource` to specific workflow definition ARNs if you have them (e.g. `arn:aws:nova-act:us-east-1:123456789012:workflow-definition/YourWorkflowName`).

---

## 5. Step-by-step: First-time Nova Act setup on the console

Do this in **US East (N. Virginia)**.

### 5.1 Confirm region and enable access

1. Log in to **AWS Management Console**.
2. Set region to **US East (N. Virginia)** (top-right).
3. Ensure your IAM user/role has the Nova Act policy (e.g. via the `NovaActUsers` group or a role with `NovaActFullAccess`).

### 5.2 Open Nova Act

1. In the search bar, type **Nova Act** and open **Amazon Nova Act**.
2. If you don’t see it, check (a) region is `us-east-1`, (b) your account is allowed to use Nova Act, (c) your IAM principal has the `nova-act:*` (or equivalent) policy.

### 5.3 Service-linked role (first use only)

1. When you first create a workflow definition or run a workflow, Nova Act may create the **service-linked role** for Nova Act (for CloudWatch metrics).
2. If prompted, allow **CreateServiceLinkedRole** (that’s what the second statement in the policy in Section 4 is for). You only need to do this once per account.

### 5.4 Deploy a workflow (outside console: IDE/CLI)

- **Workflow definitions** in the console are created when you **deploy** from the Nova Act IDE extension or CLI (not by clicking “Create” in the console UI in the same way as some other services). So:

1. **Develop** the workflow (e.g. in Cursor/VS Code with the Nova Act extension, or via Nova Act Playground then export).
2. **Deploy** to AWS via the extension’s “Deploy” or the Nova Act CLI. That will:
   - Build the container and push to **ECR** (in your account).
   - Create/use an **S3** bucket (e.g. `nova-act-{account-id}-{region}`).
   - Create/use **IAM roles** for the workflow execution (Bedrock AgentCore).
   - Register the **workflow definition** in Nova Act.

3. After deployment, in **Nova Act** → **Workflow definitions** you’ll see your workflow. Note its **Name** — that’s the value your backend will pass when calling `CreateWorkflowRun`.

### 5.5 What you’ll see in the console

- **Workflow definitions:** List of deployed workflows (name, ARN, etc.).
- **Workflow runs:** Per workflow, list of runs with status, start/end time, inputs/outputs (or pointer to S3 artifacts).
- **Observability:** Traces, steps, browser screenshots (depending on how the run is configured).

---

## 6. Details your app will need (summary)

- **Region:** `us-east-1` (required).
- **Workflow definition name:** From Nova Act console after first deploy (e.g. `car-search-workflow`).
- **Credentials:** IAM user access keys **or** IAM role (e.g. `NovaActExecutionRole`) with the Nova Act policy attached. Prefer role for backend.
- **Optional:** Account ID (for ARNs or logging).

**No** separate “Nova Act API key” for the AWS service path — authentication is IAM only. (The **Playground** at nova.amazon.com/act can use an API key; that’s separate from the AWS Nova Act service.)

---

## 7. Checklist

- [ ] AWS Console region set to **US East (N. Virginia)** for Nova Act.
- [ ] Customer-managed IAM policy created (e.g. `NovaActFullAccess` with `nova-act:*` and optional `iam:CreateServiceLinkedRole`).
- [ ] IAM group (e.g. `NovaActUsers`) created and policy attached; users who need console access added to the group.
- [ ] Backend: IAM role or user with same (or least-privilege) policy; credentials via env (e.g. `AWS_REGION=us-east-1`, profile or role).
- [ ] Workflow developed and deployed via extension/CLI; workflow **name** noted for `CreateWorkflowRun`.
- [ ] Optional: Restrict policy with `aws:RequestedRegion = us-east-1`.

Once this is done, you can implement the backend service that calls `CreateWorkflowRun` (and polls `GetWorkflowRun`) with the workflow name and your search parameters (zip, make, model, etc.) as input.
