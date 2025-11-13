# GDPR & CCPA Compliance Guide

This document outlines the data privacy and compliance measures implemented in the Zapier Triggers API.

## Overview

The API complies with:
- **GDPR** (General Data Protection Regulation - EU)
- **CCPA** (California Consumer Privacy Act - US)

## Data Retention Policy

### Automatic Data Deletion

**Retention Period**: 90 days

All events stored in DynamoDB are automatically deleted after 90 days using DynamoDB's Time-To-Live (TTL) feature.

### Implementation

**DynamoDB TTL Configuration:**
- **TTL Attribute**: `ttl`
- **Value Format**: Unix timestamp (seconds since epoch)
- **Calculation**: `current_time + 90 days`
- **Deletion**: Automatic within 48 hours after TTL expiration

**Code Implementation:**

```typescript
// backend.ts
const eventsTable = new dynamodb.Table(stack, 'EventsTable', {
  // ... other config
  timeToLiveAttribute: 'ttl',  // Enable TTL
});
```

```python
# main.py
# Calculate TTL (90 days from now)
ttl_timestamp = int((datetime.utcnow() + timedelta(days=90)).timestamp())

event_data = {
  "id": event_id,
  "ttl": ttl_timestamp,  # Auto-delete after 90 days
  # ... other fields
}
```

### Rationale

**Why 90 days?**
- Balances business needs with privacy requirements
- Allows sufficient time for event processing and delivery
- Complies with GDPR's "data minimization" principle
- Exceeds CCPA's minimum requirements

### Verification

Check TTL status in AWS Console or CLI:

```bash
# Describe table TTL settings
aws dynamodb describe-time-to-live \
  --table-name zapier-triggers-events-{stackName} \
  --region us-east-2

# Expected response:
# {
#   "TimeToLiveDescription": {
#     "TimeToLiveStatus": "ENABLED",
#     "AttributeName": "ttl"
#   }
# }
```

## Data Categories and Processing

### Personal Data Collected

The API may process the following categories of personal data:

**Event Payload Data:**
- User identifiers (if included in payloads)
- Email addresses (if included in payloads)
- Custom data provided by API clients

**Metadata:**
- Event creation timestamps
- Event source identifiers
- Event type information

**Note**: The API is payload-agnostic. Personal data inclusion depends on client implementation.

### Legal Basis for Processing

- **Contractual Necessity**: Processing events as part of the service agreement
- **Legitimate Interests**: System monitoring, security, and service improvement

### Data Processing Activities

1. **Collection**: Events received via POST /events endpoint
2. **Storage**: Temporary storage in DynamoDB (max 90 days)
3. **Transfer**: Events delivered to configured webhooks
4. **Deletion**: Automatic deletion after TTL expiration

## GDPR Rights Implementation

### Right to Access (Article 15)

**Not Currently Implemented**

*Recommendation*: Implement a GET /events/{user_id} endpoint for data subject access requests.

### Right to Erasure (Article 17)

**Partial Implementation**

- ✅ Automatic deletion after 90 days via TTL
- ❌ On-demand deletion not implemented

*Recommendation*: Implement DELETE /events/{id} endpoint for immediate deletion requests.

### Right to Data Portability (Article 20)

**Not Currently Implemented**

*Recommendation*: Implement data export functionality in standard format (JSON/CSV).

### Right to Rectification (Article 16)

**Not Currently Implemented**

*Recommendation*: Implement PUT /events/{id} endpoint for data correction.

## CCPA Rights Implementation

### Right to Know

**Partial Implementation**

- ✅ Privacy documentation (this document)
- ❌ Consumer-facing privacy policy not created

*Recommendation*: Create a public-facing privacy policy.

### Right to Delete

**Partial Implementation**

- ✅ Automatic deletion after 90 days
- ❌ On-demand deletion not implemented

*Recommendation*: Same as GDPR Right to Erasure.

### Right to Opt-Out

**Not Applicable**

The API does not sell personal data.

## Security Measures

### Data Protection

- ✅ **Encryption in Transit**: TLS 1.2+ for all communications
- ✅ **Encryption at Rest**: DynamoDB encryption enabled by default
- ✅ **Access Control**: JWT authentication for API access
- ✅ **Audit Logging**: CloudWatch logs for all API requests
- ✅ **Secret Management**: AWS Secrets Manager for credentials

See [SECURITY.md](./SECURITY.md) for detailed security documentation.

## Data Breach Response

### Detection

**Monitoring Tools:**
- CloudWatch alarms for unusual activity
- CloudTrail for AWS API access logging
- Lambda execution logs

### Response Procedure

1. **Identification** (0-24 hours):
   - Detect and confirm breach
   - Assess scope and impact
   - Document initial findings

2. **Containment** (24-48 hours):
   - Isolate affected systems
   - Revoke compromised credentials
   - Block unauthorized access

3. **Notification** (72 hours):
   - GDPR: Notify supervisory authority within 72 hours
   - CCPA: Notify affected consumers without unreasonable delay
   - Document all actions taken

4. **Remediation**:
   - Fix vulnerabilities
   - Implement additional controls
   - Update documentation

5. **Review**:
   - Conduct post-incident analysis
   - Update breach response procedures
   - Provide staff training

## Compliance Audit Checklist

### Monthly Audit

- [ ] **Data Retention**: Verify TTL is enabled and functioning
- [ ] **Access Logs**: Review CloudWatch logs for suspicious activity
- [ ] **Authentication**: Verify JWT tokens are expiring correctly
- [ ] **Secrets**: Confirm API keys and secrets are not exposed

### Quarterly Audit

- [ ] **Security Review**: Conduct security assessment
- [ ] **Data Processing**: Review data processing activities
- [ ] **Third-Party Access**: Audit third-party integrations
- [ ] **Documentation**: Update compliance documentation

### Annual Audit

- [ ] **Full Compliance Review**: Comprehensive GDPR/CCPA assessment
- [ ] **Privacy Policy Update**: Review and update privacy documentation
- [ ] **Breach Response Test**: Conduct breach response drill
- [ ] **Staff Training**: Provide compliance training
- [ ] **External Audit**: Consider third-party compliance audit

### Audit Logging

**Create Audit Log Entry:**

```bash
# Example audit log entry
cat << EOF >> compliance-audit-log.txt
==========================================================
Audit Date: $(date)
Auditor: [Name]
Audit Type: [Monthly/Quarterly/Annual]

Checklist Results:
- Data Retention TTL: [PASS/FAIL] - [Notes]
- Access Logs Review: [PASS/FAIL] - [Notes]
- Authentication: [PASS/FAIL] - [Notes]
- Secrets Management: [PASS/FAIL] - [Notes]

Findings:
[List any issues or concerns]

Actions Required:
[List remediation actions]

Sign-off: [Name]
==========================================================
EOF
```

## DynamoDB TTL Monitoring

### Verify TTL is Working

```bash
# Check TTL status
aws dynamodb describe-time-to-live \
  --table-name zapier-triggers-events-{stackName} \
  --region us-east-2

# Query for items nearing expiration
aws dynamodb query \
  --table-name zapier-triggers-events-{stackName} \
  --index-name status-index \
  --key-condition-expression "status = :status" \
  --expression-attribute-values '{":status": {"S": "pending"}}' \
  --region us-east-2 \
  --max-items 10

# Check TTL values in returned items
```

### CloudWatch Metrics for TTL

**Important Metrics:**
- `TTLDeletedItems`: Number of items deleted by TTL
- `SystemErrors`: Should remain low

**Create Alarm for TTL Issues:**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-ttl-errors \
  --alarm-description "Alert when TTL deletions fail" \
  --metric-name SystemErrors \
  --namespace AWS/DynamoDB \
  --statistic Sum \
  --period 3600 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=TableName,Value=zapier-triggers-events-{stackName} \
  --region us-east-2
```

## Data Processing Agreement (DPA)

### Controller vs. Processor

**For this API:**
- **Data Controller**: The organization deploying this API
- **Data Processor**: AWS (infrastructure provider)

**AWS as Processor:**
- AWS Data Processing Addendum (DPA) applies
- AWS is GDPR-compliant
- Standard Contractual Clauses (SCCs) in place

### Client Responsibilities

If you are deploying this API, you are the **Data Controller** and responsible for:

1. ✅ Ensuring lawful basis for data processing
2. ✅ Providing privacy notices to data subjects
3. ✅ Honoring data subject rights requests
4. ✅ Maintaining Records of Processing Activities (ROPA)
5. ✅ Conducting Data Protection Impact Assessments (DPIA) if required
6. ✅ Appointing Data Protection Officer (DPO) if required
7. ✅ Reporting data breaches to authorities

## Records of Processing Activities (ROPA)

### Processing Activity Record

**Activity Name**: Zapier Triggers Event Processing

**Data Controller**: [Organization Name]

**Data Protection Officer**: [Contact Information]

**Purpose**: Event ingestion and delivery for automation workflows

**Categories of Data Subjects**:
- API clients
- End users (if personal data included in payloads)

**Categories of Personal Data**:
- Event payload data (client-defined)
- Metadata (timestamps, event types)

**Categories of Recipients**:
- Zapier webhook endpoints
- Internal systems

**Transfers to Third Countries**:
- [Specify if applicable]

**Retention Period**:
- 90 days (automatic deletion via TTL)

**Security Measures**:
- TLS encryption in transit
- DynamoDB encryption at rest
- JWT authentication
- AWS Secrets Manager

## Recommendations for Full Compliance

### Short Term (1-3 months)

1. **Implement On-Demand Deletion**:
   ```python
   @app.delete("/events/{event_id}")
   async def delete_event(event_id: str, current_user: User = Depends(get_authenticated_user)):
       # Delete event immediately
   ```

2. **Add Data Export**:
   ```python
   @app.get("/events/export")
   async def export_events(user_id: str, current_user: User = Depends(get_authenticated_user)):
       # Export user's events as JSON
   ```

3. **Create Privacy Policy**:
   - Draft consumer-facing privacy policy
   - Publish at /privacy-policy endpoint

### Medium Term (3-6 months)

1. **Implement Data Subject Access Requests (DSAR)**:
   - Create workflow for handling DSAR
   - Implement automated response system

2. **Conduct DPIA**:
   - Assess privacy impact of processing activities
   - Document findings and mitigation measures

3. **Staff Training**:
   - GDPR/CCPA compliance training
   - Data breach response procedures
   - Privacy-by-design principles

### Long Term (6-12 months)

1. **Third-Party Audit**:
   - Engage external auditor for compliance review
   - Obtain certifications if applicable

2. **Privacy-Enhancing Technologies**:
   - Consider pseudonymization
   - Implement data minimization techniques
   - Explore differential privacy

## References

- [GDPR Full Text](https://gdpr-info.eu/)
- [CCPA Full Text](https://oag.ca.gov/privacy/ccpa)
- [DynamoDB TTL Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
- [AWS GDPR Center](https://aws.amazon.com/compliance/gdpr-center/)
- [AWS Data Privacy](https://aws.amazon.com/compliance/data-privacy/)
- [ICO GDPR Guide](https://ico.org.uk/for-organisations/guide-to-data-protection/guide-to-the-general-data-protection-regulation-gdpr/)

---

**Last Updated:** 2025-11-13
**Maintained By:** Development Team
**Review Schedule**: Quarterly
