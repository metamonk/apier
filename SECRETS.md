# Secrets Management

This document describes how secrets are managed in the Zapier Triggers API.

## Overview

All sensitive credentials are stored in **AWS Secrets Manager** and retrieved at runtime by the Lambda function. Secrets are **never** committed to Git.

## Secret Location

**Production Environment:**
- Secret Name: `zapier-api-credentials-amplify-dmmfqlsr845yz-main-branch-6ca37098e7-apistack7B433BC7-MMMAWD4LJ6AL`
- Region: `us-east-2`
- ARN: `arn:aws:secretsmanager:us-east-2:971422717446:secret:zapier-api-credentials-*`

**Development Environment:**
- Will be created when `dev` branch is deployed
- Same naming pattern with `-dev-` infix

## Secret Structure

```json
{
  "environment": "production|development",
  "jwt_secret": "auto-generated-secure-string",
  "zapier_api_key": "your-zapier-api-key",
  "zapier_webhook_url": "https://hooks.zapier.com/hooks/catch/xxx/yyy"
}
```

### Field Descriptions

- **environment**: Environment identifier (`production` or `development`)
- **jwt_secret**: Auto-generated 32-character secret for JWT signing (do not change unless rotating)
- **zapier_api_key**: Your Zapier API key for authentication
- **zapier_webhook_url**: Zapier webhook URL for sending events

## Viewing Secrets

### Via AWS Console

1. Go to **AWS Secrets Manager** in us-east-2
2. Search for `zapier-api-credentials`
3. Click on the secret
4. Click "Retrieve secret value"

### Via AWS CLI

```bash
# View secret
aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-amplify-dmmfqlsr845yz-main-branch-6ca37098e7-apistack7B433BC7-MMMAWD4LJ6AL \
  --region us-east-2 \
  --query SecretString --output text | jq .
```

## Updating Secrets

### Method 1: AWS Console (Recommended)

1. Go to **AWS Secrets Manager** → Your secret
2. Click "Retrieve secret value"
3. Click "Edit"
4. Update the JSON values
5. Click "Save"

### Method 2: AWS CLI

```bash
# Update the entire secret
aws secretsmanager update-secret \
  --secret-id zapier-api-credentials-amplify-dmmfqlsr845yz-main-branch-6ca37098e7-apistack7B433BC7-MMMAWD4LJ6AL \
  --region us-east-2 \
  --secret-string '{
    "environment": "production",
    "jwt_secret": "hO3j[2=GK6L97yF2=is0F(nU{{PNPlvX",
    "zapier_api_key": "YOUR_ACTUAL_ZAPIER_API_KEY",
    "zapier_webhook_url": "https://hooks.zapier.com/hooks/catch/YOUR/WEBHOOK"
  }'
```

**Important:** Keep the `jwt_secret` value unless you're intentionally rotating it.

## Initial Setup

After deploying to a new environment, you must update the placeholder values:

1. **Get your Zapier API Key:**
   - Log in to Zapier
   - Go to Settings → API Keys
   - Generate a new API key

2. **Get your Zapier Webhook URL:**
   - Create a Zap with "Webhooks by Zapier" as the trigger
   - Choose "Catch Hook"
   - Copy the webhook URL

3. **Update the secret:**
   ```bash
   aws secretsmanager update-secret \
     --secret-id zapier-api-credentials-* \
     --region us-east-2 \
     --secret-string '{
       "environment": "production",
       "jwt_secret": "<keep-existing-value>",
       "zapier_api_key": "<your-zapier-api-key>",
       "zapier_webhook_url": "<your-zapier-webhook-url>"
     }'
   ```

## Testing Secret Access

You can verify the Lambda function can read secrets by calling:

```bash
curl https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/config
```

Expected response:
```json
{
  "environment": "production",
  "zapier_configured": true,
  "webhook_configured": true,
  "jwt_configured": true,
  "cache_hit": true
}
```

## Secret Rotation

### JWT Secret Rotation

**When to rotate:**
- Security breach
- Compliance requirements
- Scheduled rotation (e.g., every 90 days)

**How to rotate:**

1. Update the secret with a new `jwt_secret` value
2. Restart the Lambda function (or wait for cold start)
3. All existing JWT tokens will be invalidated

```bash
aws secretsmanager update-secret \
  --secret-id zapier-api-credentials-* \
  --region us-east-2 \
  --secret-string '{
    "environment": "production",
    "jwt_secret": "NEW-32-CHAR-SECRET-HERE",
    "zapier_api_key": "<existing-value>",
    "zapier_webhook_url": "<existing-value>"
  }'
```

### API Key Rotation

**When to rotate:**
- Security breach
- Employee offboarding
- Key compromise

**How to rotate:**

1. Generate a new API key in Zapier
2. Update the secret
3. Test the new key
4. Revoke the old key in Zapier

## Lambda Function Access

The Lambda function retrieves secrets at runtime via the `/config` endpoint logic in `main.py`:

```python
def get_secret(secret_id: str) -> Dict[str, Any]:
    """Retrieve a secret from AWS Secrets Manager with caching."""
    # Return cached value if available
    if secret_id in _secrets_cache:
        return _secrets_cache[secret_id]

    try:
        response = secrets_client.get_secret_value(SecretId=secret_id)
        secret_data = json.loads(response['SecretString'])
        _secrets_cache[secret_id] = secret_data
        return secret_data
    except ClientError as e:
        # Error handling...
```

**Caching:** Secrets are cached in memory for the lifetime of the Lambda container (typically 5-15 minutes). This reduces Secrets Manager API calls and improves performance.

## IAM Permissions

The Lambda execution role has these permissions:

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:us-east-2:*:secret:zapier-api-credentials-*"
}
```

Defined in: `amplify/backend.ts` line 96:
```typescript
apiSecret.grantRead(triggersApiFunction);
```

## Security Best Practices

✅ **Do:**
- Use Secrets Manager for all sensitive data
- Rotate secrets regularly (90 days recommended)
- Use different secrets per environment
- Monitor secret access via CloudTrail
- Use IAM policies to restrict secret access

❌ **Don't:**
- Commit secrets to Git
- Share secrets via email/Slack
- Use the same secret across environments
- Store secrets in environment variables
- Log secret values

## Troubleshooting

### Lambda can't read secrets

**Error:** `Secret not found` or `Access denied`

**Solution:**
1. Verify the secret ARN in Lambda environment variables
2. Check IAM role has `secretsmanager:GetSecretValue` permission
3. Verify secret exists in the same region as Lambda

### Secrets not updating

**Issue:** Lambda still returns old values after updating secret

**Cause:** Lambda container is caching the old value

**Solution:** Wait 5-15 minutes for Lambda container to recycle, or manually clear cache by updating Lambda configuration (triggers redeployment)

## References

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [Lambda Environment Variables](https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html)

---

**Last Updated:** 2025-11-13
**Maintained By:** Development Team
