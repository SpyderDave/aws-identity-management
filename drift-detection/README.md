# CloudFormation Drift Detection with Slack Notifications

Automated drift detection for CloudFormation stacks deployed by your Sceptre pipeline, with Slack alerts.

## Deployment

The drift detection stack is deployed via Sceptre, just like your other stacks.

### Via GitHub Actions (Automatic)

The stack deploys automatically when you merge changes to the `core/` config or when you trigger a core deployment via GitHub Actions. Additionally, the **Core Components and Common Assignments - Deploy** workflow runs on a [weekly schedule every Sunday night ET](../.github/workflows/core-deployment.yml) to ensure drift detection stays current.

To manually trigger:

1. Go to GitHub → Actions → Select your core deployment workflow (e.g., "Core - Deploy")
2. Click "Run workflow"
3. Deployment includes the drift detection stack automatically

### Via Sceptre CLI (Manual)

```bash
sceptre deploy config/core/drift-detection.yaml
```

## Configuration

The stack is configured in `config/core/drift-detection.yaml`:

```yaml
parameters:
  SlackWebhookUrl: !environment_variable SLACK_WEBHOOK_URL
  DriftCheckSchedule: "cron(0 8 * * ? *)"
```

### Change Drift Detection Schedule

Edit `config/core/drift-detection.yaml`:

```yaml
parameters:
  DriftCheckSchedule: "cron(0 */6 * * ? *)"  # Every 6 hours
```

Common cron expressions:

- `cron(0 8 * * ? *)` - Daily at 8 AM UTC
- `cron(0 */6 * * ? *)` - Every 6 hours
- `cron(0 9 ? * MON-FRI *)` - Weekdays at 9 AM UTC

## How It Works

1. **Deployment Schedule** - The core deployment stack (including drift detection) is deployed weekly on Sunday nights ET via GitHub Actions
2. **EventBridge Schedule** - EventBridge triggers Lambda at 8 AM UTC daily to check for drift (configurable in `drift-detection.yaml`)
3. **Stack Detection** - Finds all stacks with `managed-by: github-actions` tag
4. **Drift Check** - Runs CloudFormation drift detection on each stack
5. **Slack Alert** - Sends notification if drift is detected

## What Gets Checked

Only stacks deployed by your Sceptre pipeline are checked (tagged with `managed-by: github-actions`).

To see which stacks will be monitored:

```bash
aws cloudformation describe-stacks \
  --region ca-central-1 \
  --query "Stacks[?Tags[?Key=='managed-by' && Value=='github-actions']].StackName" \
  --output table
```

## Testing

### Manual Lambda Invocation

```bash
aws lambda invoke \
  --function-name cf-drift-detection \
  --region ca-central-1 \
  /tmp/response.json

cat /tmp/response.json
```

### View Logs

```bash
# Real-time logs
aws logs tail /aws/lambda/cf-drift-detection --follow --region ca-central-1
```

## Stack Details

- **Template**: `templates/core/drift-detection.yaml`
- **Config**: `config/core/drift-detection.yaml`
- **Lambda**: `cf-drift-detection`
- **EventBridge Rule**: `cf-drift-detection-daily`
- **Logs**: `/aws/lambda/cf-drift-detection`

## References

- [CloudFormation Drift Detection Docs](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html)
- [EventBridge Cron Expressions](https://docs.aws.amazon.com/eventbridge/latest/userguide/scheduled-rules.html)
