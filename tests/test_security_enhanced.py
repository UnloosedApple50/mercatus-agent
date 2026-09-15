"""Tests for enhanced security features: brute force, session timeout, IP blocking."""

from __future__ import annotations

import pytest
import time

from mercatus.utils.security import (
    BruteForceProtector,
    SessionManager,
    IPBlocker,
    get_security_headers,
)


class TestBruteForceProtector:
    """Tests for BruteForceProtector."""

    def test_init(self):
        protector = BruteForceProtector(max_attempts=5, lockout_duration=900)
        assert protector._max_attempts == 5
        assert protector._lockout_duration == 900

    def test_success_clears_attempts(self):
        protector = BruteForceProtector(max_attempts=3)
        protector.record_attempt("user1", success=False)
        protector.record_attempt("user1", success=False)
        result = protector.record_attempt("user1", success=True)
        assert result["locked"] is False
        assert result["remaining_attempts"] == 3

    def test_lockout_after_max_attempts(self):
        protector = BruteForceProtector(max_attempts=3, lockout_duration=60)
        protector.record_attempt("user1", success=False)
        protector.record_attempt("user1", success=False)
        result = protector.record_attempt("user1", success=False)
        assert result["locked"] is True
        assert result["remaining_attempts"] == 0
        assert result["retry_after"] > 0

    def test_is_locked(self):
        protector = BruteForceProtector(max_attempts=2, lockout_duration=60)
        protector.record_attempt("user1", success=False)
        protector.record_attempt("user1", success=False)
        locked, retry_after = protector.is_locked("user1")
        assert locked is True
        assert retry_after > 0

    def test_is_not_locked_initially(self):
        protector = BruteForceProtector()
        locked, retry_after = protector.is_locked("user1")
        assert locked is False
        assert retry_after == 0

    def test_reset(self):
        protector = BruteForceProtector(max_attempts=2)
        protector.record_attempt("user1", success=False)
        protector.record_attempt("user1", success=False)
        assert protector.reset("user1") is True
        locked, _ = protector.is_locked("user1")
        assert locked is False

    def test_reset_nonexistent(self):
        protector = BruteForceProtector()
        assert protector.reset("nonexistent") is False

    def test_get_stats(self):
        protector = BruteForceProtector(max_attempts=2)
        protector.record_attempt("user1", success=False)
        protector.record_attempt("user1", success=False)
        stats = protector.get_stats()
        assert stats["tracked_identifiers"] == 1
        assert stats["currently_locked"] == 1

    def test_different_users_independent(self):
        protector = BruteForceProtector(max_attempts=2)
        protector.record_attempt("user1", success=False)
        protector.record_attempt("user1", success=False)
        # user2 should not be affected
        result = protector.record_attempt("user2", success=False)
        assert result["locked"] is False
        assert result["remaining_attempts"] == 1


class TestSessionManager:
    """Tests for SessionManager."""

    def test_init(self):
        manager = SessionManager(timeout_minutes=30)
        assert manager._timeout_seconds == 1800

    def test_create_session(self):
        manager = SessionManager(timeout_minutes=30)
        session = manager.create_session("sess_123", "127.0.0.1", "Mozilla/5.0")
        assert session.session_id == "sess_123"
        assert session.ip_address == "127.0.0.1"
        assert session.user_agent == "Mozilla/5.0"
        assert session.is_active is True

    def test_get_session(self):
        manager = SessionManager(timeout_minutes=30)
        manager.create_session("sess_123", "127.0.0.1")
        session = manager.get_session("sess_123")
        assert session is not None
        assert session.session_id == "sess_123"

    def test_get_nonexistent_session(self):
        manager = SessionManager(timeout_minutes=30)
        assert manager.get_session("nonexistent") is None

    def test_update_activity(self):
        manager = SessionManager(timeout_minutes=30)
        manager.create_session("sess_123", "127.0.0.1")
        old_time = manager._sessions["sess_123"].last_activity
        time.sleep(0.01)
        assert manager.update_activity("sess_123") is True
        assert manager._sessions["sess_123"].last_activity > old_time

    def test_invalidate_session(self):
        manager = SessionManager(timeout_minutes=30)
        manager.create_session("sess_123", "127.0.0.1")
        assert manager.invalidate_session("sess_123") is True
        assert manager.get_session("sess_123") is None

    def test_session_timeout(self):
        manager = SessionManager(timeout_minutes=0)  # 0 minute timeout
        manager.create_session("sess_123", "127.0.0.1")
        time.sleep(0.01)
        # Session should be expired
        assert manager.get_session("sess_123") is None

    def test_cleanup_expired(self):
        manager = SessionManager(timeout_minutes=0)
        manager.create_session("sess_1", "127.0.0.1")
        manager.create_session("sess_2", "127.0.0.1")
        time.sleep(0.01)
        removed = manager.cleanup_expired()
        assert removed == 2

    def test_get_active_sessions(self):
        manager = SessionManager(timeout_minutes=30)
        manager.create_session("sess_1", "127.0.0.1")
        manager.create_session("sess_2", "127.0.0.2")
        sessions = manager.get_active_sessions()
        assert len(sessions) == 2

    def test_get_stats(self):
        manager = SessionManager(timeout_minutes=30)
        manager.create_session("sess_1", "127.0.0.1")
        stats = manager.get_stats()
        assert stats["active_sessions"] == 1
        assert stats["total_sessions"] == 1
        assert stats["timeout_minutes"] == 30


class TestIPBlocker:
    """Tests for IPBlocker."""

    def test_init(self):
        blocker = IPBlocker(max_violations=10, block_duration=3600)
        assert blocker._max_violations == 10
        assert blocker._block_duration == 3600

    def test_record_violation(self):
        blocker = IPBlocker(max_violations=3, block_duration=3600)
        assert blocker.record_violation("192.168.1.1") is False
        assert blocker.record_violation("192.168.1.1") is False
        assert blocker.record_violation("192.168.1.1") is True  # Now blocked

    def test_is_blocked(self):
        blocker = IPBlocker(max_violations=1, block_duration=3600)
        blocker.record_violation("192.168.1.1")
        blocked, retry_after = blocker.is_blocked("192.168.1.1")
        assert blocked is True
        assert retry_after > 0

    def test_is_not_blocked(self):
        blocker = IPBlocker(max_violations=10)
        blocked, retry_after = blocker.is_blocked("192.168.1.1")
        assert blocked is False
        assert retry_after == 0

    def test_unblock(self):
        blocker = IPBlocker(max_violations=1, block_duration=3600)
        blocker.record_violation("192.168.1.1")
        assert blocker.unblock("192.168.1.1") is True
        blocked, _ = blocker.is_blocked("192.168.1.1")
        assert blocked is False

    def test_unblock_nonexistent(self):
        blocker = IPBlocker()
        assert blocker.unblock("192.168.1.1") is False

    def test_get_stats(self):
        blocker = IPBlocker(max_violations=1, block_duration=3600)
        blocker.record_violation("192.168.1.1")
        stats = blocker.get_stats()
        assert stats["blocked_ips"] == 1
        assert stats["total_violations"] == 1

    def test_different_ips_independent(self):
        blocker = IPBlocker(max_violations=2, block_duration=3600)
        blocker.record_violation("192.168.1.1")
        blocker.record_violation("192.168.1.1")
        # Different IP should not be blocked
        blocked, _ = blocker.is_blocked("10.0.0.1")
        assert blocked is False


class TestSecurityHeaders:
    """Tests for security headers."""

    def test_get_security_headers(self):
        headers = get_security_headers()
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "Strict-Transport-Security" in headers
        assert "Content-Security-Policy" in headers

    def test_x_content_type_options(self):
        headers = get_security_headers()
        assert headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self):
        headers = get_security_headers()
        assert headers["X-Frame-Options"] == "DENY"
