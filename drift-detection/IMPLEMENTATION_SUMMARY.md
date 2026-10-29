# Drift Detection Implementation Summary

## Overview

Sceptre-based CloudFormation drift detection with automated Slack notifications for stacks deployed via your pipeline.

## Architecture

The drift detection stack is deployed like any other core stack:

```
GitHub Actions (core deployment)
  ↓
Sceptre (config/core/drift-detection.yaml)
  ↓
CloudFormation Stack
  ├── Lambda: cf-drift-detection
  ├── EventBridge: cf-drift-detection-daily (8 AM UTC)
  ├── IAM Role: Permissions for CloudFormation + SSM access
  └── SSM Parameter: Slack webhook URL
  ↓
Daily Schedule
  ↓
Lambda runs drift detection
  ├── Find stacks with managed-by: github-actions tag
  ├── Run CloudFormation drift detection
  └── Send Slack alert if drift detected
```

## Files

| File | Purpose |
|------|---------|
| `config/core/drift-detection.yaml` | Sceptre stack configuration |
| `templates/core/drift-detection.yaml` | CloudFormation template |
| `README.md` | Quick reference |
| `DEPLOYMENT_GUIDE.md` | Detailed guide |

## Deployment

### Automatic (Recommended)

Drift detection deploys automatically with core stacks:

1. Changes merged to prod/nonp
2. GitHub Actions runs core deployment workflow
3. Sceptre deploys all core stacks including drift-detection
4. Done!

### Manual

```bash
sceptre deploy config/core/drift-detection.yaml
```

## How It Works

1. **EventBridge Rule** - Triggers daily at 8 AM UTC
2. **Lambda Function** - Detects drift for pipeline-managed stacks
3. **Stack Filtering** - Only checks stacks with `managed-by: github-actions` tag (auto-applied by Sceptre)
4. **Slack Alert** - Sends notification if drift detected

## Configuration

### Drift Schedule

Edit `config/core/drift-detection.yaml`:

```yaml
parameters:
  DriftCheckSchedule: "cron(0 */6 * * ? *)"  # Change to every 6 hours
```

### Slack Webhook

Provided via `SLACK_WEBHOOK_URL` environment variable from GitHub Actions `SLACK_WEBHOOK` secret.

No manual configuration needed - uses your existing secret.

## Key Features

✅ **Integrated with Sceptre Pipeline**
- Deploys like all other core stacks
- Uses same tags and parameters
- Managed in version control
- Part of GitHub Actions workflow

✅ **Automatic Stack Discovery**
- Detects all stacks with `managed-by: github-actions` tag
- No manual configuration needed
- Works for all Sceptre-deployed stacks

✅ **Smart Slack Notifications**
- Only alerts when drift detected
- Shows drifted resource count and timestamps
- Error alerts included

✅ **Secure**
- Webhook stored encrypted in Parameter Store
- IAM least-privilege permissions
- No hardcoded secrets

## Monitoring

### View Logs

```bash
aws logs tail /aws/lambda/cf-drift-detection --follow
```

### Test Lambda

```bash
aws lambda invoke --function-name cf-drift-detection /tmp/response.json && cat /tmp/response.json
```

### Check Stacks Being Monitored

```bash
aws cloudformation describe-stacks \
  --region ca-central-1 \
  --query "Stacks[?Tags[?Key=='managed-by' && Value=='github-actions']].StackName" \
  --output table
```

## Cost

Minimal cost (<$0.10/month):
- Lambda: Free tier covers invocations
- CloudFormation API: Minimal cost
- CloudWatch Logs: <$0.01/month
- EventBridge: ~$0.00

## Troubleshooting

**Stack won't deploy**: Run `sceptre validate config/core/drift-detection.yaml`

**Lambda not running**: Check EventBridge rule is enabled

**No Slack alerts**: Check Lambda logs and verify webhook is stored

**Stacks not detected**: Verify they have `managed-by: github-actions` tag

See `DEPLOYMENT_GUIDE.md` for detailed troubleshooting.

## Next Steps

1. The stack is ready to deploy with your core stacks
2. Merge to prod/nonp to trigger GitHub Actions deployment
3. Or run `sceptre deploy config/core/drift-detection.yaml` manually
4. Drift detection runs automatically every day at 8 AM UTC

That's it! 🎉
