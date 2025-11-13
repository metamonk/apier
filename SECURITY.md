# Security Implementation

This document describes the security measures implemented in the Zapier Triggers API.

## Overview

The API implements multiple layers of security:
- **TLS/HTTPS Encryption**: All traffic encrypted in transit
- **JWT Bearer Token Authentication**: Stateless token-based authentication
- **AWS Secrets Manager**: Secure storage of sensitive credentials
- **IAM Role-Based Access**: Least privilege access to AWS resources

## TLS/HTTPS Encryption

### Implementation

The API uses **AWS Lambda Function URLs**, which enforce HTTPS by default:
- All requests MUST use HTTPS
- HTTP requests are automatically rejected
- TLS 1.2+ is enforced
- Certificates are managed by AWS

### Verification

```bash
# All requests must use HTTPS
curl https://YOUR_FUNCTION_URL/

# HTTP is not supported
curl http://YOUR_FUNCTION_URL/  # This will fail
```

**No additional configuration required** - Lambda Function URLs are HTTPS-only by default.

## JWT Bearer Token Authentication

### Overview

Protected API endpoints require a valid JWT (JSON Web Token) bearer token in the `Authorization` header.

### Token Characteristics

- **Algorithm**: HS256 (HMAC with SHA-256)
- **Expiration**: 24 hours
- **Signing Key**: Stored in AWS Secrets Manager (`jwt_secret`)
- **Claims**:
  - `sub` (subject): Username (always "api")
  - `iat` (issued at): Token creation timestamp
  - `exp` (expiration): Token expiration timestamp
  - `api_key`: Truncated API key for reference

### Obtaining a Token

#### Step 1: Prepare Your API Key

The API key is stored in AWS Secrets Manager as `zapier_api_key`. To view it:

```bash
aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-{stackName} \
  --region us-east-2 \
  --query SecretString --output text | jq -r '.zapier_api_key'
```

#### Step 2: Request a Token

Send a POST request to `/token` with your API key:

```bash
curl -X POST "https://YOUR_FUNCTION_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=YOUR_API_KEY"
```

**Request Format:**
- **Method**: POST
- **Endpoint**: `/token`
- **Content-Type**: `application/x-www-form-urlencoded`
- **Body Parameters**:
  - `username`: Must be "api"
  - `password`: Your Zapier API key

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using Tokens

Include the token in the `Authorization` header with the `Bearer` prefix:

```bash
curl -X POST "https://YOUR_FUNCTION_URL/events" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "user.signup",
    "source": "web-app",
    "payload": {"user_id": "123"}
  }'
```

### Token Errors

**401 Unauthorized** responses indicate authentication issues:

1. **Missing Token**:
   ```json
   {
     "detail": "Not authenticated"
   }
   ```

2. **Invalid Token**:
   ```json
   {
     "detail": "Could not validate credentials"
   }
   ```

3. **Expired Token**:
   ```json
   {
     "detail": "Could not validate credentials"
   }
   ```
   **Solution**: Request a new token from `/token`

## Protected vs Public Endpoints

### Public Endpoints (No Authentication Required)

These endpoints are accessible without authentication:

- `GET /` - Service information
- `GET /health` - Health check
- `GET /config` - Non-sensitive configuration
- `POST /token` - Token generation

### Protected Endpoints (Authentication Required)

These endpoints require a valid JWT bearer token:

- `POST /events` - Create event
- `GET /inbox` - Retrieve pending events
- `POST /inbox/{event_id}/ack` - Acknowledge event delivery

## Security Best Practices

### API Key Management

✅ **Do:**
- Store API keys in AWS Secrets Manager
- Rotate API keys regularly (every 90 days)
- Use different API keys per environment
- Monitor API key usage via CloudTrail
- Revoke compromised keys immediately

❌ **Don't:**
- Commit API keys to Git
- Share API keys via email/Slack
- Log API keys in application logs
- Store API keys in environment variables (use Secrets Manager)
- Use the same API key across environments

### JWT Token Management

✅ **Do:**
- Store tokens securely (e.g., encrypted storage)
- Request new tokens when expired
- Use HTTPS for all token transmissions
- Set appropriate token expiration times
- Validate tokens on every request

❌ **Don't:**
- Store tokens in browser localStorage (for web apps)
- Share tokens between applications
- Include sensitive data in token claims
- Use tokens after expiration
- Log token values

### API Request Security

✅ **Do:**
- Always use HTTPS
- Include tokens in `Authorization` header
- Validate responses
- Implement retry logic with exponential backoff
- Monitor for suspicious activity

❌ **Don't:**
- Use HTTP
- Include tokens in URL query parameters
- Ignore SSL/TLS certificate errors
- Store sensitive data in request logs
- Make excessive requests (implement rate limiting)

## Password Hashing

The API uses **Argon2id** for password hashing:
- **Library**: `pwdlib` with Argon2 backend
- **Algorithm**: Argon2id (recommended by OWASP)
- **Parameters**: Default secure parameters

```python
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

# Hash a password
hashed = password_hash.hash("secret_password")

# Verify a password
is_valid = password_hash.verify("secret_password", hashed)
```

## JWT Implementation Details

### Token Structure

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.  ← Header
eyJzdWIiOiJhcGkiLCJpYXQiOjE2ODk...       ← Payload
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJ...      ← Signature
```

**Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "sub": "api",
  "api_key": "test-api...",
  "iat": 1689000000,
  "exp": 1689086400
}
```

### Token Validation Process

1. Extract token from `Authorization: Bearer {token}` header
2. Verify JWT signature using secret from AWS Secrets Manager
3. Check token expiration (`exp` claim)
4. Validate required claims (`sub`)
5. Return user object or raise 401 Unauthorized

## Secrets Rotation

### Rotating JWT Secret

**When to rotate:**
- Security breach
- Employee offboarding
- Scheduled rotation (every 90-180 days)
- Compliance requirements

**How to rotate:**

1. **Generate new secret**:
   ```bash
   openssl rand -hex 32
   ```

2. **Update in Secrets Manager**:
   ```bash
   aws secretsmanager update-secret \
     --secret-id zapier-api-credentials-{stackName} \
     --region us-east-2 \
     --secret-string '{
       "environment": "production",
       "jwt_secret": "NEW_32_CHAR_SECRET",
       "zapier_api_key": "<keep-existing>",
       "zapier_webhook_url": "<keep-existing>"
     }'
   ```

3. **Impact**: All existing JWT tokens will be invalidated. Clients must request new tokens.

### Rotating API Key

**How to rotate:**

1. **Generate new API key** in Zapier dashboard
2. **Update Secrets Manager** with new key
3. **Test with new key**
4. **Revoke old key** in Zapier

## Security Monitoring

### CloudTrail Logging

Monitor security-related events:

```bash
# Check Secrets Manager access
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=zapier-api-credentials \
  --region us-east-2

# Check Lambda invocations
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=TriggersApiFunction \
  --region us-east-2
```

### CloudWatch Alarms

Set up alarms for:
- High rate of 401 Unauthorized responses
- Unusual API call patterns
- Failed authentication attempts

**Example alarm for authentication failures:**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-auth-failures \
  --alarm-description "Alert on high authentication failure rate" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=TriggersApiFunction \
  --region us-east-2
```

## Compliance & Standards

The API security implementation follows:
- **OWASP Top 10** best practices
- **NIST Cybersecurity Framework** guidelines
- **AWS Well-Architected Framework** Security Pillar
- **OAuth 2.0** specifications for token handling

## Testing Authentication

### Manual Testing

```bash
# 1. Get token
TOKEN=$(curl -s -X POST "https://YOUR_FUNCTION_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=YOUR_API_KEY" | jq -r '.access_token')

# 2. Test protected endpoint
curl -X POST "https://YOUR_FUNCTION_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "test.event",
    "source": "test",
    "payload": {"test": "data"}
  }'

# 3. Test without token (should fail with 401)
curl -X POST "https://YOUR_FUNCTION_URL/events" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "test.event",
    "source": "test",
    "payload": {"test": "data"}
  }'
```

### Automated Testing

Run the authentication test suite:

```bash
cd amplify/functions/api
pytest tests/test_auth_api.py -v
```

## Troubleshooting

### Issue: 401 Unauthorized

**Symptoms**: All authenticated requests return 401

**Possible Causes:**
1. Token expired (24-hour expiration)
2. Invalid JWT secret in Secrets Manager
3. Token signature verification failed
4. Missing `Authorization` header

**Solutions:**
1. Request a new token from `/token`
2. Verify JWT secret is correctly configured
3. Check `Authorization: Bearer {token}` header format
4. Verify API key is correct

### Issue: JWT Secret Not Found

**Symptoms**: 500 Internal Server Error when accessing protected endpoints

**Cause**: JWT secret missing from AWS Secrets Manager

**Solution:**
```bash
aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-{stackName} \
  --region us-east-2 \
  --query SecretString --output text | jq -r '.jwt_secret'
```

If missing, update the secret with a new JWT secret.

### Issue: Lambda Container Caching

**Symptoms**: Secrets not updating despite Secrets Manager changes

**Cause**: Lambda container caching old secret values

**Solution**: Wait 5-15 minutes for Lambda container to recycle, or force update:
```bash
aws lambda update-function-configuration \
  --function-name TriggersApiFunction \
  --environment Variables={FORCE_UPDATE=true} \
  --region us-east-2
```

## References

- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT.io](https://jwt.io/) - JWT Debugger
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [python-jose Documentation](https://python-jose.readthedocs.io/)
- [pwdlib Documentation](https://frankie567.github.io/pwdlib/)

---

**Last Updated:** 2025-11-13
**Maintained By:** Development Team
