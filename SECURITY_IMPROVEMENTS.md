# Webhook Security Hardening - Implementation Summary

## Overview
All critical security vulnerabilities in the webhook service have been fixed. The service is now hardened against external attacks through signature verification, authorization, rate limiting, and strict payload validation.

## Changes Made

### 1. **HMAC Signature Verification** ✅
**Problem:** Webhook calls were not verified - any attacker could send fake webhooks.

**Solution:** 
- Added `verify_strava_signature()` function that validates `X-Strava-Signature` header
- Uses HMAC-SHA256 with `STRAVA_CLIENT_SECRET` environment variable
- Implements timing-safe comparison to prevent timing attacks
- Returns `401 Unauthorized` for invalid signatures

**Code:**
```python
def verify_strava_signature(request_body_bytes: bytes, signature: str) -> bool:
    """Verify Strava webhook signature using HMAC SHA256."""
    # Computes HMAC-SHA256 and compares with timing-safe comparison
```

**Required env var:** `STRAVA_CLIENT_SECRET` - must be configured before deployment

---

### 2. **Authorization Token Validation** ✅
**Problem:** POST endpoint accepted requests without any token validation (only GET verified token).

**Solution:**
- Added `Authorization: Bearer <token>` header validation to POST endpoint
- Uses timing-safe comparison (`hmac.compare_digest()`)
- Token must match `WEBHOOK_VERIFY_TOKEN` environment variable
- Returns `401 Unauthorized` for invalid/missing tokens

**Client requirement:**
```bash
curl -X POST https://your-webhook.com/webhook \
  -H "Authorization: Bearer $WEBHOOK_VERIFY_TOKEN" \
  -H "X-Strava-Signature: v0=..." \
  -H "Content-Type: application/json" \
  -d '{"..."}'
```

---

### 3. **Rate Limiting** ✅
**Problem:** No protection against DoS/brute force attacks.

**Solution:**
- Installed `Flask-Limiter` middleware
- Global limits: 200 requests/day, 50 requests/hour per IP
- GET endpoint: 10 requests/minute (strict for verification)
- POST endpoint: 30 requests/minute (stricter than global)
- Returns `429 Too Many Requests` when exceeded

**Config in code:**
```python
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

@app.route("/webhook", methods=["POST"])
@limiter.limit("30 per minute")
```

---

### 4. **Stricter Payload Validation** ✅
**Problem:** Minimal validation of event data - could cause unexpected behavior.

**Solution:**
- Explicit validation of `aspect_type` (must be "create")
- Explicit validation of `object_type` (must be "activity")
- Validation of `object_id` (must be integer)
- Returns `400 Bad Request` for invalid payloads
- Debug logging instead of info logging for ignored events

**Code:**
```python
if not object_id or not isinstance(object_id, int):
    logger.warning(f"Invalid object_id: {object_id}")
    return jsonify({"error": "Bad Request"}), 400
```

---

### 5. **Improved Error Handling & Logging** ✅
**Changes:**
- Changed string responses to JSON responses (`jsonify()`)
- Added proper HTTP status codes
- Changed info logging for successful verification to only log on success
- Warning logs for failed verification attempts
- Error logs with exception type (not full message) for security
- Removed IP address logging in endpoint logs

**Before:**
```python
return "Forbidden", 403
logger.info(f"mode={mode}")  # Logging parameters
```

**After:**
```python
return jsonify({"error": "Forbidden"}), 403
logger.warning(f"Verification failed - mode: {mode}, token_match: {token == VERIFY_TOKEN}")
```

---

## Environment Variables Required

Make sure these are set in your Cloud Run deployment:

```bash
# NEW: Strava webhook signing secret (from Strava API settings)
STRAVA_CLIENT_SECRET=your_strava_client_secret

# EXISTING: Webhook verification token
WEBHOOK_VERIFY_TOKEN=your_strong_random_token

# EXISTING: GCP config
STRAVA_GCP_PROJECT=your-gcp-project
STRAVA_GCP_REGION=europe-west1
STRAVA_WORKER_JOB=your-worker-job-name
WEBHOOK_COOLDOWN_SECONDS=180
```

---

## Testing

Comprehensive security test suite provided in `tests/test_webhook.py`:

```bash
# Install dev dependencies
pip install -r requirements.txt pytest

# Run all tests
pytest tests/test_webhook.py -v

# Run specific test class
pytest tests/test_webhook.py::TestSignatureVerification -v
```

**Test Coverage:**
- ✅ Valid signatures accepted
- ✅ Invalid signatures rejected
- ✅ Missing signatures rejected
- ✅ Authorization token validation
- ✅ Missing Authorization header rejected
- ✅ Wrong tokens rejected
- ✅ Malformed headers rejected
- ✅ Payload validation (object_type, aspect_type, object_id)
- ✅ Non-activity objects ignored
- ✅ Non-create events ignored
- ✅ GET verification endpoint protection
- ✅ Rate limiting (implicit in Flask-Limiter)

---

## Security Best Practices Applied

1. **Signature Verification** - Cryptographic proof webhook is from Strava
2. **Timing-Safe Comparison** - Prevents timing attacks on token/signature validation
3. **Defense in Depth** - Both signature AND token validation (signature is primary)
4. **Rate Limiting** - Prevents DoS and brute force attacks
5. **Strict Validation** - No assumption about event structure
6. **Proper HTTP Status Codes** - Correct semantics (401 for auth, 400 for data, 429 for rate limit)
7. **Safe Logging** - No sensitive data in logs
8. **Error Hiding** - Generic error messages to attackers

---

## Deployment Checklist

Before deploying to production:

- [ ] Set `STRAVA_CLIENT_SECRET` in Cloud Run secrets
- [ ] Verify `WEBHOOK_VERIFY_TOKEN` is strong (>32 chars random)
- [ ] Run full test suite locally
- [ ] Update Strava webhook settings if needed
- [ ] Test with actual Strava events (e.g., create a test activity)
- [ ] Monitor logs for security events in first 24h
- [ ] Document the changes in team wiki/runbook

---

## Backward Compatibility Notes

**Breaking Change:** The POST endpoint now requires:
1. Valid `X-Strava-Signature` header
2. `Authorization: Bearer <token>` header

If you have other services calling this webhook, they must be updated to include these headers.

---

## Next Steps (Optional Enhancements)

1. **Persistent Rate Limit Storage** - Replace `memory://` with Redis for multi-instance deployments
2. **Signature Rotation** - Implement secret rotation mechanism
3. **IP Whitelist** - Add GCP-specific IP restrictions if available
4. **Metrics/Monitoring** - Add Prometheus metrics for failed auth attempts
5. **Webhook Replay Protection** - Add timestamp validation to prevent replay attacks
6. **Request Logging** - Add secure audit logging to Cloud Logging
