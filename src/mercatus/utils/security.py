"""Enhanced security utilities — brute force protection, session management, IP blocking, secure headers."""

from __future__ import annotations

import hashlib
import hmac
import html
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Final, Optional

from mercatus.db.database import Database
from mercatus.utils.logger import get_logger

logger = get_logger("security")

# Patterns that indicate SQL injection attempts
SQL_INJECTION_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)", re.IGNORECASE),
    re.compile(r"(--|;|/\*|\*/|xp_|sp_)"),
    re.compile(r"('|\\\")", re.IGNORECASE),
]

# Patterns for XSS prevention
XSS_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
]

# Allowed HTML tags (for rich content)
ALLOWED_TAGS: Final[set[str]] = {
    "p", "br", "strong", "em", "ul", "ol", "li", "code", "pre", "blockquote",
}


@dataclass
class RateLimitEntry:
    """Rate limit tracking for a client."""

    requests: list[float] = field(default_factory=list)
    blocked_until: float = 0.0
    total_requests: int = 0
    total_blocked: int = 0


class RateLimiter:
    """In-memory rate limiter with configurable limits."""

    def __init__(
        self,
        requests_per_minute: int = 100,
        burst_size: int = 10,
        block_duration: int = 60,
    ) -> None:
        self._rpm = requests_per_minute
        self._burst = burst_size
        self._block_duration = block_duration
        self._clients: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._global_requests: list[float] = []

    def _cleanup(self) -> None:
        """Remove old entries."""
        now = time.time()
        cutoff = now - 60
        for client_id in list(self._clients.keys()):
            entry = self._clients[client_id]
            entry.requests = [t for t in entry.requests if t > cutoff]
            if not entry.requests and entry.blocked_until < now:
                del self._clients[client_id]
        self._global_requests = [t for t in self._global_requests if t > cutoff]

    def check_rate_limit(self, client_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Check if a client is within rate limits.

        Args:
            client_id: Unique client identifier (IP, session, API key).

        Returns:
            Tuple of (allowed, info_dict).
        """
        self._cleanup()
        now = time.time()
        entry = self._clients[client_id]

        # Check if blocked
        if entry.blocked_until > time.time():
            entry.total_blocked += 1
            return False, {
                "allowed": False,
                "retry_after": int(entry.blocked_until - now),
                "limit": self._rpm,
                "window": "60",
            }

        # Count recent requests
        cutoff = now - 60
        entry.requests = [t for t in entry.requests if t > cutoff]
        entry.requests.append(now)
        entry.total_requests += 1
        self._global_requests.append(now)

        # Check limits
        if len(entry.requests) > self._rpm:
            entry.blocked_until = now + self._block_duration
            entry.total_blocked += 1
            logger.warning(f"Rate limit exceeded for {client_id}")
            return False, {
                "allowed": False,
                "retry_after": self._block_duration,
                "limit": self._rpm,
                "window": "60",
            }

        remaining = max(0, self._rpm - len(entry.requests))
        return True, {
            "allowed": True,
            "remaining": remaining,
            "limit": self._rpm,
            "reset": int(now + 60),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        self._cleanup()
        return {
            "active_clients": len(self._clients),
            "global_rpm": len(self._global_requests),
            "config": {
                "requests_per_minute": self._rpm,
                "burst_size": self._burst,
                "block_duration": self._block_duration,
            },
        }


@dataclass
class SessionEntry:
    """Session tracking for timeout management."""

    session_id: str
    created_at: float
    last_activity: float
    ip_address: str
    user_agent: str = ""
    is_active: bool = True


class SessionManager:
    """Manages session timeouts and tracking."""

    def __init__(self, timeout_minutes: int = 30) -> None:
        self._sessions: dict[str, SessionEntry] = {}
        self._timeout_seconds = timeout_minutes * 60

    def create_session(self, session_id: str, ip_address: str, user_agent: str = "") -> SessionEntry:
        """Create a new session."""
        now = time.time()
        entry = SessionEntry(
            session_id=session_id,
            created_at=now,
            last_activity=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._sessions[session_id] = entry
        return entry

    def get_session(self, session_id: str) -> Optional[SessionEntry]:
        """Get session if it exists and is not timed out."""
        entry = self._sessions.get(session_id)
        if not entry:
            return None

        # Check timeout
        if time.time() - entry.last_activity > self._timeout_seconds:
            entry.is_active = False
            return None

        return entry

    def update_activity(self, session_id: str) -> bool:
        """Update last activity timestamp."""
        entry = self._sessions.get(session_id)
        if not entry:
            return False
        entry.last_activity = time.time()
        return True

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        if session_id in self._sessions:
            self._sessions[session_id].is_active = False
            del self._sessions[session_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        now = time.time()
        expired = [
            sid for sid, entry in self._sessions.items()
            if now - entry.last_activity > self._timeout_seconds
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get all active sessions."""
        self.cleanup_expired()
        return [
            {
                "session_id": s.session_id,
                "ip_address": s.ip_address,
                "created_at": s.created_at,
                "last_activity": s.last_activity,
                "user_agent": s.user_agent,
            }
            for s in self._sessions.values()
            if s.is_active
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        self.cleanup_expired()
        return {
            "active_sessions": len([s for s in self._sessions.values() if s.is_active]),
            "total_sessions": len(self._sessions),
            "timeout_minutes": self._timeout_seconds // 60,
        }


@dataclass
class BruteForceEntry:
    """Tracks failed authentication attempts."""

    attempts: int = 0
    first_attempt: float = 0.0
    last_attempt: float = 0.0
    locked_until: float = 0.0
    ip_address: str = ""


class BruteForceProtector:
    """Protects against brute force attacks."""

    def __init__(
        self,
        max_attempts: int = 5,
        lockout_duration: int = 900,  # 15 minutes
        window_seconds: int = 3600,  # 1 hour
    ) -> None:
        self._max_attempts = max_attempts
        self._lockout_duration = lockout_duration
        self._window_seconds = window_seconds
        self._entries: dict[str, BruteForceEntry] = {}

    def record_attempt(self, identifier: str, success: bool, ip_address: str = "") -> dict[str, Any]:
        """
        Record an authentication attempt.

        Args:
            identifier: User identifier (username, API key, etc.).
            success: Whether the attempt was successful.
            ip_address: Client IP address.

        Returns:
            Status dict with locked status and remaining attempts.
        """
        now = time.time()

        if success:
            # Clear failed attempts on success
            if identifier in self._entries:
                del self._entries[identifier]
            return {"locked": False, "remaining_attempts": self._max_attempts}

        # Get or create entry
        entry = self._entries.get(identifier)
        if not entry:
            entry = BruteForceEntry(first_attempt=now, ip_address=ip_address)
            self._entries[identifier] = entry

        # Check if already locked
        if entry.locked_until > now:
            return {
                "locked": True,
                "remaining_attempts": 0,
                "retry_after": int(entry.locked_until - now),
            }

        # Reset if outside window
        if now - entry.first_attempt > self._window_seconds:
            entry.attempts = 0
            entry.first_attempt = now

        entry.attempts += 1
        entry.last_attempt = now

        # Check if should lock
        if entry.attempts >= self._max_attempts:
            entry.locked_until = now + self._lockout_duration
            logger.warning(
                f"Brute force lockout for {identifier} from {ip_address}: "
                f"{entry.attempts} attempts"
            )
            return {
                "locked": True,
                "remaining_attempts": 0,
                "retry_after": self._lockout_duration,
            }

        return {
            "locked": False,
            "remaining_attempts": self._max_attempts - entry.attempts,
        }

    def is_locked(self, identifier: str) -> tuple[bool, int]:
        """Check if identifier is locked. Returns (locked, retry_after)."""
        entry = self._entries.get(identifier)
        if not entry:
            return False, 0

        if entry.locked_until > time.time():
            return True, int(entry.locked_until - time.time())

        return False, 0

    def reset(self, identifier: str) -> bool:
        """Reset attempts for an identifier."""
        if identifier in self._entries:
            del self._entries[identifier]
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get brute force protection stats."""
        now = time.time()
        locked = sum(1 for e in self._entries.values() if e.locked_until > now)
        return {
            "tracked_identifiers": len(self._entries),
            "currently_locked": locked,
            "max_attempts": self._max_attempts,
            "lockout_duration": self._lockout_duration,
        }


class IPBlocker:
    """Blocks IP addresses based on configurable thresholds."""

    def __init__(
        self,
        max_violations: int = 10,
        block_duration: int = 3600,  # 1 hour
    ) -> None:
        self._max_violations = max_violations
        self._block_duration = block_duration
        self._violations: dict[str, list[float]] = defaultdict(list)
        self._blocked: dict[str, float] = {}  # ip -> blocked_until

    def record_violation(self, ip_address: str) -> bool:
        """
        Record a violation for an IP.

        Args:
            ip_address: Client IP address.

        Returns:
            True if IP is now blocked.
        """
        now = time.time()
        self._violations[ip_address].append(now)

        # Clean old violations (older than block_duration)
        cutoff = now - self._block_duration
        self._violations[ip_address] = [
            t for t in self._violations[ip_address] if t > cutoff
        ]

        # Check if should block
        if len(self._violations[ip_address]) >= self._max_violations:
            self._blocked[ip_address] = now + self._block_duration
            logger.warning(f"IP blocked: {ip_address} ({len(self._violations[ip_address])} violations)")
            return True

        return False

    def is_blocked(self, ip_address: str) -> tuple[bool, int]:
        """Check if IP is blocked. Returns (blocked, retry_after)."""
        if ip_address in self._blocked:
            retry_after = int(self._blocked[ip_address] - time.time())
            if retry_after > 0:
                return True, retry_after
            else:
                del self._blocked[ip_address]
                return False, 0
        return False, 0

    def unblock(self, ip_address: str) -> bool:
        """Manually unblock an IP."""
        if ip_address in self._blocked:
            del self._blocked[ip_address]
            if ip_address in self._violations:
                del self._violations[ip_address]
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get IP blocking stats."""
        now = time.time()
        active_blocks = {
            ip: int(until - now)
            for ip, until in self._blocked.items()
            if until > now
        }
        return {
            "blocked_ips": len(active_blocks),
            "total_violations": sum(len(v) for v in self._violations.values()),
            "blocked_details": active_blocks,
            "max_violations": self._max_violations,
            "block_duration": self._block_duration,
        }


class AuditLogger:
    """Audit logging for security-relevant operations."""

    def __init__(self, database: Optional[Database] = None) -> None:
        self._db = database

    async def log(
        self,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Log an auditable action.

        Args:
            action: Action type (e.g., 'chat.create', 'api_key.create').
            user_id: User who performed the action.
            resource_type: Type of resource affected.
            resource_id: Resource identifier.
            details: Additional details dict.
            ip_address: Client IP.
        """
        if self._db and self._db.is_connected:
            try:
                await self._db.execute(
                    """
                    INSERT INTO audit_log
                    (action, user_id, resource_type, resource_id, details, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action,
                        user_id,
                        resource_type,
                        resource_id,
                        __import__("json").dumps(details or {}),
                        ip_address,
                    ),
                )
                await self._db.commit()
            except Exception as e:
                logger.warning(f"Failed to write audit log: {e}")

    async def get_audit_log(
        self,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve audit log entries."""
        if not self._db or not self._db.is_connected:
            return []

        query = "SELECT * FROM audit_log"
        params: list[Any] = []

        if action:
            query += " WHERE action = ?"
            params.append(action)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        try:
            rows = await self._db.fetchall(query, tuple(params))
            return [
                {
                    "id": row["id"] if isinstance(row["id"], int) else row[0],
                    "action": row["action"] if isinstance(row["action"], str) else row[1],
                    "user_id": row["user_id"] if isinstance(row["user_id"], str) else row[2],
                    "resource_type": row["resource_type"] if isinstance(row["resource_type"], str) else row[3],
                    "resource_id": row["resource_id"] if isinstance(row["resource_id"], str) else row[4],
                    "details": __import__("json").loads(row["details"] if isinstance(row["details"], str) else row[5]) if (row["details"] if isinstance(row["details"], str) else row[5]) else {},
                    "ip_address": row["ip_address"] if isinstance(row["ip_address"], str) else row[6],
                    "created_at": row["created_at"] if isinstance(row["created_at"], str) else row[7],
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Failed to read audit log: {e}")
            return []


class APIKeyRotator:
    """Manages API key rotation."""

    def __init__(self, rotation_interval_days: int = 90) -> None:
        self._rotation_interval = rotation_interval_days * 86400

    def should_rotate(self, created_at: float) -> bool:
        """Check if a key should be rotated."""
        return (time.time() - created_at) > self._rotation_interval

    def days_until_rotation(self, created_at: float) -> int:
        """Get days until rotation is needed."""
        remaining = self._rotation_interval - (time.time() - created_at)
        return max(0, int(remaining / 86400))


def get_security_headers() -> dict[str, str]:
    """Get recommended security headers for HTTP responses."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }


def sanitize_input(text: str) -> str:
    """
    Sanitize user input by escaping HTML and removing dangerous content.

    Args:
        text: Raw user input.

    Returns:
        Sanitized text safe for processing and display.

    Raises:
        ValueError: If input exceeds maximum length.
    """
    from mercatus.models.config import get_settings
    settings = get_settings()

    if len(text) > settings.max_input_length:
        raise ValueError(
            f"Input exceeds maximum length of {settings.max_input_length} characters"
        )

    # Remove null bytes
    text = text.replace("\x00", "")

    # Escape HTML entities
    text = html.escape(text)

    # Remove potential XSS vectors
    for pattern in XSS_PATTERNS:
        text = pattern.sub("", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def validate_module(module: str) -> str:
    """
    Validate and normalize module name.

    Args:
        module: Module identifier.

    Returns:
        Normalized module name.

    Raises:
        ValueError: If module is not recognized.
    """
    valid_modules = {"sales", "trading", "general"}
    normalized = module.lower().strip()

    if normalized not in valid_modules:
        raise ValueError(
            f"Invalid module '{module}'. Must be one of: {', '.join(sorted(valid_modules))}"
        )

    return normalized


def check_sql_injection(text: str) -> bool:
    """
    Check if text contains potential SQL injection patterns.

    Args:
        text: Input text to check.

    Returns:
        True if suspicious patterns detected.
    """
    return any(pattern.search(text) for pattern in SQL_INJECTION_PATTERNS)


def generate_session_id() -> str:
    """Generate a unique session identifier."""
    return f"sess_{uuid.uuid4().hex[:12]}"


def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return uuid.uuid4().hex


def validate_csrf_token(token: str, expected: str) -> bool:
    """Validate a CSRF token using constant-time comparison."""
    return hmac.compare_digest(token, expected)


def hash_sensitive_value(value: str) -> str:
    """Hash a sensitive value for secure storage."""
    return hashlib.sha256(value.encode()).hexdigest()


# Global instances
rate_limiter = RateLimiter()
audit_logger = AuditLogger()
session_manager = SessionManager(timeout_minutes=30)
brute_force_protector = BruteForceProtector(max_attempts=5, lockout_duration=900)
ip_blocker = IPBlocker(max_violations=10, block_duration=3600)
api_key_rotator = APIKeyRotator(rotation_interval_days=90)
