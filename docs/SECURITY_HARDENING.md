# Security Hardening

Mercatus Agent implements multiple layers of security protection.

## Brute Force Protection

- Tracks failed authentication attempts per identifier
- Locks out after 5 failed attempts (configurable)
- 15-minute lockout duration (configurable)
- Automatic reset on successful authentication

## Session Management

- 30-minute inactivity timeout (configurable)
- Automatic cleanup of expired sessions
- IP address and user agent tracking
- Session invalidation support

## IP Blocking

- Configurable violation threshold (default: 10)
- 1-hour block duration (configurable)
- Automatic expiration of old violations
- Manual unblock support

## Rate Limiting

- Requests per minute limiting (default: 100)
- Per-client tracking
- Burst size support
- Configurable block duration

## Secure Headers

All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy` (CSP)
- `X-XSS-Protection: 1; mode=block`

## Input Sanitization

- HTML entity escaping
- XSS pattern removal
- SQL injection detection
- Null byte removal
- Whitespace normalization

## API Key Rotation

- 90-day rotation interval (configurable)
- Days-until-rotation tracking
- Prefix-based key identification

## API Endpoints

```
GET /api/v1/security/audit
GET /api/v1/security/sessions
```
