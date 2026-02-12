"""Base Celery task with structured logging and DB session support."""

from typing import Any

import structlog
from celery import Task
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


class BaseTask(Task):
    """Base task class with logging context and sync DB session support."""

    _session_maker: sessionmaker[Session] | None = None

    @property
    def session_maker(self) -> sessionmaker[Session]:
        """Lazy initialization of sync DB session maker."""
        if self._session_maker is None:
            settings = get_settings()
            engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True)
            self._session_maker = sessionmaker(bind=engine, expire_on_commit=False)
        return self._session_maker

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute task with structured logging context."""
        log = structlog.get_logger()
        log = log.bind(
            task_id=self.request.id,
            task_name=self.name,
            user_id=kwargs.get("user_id"),
            activity_id=kwargs.get("activity_id"),
        )

        log.info("task_started")
        try:
            result = super().__call__(*args, **kwargs)
            log.info("task_completed", result=result)
            return result
        except Exception as exc:
            log.exception("task_failed", error=str(exc))
            raise

    def on_success(self, retval: Any, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        """Called when task completes successfully."""
        log = structlog.get_logger()
        log.info("task_success", task_id=task_id, task_name=self.name)

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Called when task fails."""
        log = structlog.get_logger()
        log.error(
            "task_failure",
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            traceback=str(einfo),
        )
