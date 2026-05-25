"""/report — summary + кнопка скачать XLSX."""

from __future__ import annotations

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from sqlalchemy import select

from apps.bot.i18n import t
from apps.bot.keyboards import report_download_keyboard
from packages.db.base import get_sessionmaker
from packages.db.models import ActiveContext, Expense, Project, ProjectMember, User
from packages.domain.categories import label_for
from packages.domain.currency import format_amount
from packages.domain.reports import summarize_expenses

router = Router(name="report")


def _ru_count(n: int) -> str:
    """1 трата / 2-4 траты / 5+ трат."""
    n = abs(n) % 100
    if 11 <= n <= 14:
        return "many"
    n %= 10
    if n == 1:
        return "singular"
    if 2 <= n <= 4:
        return "few"
    return "many"


@router.message(Command("report"))
async def cmd_report(message: types.Message, locale: str = "ru") -> None:
    tg = message.from_user
    if not tg:
        return
    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            return
        ctx = await session.get(ActiveContext, user.id)
        if not ctx or not ctx.current_project_id:
            await message.answer(t("projects.no_active", locale))
            return
        project = await session.get(Project, ctx.current_project_id)
        if not project:
            await message.answer(t("projects.no_active", locale))
            return
        rows = await session.execute(
            select(Expense).where(Expense.project_id == project.id)
        )
        expenses = rows.scalars().all()
    if not expenses:
        await message.answer(t("report.empty", locale))
        return

    summary = summarize_expenses(expenses)
    cat_lines = "\n".join(
        t("report.category_line", locale,
          label=label_for(r.category, locale),  # type: ignore[arg-type]
          amount=format_amount(r.total_minor, project.currency))
        for r in summary.by_category
    )
    count_word_key = f"report.count_{_ru_count(summary.count)}"
    text = t(
        "report.summary",
        locale,
        project=project.name,
        total=format_amount(summary.total_minor, project.currency),
        count=summary.count,
        count_word=t(count_word_key, locale),
        by_category=cat_lines,
    )
    await message.answer(text, reply_markup=report_download_keyboard(project.id))


@router.callback_query(F.data.startswith("rep:xlsx:"))
async def cb_export_xlsx(query: types.CallbackQuery, bot: Bot, locale: str = "ru") -> None:
    if not query.data or not query.from_user:
        return
    try:
        project_id = int(query.data.split(":")[2])
    except (IndexError, ValueError):
        return

    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User).where(User.telegram_id == query.from_user.id))
        if not user:
            await query.answer("⚠️", show_alert=True)
            return
        # RBAC: только член проекта может скачать XLSX
        member = await session.scalar(
            select(ProjectMember).where(
                ProjectMember.user_id == user.id,
                ProjectMember.project_id == project_id,
            )
        )
        if not member:
            await query.answer(t("projects.not_yours", locale), show_alert=True)
            return
        project = await session.get(Project, project_id)
        if not project:
            await query.answer("⚠️", show_alert=True)
            return
        rows = await session.execute(
            select(Expense).where(Expense.project_id == project_id).order_by(Expense.paid_at)
        )
        expenses = rows.scalars().all()

    await query.answer(t("report.preparing_xlsx", locale))

    # Генерим XLSX inline (не через Celery — отчёт маленький, 2-3 сек ОК).
    # Для больших — Celery `reports.export_xlsx` в apps/worker/tasks/reports.py.
    from apps.worker.tasks.reports import build_xlsx_bytes

    data = build_xlsx_bytes(project, expenses, locale=locale)
    if query.message:
        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project.name)
        await query.message.answer_document(
            BufferedInputFile(data, filename=f"{safe_name}_report.xlsx")
        )
