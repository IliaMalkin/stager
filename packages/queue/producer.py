from __future__ import annotations

from celery import Celery


class TaskProducer:
    def __init__(self, broker_url: str) -> None:
        self._app = Celery(broker=broker_url)

    def enqueue_ocr(
        self,
        file_id: str,
        chat_id: int,
        project_id: int,
        user_tg_id: int,
        locale: str,
    ) -> None:
        self._app.send_task(
            "ocr.process_receipt",
            args=[file_id, user_tg_id, chat_id, project_id, locale],
        )
