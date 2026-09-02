# Logging system
#
# setup_logger() returns a stdlib logger as before (backwards-compatible).
# An AuditLogHandler is attached so WARNING+ messages are also routed
# to the audit_log DB table (best-effort, never crashes).

import logging


class _AuditLogHandler(logging.Handler):
    """
    Bridges stdlib logging.WARNING+ messages to observability/audit_log.
    Uses a lazy import to avoid circular dependencies at module load time.
    A class-level guard prevents infinite recursion when the DB layer itself logs.
    """
    _emitting = False  # class-level guard against recursive emit

    def emit(self, record: logging.LogRecord) -> None:
        if _AuditLogHandler._emitting:
            return
        _AuditLogHandler._emitting = True
        try:
            from observability.audit_log import log_event
            severity_map = {
                logging.DEBUG:    "DEBUG",
                logging.INFO:     "INFO",
                logging.WARNING:  "WARNING",
                logging.ERROR:    "ERROR",
                logging.CRITICAL: "CRITICAL",
            }
            severity = severity_map.get(record.levelno, "INFO")
            log_event(
                trace_id=None,
                event_type="log",
                component=record.name,
                message=self.format(record),
                severity=severity,
            )
        except Exception:
            pass  # Never crash on logging failure
        finally:
            _AuditLogHandler._emitting = False


def setup_logger(name: str) -> logging.Logger:
    """
    Return a configured logger.

    Guards against duplicate handlers when the same module is imported
    multiple times (e.g. during testing or scheduler restarts).
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Stdout handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(ch)

    # Audit log bridge — WARNING+ only (avoids flooding DB with INFO spam)
    audit_handler = _AuditLogHandler()
    audit_handler.setLevel(logging.WARNING)
    audit_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(audit_handler)

    return logger
