# Drift Detection Deployment Guide

The drift detection stack is deployed as a standard Sceptre stack, just like all other stacks in your pipeline.

## Automatic Deployment (Recommended)

The stack deploys automatically with your core stack deployment:

1. Merge changes to prod or nonp branch
2. GitHub Actions triggers the core deployment workflow
3. Drift detection stack deploys along with other core stacks

## Manual Deployment via Sceptre

```bash
sceptre deploy config/core/drift-detection.yaml
```

Validate before deploying:

```bash
sceptre validate config/core/drift-detection.yaml
```

Delete the stack (if needed):

```bash
sceptre delete config/core/drift-detection.yaml
```

## Configuration

Edit `config/core/drift-detection.yaml` to customize:

### Change Drift Schedule

```yaml
parameters:
  DriftCheckSchedule: "cron(0 */12 * * ? *)"  # Every 12 hours
```

Schedule examples:

| Schedule | Cron Expression |
|----------|-----------------|
| Daily at 8 AM UTC | `cron(0 8 * * ? *)` |
| Every 6 hours | `cron(0 */6 * * ? *)` |
| Every 12 hours | `cron(0 */12 * * ? *)` |
| Weekdays 9 AM | `cron(0 9 ? * MON-FRI *)` |
| Business hours (9-5) | `cron(0 9-17 ? * MON-FRI *)` |

### Update Slack Webhook

The webhook is provided via the `SLACK_WEBHOOK_URL` environment variable, which GitHub Actions passes from your `SLACK_WEBHOOK` secret.

If needed to use a different webhook, update the environment variable in your GitHub Actions workflow.

## Monitoring

### View Logs

```bash
aws logs tail /aws/lambda/cf-drift-detection --follow --region ca-central-1
```

### Check Lambda Invocations

```bash
aws lambda list-functions --query "Functions[?FunctionName=='cf-drift-detection']"
```

### Manual Test

```bash
aws lambda invoke \
  --function-name cf-drift-detection \
  --region ca-central-1 \
  /tmp/response.json

cat /tmp/response.json
```

Expected response:

```json
{
  "statusCode": 200,
  "drifted_stacks": 0,
  "total_stacks": 42,
  "message": "No drift detected"
}
```

## Stack Components

| Component | Details |
|-----------|---------|
| Lambda Function | `cf-drift-detection` - Detects drift and sends Slack alerts |
| EventBridge Rule | `cf-drift-detection-daily` - Triggers Lambda on schedule |
| IAM Role | Allows Lambda to check CloudFormation drift and access Parameter Store |
| SSM Parameter | `/drift-detection/slack-webhook` - Stores webhook URL securely |

## Drift Detection Logic

The Lambda function:

1. Queries all CloudFormation stacks in the region
2. Filters to stacks with `managed-by: github-actions` tag
3. Runs drift detection on each stack
4. Collects results
5. Sends Slack alert if any drift detected

**Only stacks deployed via Sceptre pipeline are checked** (they have the `managed-by: github-actions` tag from your Sceptre config).

## Slack Notifications

### When You Get Alerts

- **Drift Detected**: Slack alert shows stack name, drifted resource count, and timestamp
- **Errors**: Slack alert with error details
- **No Drift**: Silent (no alert)

### Alert Format

```
🚨 CloudFormation Drift Detected

2 stack(s) have drifted from their templates

prod-core-iam-roles
Resources Drifted: 3/15
Detected: 2026-07-30T08:30:45.123456

core-dns-config
Resources Drifted: 1/5
Detected: 2026-07-30T08:32:10.654321
```

## Troubleshooting

### Stack Won't Deploy

Check Sceptre validation:

```bash
sceptre validate config/core/drift-detection.yaml
```

Check for stack naming conflicts:

```bash
aws cloudformation describe-stacks \
  --query "Stacks[?StackName=='*drift*']" \
  --region ca-central-1
```

### Lambda Not Running

Check if EventBridge rule is enabled:

```bash
aws events describe-rule --name cf-drift-detection-daily --region ca-central-1
```

Enable if disabled:

```bash
aws events enable-rule --name cf-drift-detection-daily --region ca-central-1
```

### No Slack Alerts

Check Lambda logs:

```bash
aws logs tail /aws/lambda/cf-drift-detection --region ca-central-1
```

Verify Slack webhook is stored:

```bash
aws ssm get-parameter --name /drift-detection/slack-webhook --with-decryption --region ca-central-1
```

### Lambda Timeouts

If Lambda times out on large deployments, increase timeout in the template (currently 300 seconds).

Edit `templates/core/drift-detection.yaml`:

```yaml
Timeout: 600  # 10 minutes
```

## Cost

| Component | Cost |
|-----------|------|
| Lambda invocations | ~$0.00 (within free tier) |
| CloudFormation API calls | Minimal |
| CloudWatch Logs | <$0.01/month |
| EventBridge rule | ~$0.00 |
| **Total** | **<$0.10/month** |

## Files Reference

- `templates/core/drift-detection.yaml` - CloudFormation template
- `config/core/drift-detection.yaml` - Sceptre configuration
- `README.md` - Quick reference
- `DEPLOYMENT_GUIDE.md` - This file
- `IMPLEMENTATION_SUMMARY.md` - Architecture details
