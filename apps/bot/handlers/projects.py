"""/newproject (FSM-wizard), /list (с балансом + inline switch), /switch."""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import func, select

from apps.bot.fsm.states import NewProjectStates
from apps.bot.i18n import t
from apps.bot.keyboards import new_project_confirm_keyboard, project_switch_keyboard
from packages.db.base import get_sessionmaker
from packages.db.models import ActiveContext, Expense, Project, ProjectMember, User
from packages.domain.currency import format_amount, parse_amount_to_minor
from packages.domain.quota import QuotaExceeded, check_quota, decrement_quota

router = Router(name="projects")


# ─── /newproject FSM ──────────────────────────────────────────────────────────

@router.message(Command("newproject"))
async def cmd_newproject(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    await state.set_state(NewProjectStates.name)
    await message.answer(t("newproject.ask_name", locale))


@router.message(NewProjectStates.name)
async def np_name(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer(t("newproject.ask_name", locale))
        return
    await state.update_data(name=name[:256])
    await state.set_state(NewProjectStates.budget)
    await message.answer(t("newproject.ask_budget", locale))


@router.message(NewProjectStates.budget, Command("skip"))
async def np_skip_budget(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    await state.update_data(budget_minor=None)
    await _show_confirm(message, state, locale)


@router.message(NewProjectStates.budget)
async def np_budget(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    try:
        minor = parse_amount_to_minor(message.text or "")
    except ValueError:
        await message.answer(t("newproject.bad_budget", locale))
        return
    await state.update_data(budget_minor=minor)
    await _show_confirm(message, state, locale)


async def _show_confirm(message: types.Message, state: FSMContext, locale: str) -> None:
    data = await state.get_data()
    budget = data.get("budget_minor")
    if budget is not None:
        budget_line = t("newproject.budget_line_with", locale, amount=format_amount(budget, "RUB"))
    else:
        budget_line = t("newproject.budget_line_none", locale)
    await state.set_state(NewProjectStates.confirm)
    await message.answer(
        t("newproject.confirm", locale, name=data["name"], budget_line=budget_line),
        reply_markup=new_project_confirm_keyboard(),
    )


@router.callback_query(NewProjectStates.confirm, F.data == "np:cancel")
async def np_cancel_inline(query: types.CallbackQuery, state: FSMContext, locale: str = "ru") -> None:
    await state.clear()
    await query.answer()
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        await query.message.answer(t("common.cancelled", locale))


@router.callback_query(NewProjectStates.confirm, F.data == "np:confirm")
async def np_confirm_inline(query: types.CallbackQuery, state: FSMContext, locale: str = "ru") -> None:
    data = await state.get_data()
    tg = query.from_user
    if not tg:
        return
    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            await state.clear()
            return
        try:
            check_quota(user.project_quota)
        except QuotaExceeded:
            await state.clear()
            await query.answer("⚠️ Лимит проектов исчерпан", show_alert=True)
            return
        project = Project(
            owner_user_id=user.id,
            name=data["name"],
            currency="RUB",
            budget_minor=data.get("budget_minor"),
            status="active",
        )
        session.add(project)
        await session.flush()
        session.add(ProjectMember(user_id=user.id, project_id=project.id, role="owner"))
        ctx = await session.get(ActiveContext, user.id)
        if ctx:
            ctx.current_project_id = project.id
        else:
            session.add(ActiveContext(user_id=user.id, current_project_id=project.id))
        user.project_quota = decrement_quota(user.project_quota)
        await session.commit()
        created_name = project.name
    await state.clear()
    await query.answer("✅")
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        await query.message.answer(t("newproject.created", locale, name=created_name))


# Текстовый /yes оставлен как fallback для старых сессий
@router.message(NewProjectStates.confirm, Command("yes"))
async def np_confirm_text(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    data = await state.get_data()
    tg = message.from_user
    if not tg:
        return
    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            await state.clear()
            return
        try:
            check_quota(user.project_quota)
        except QuotaExceeded:
            await state.clear()
            await message.answer("⚠️ Достигнут лимит проектов твоего инвайта.")
            return
        project = Project(
            owner_user_id=user.id,
            name=data["name"],
            currency="RUB",
            budget_minor=data.get("budget_minor"),
            status="active",
        )
        session.add(project)
        await session.flush()
        session.add(ProjectMember(user_id=user.id, project_id=project.id, role="owner"))
        ctx = await session.get(ActiveContext, user.id)
        if ctx:
            ctx.current_project_id = project.id
        else:
            session.add(ActiveContext(user_id=user.id, current_project_id=project.id))
        user.project_quota = decrement_quota(user.project_quota)
        await session.commit()
        created_name = project.name
    await state.clear()
    await message.answer(t("newproject.created", locale, name=created_name))


# ─── /list, /switch ───────────────────────────────────────────────────────────

@router.message(Command("list"))
@router.message(Command("switch"))
async def cmd_list(message: types.Message, locale: str = "ru") -> None:
    tg = message.from_user
    if not tg:
        return
    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            return
        ctx = await session.get(ActiveContext, user.id)
        active_id = ctx.current_project_id if ctx else None
        rows = await session.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id)
            .order_by(Project.created_at.desc())
        )
        projects = rows.scalars().all()
        if not projects:
            await message.answer(t("projects.none", locale))
            return
        # Подсчёт балансов одним запросом: project_id → total_minor
        totals_rows = await session.execute(
            select(Expense.project_id, func.coalesce(func.sum(Expense.amount_minor), 0))
            .where(Expense.project_id.in_([p.id for p in projects]))
            .group_by(Expense.project_id)
        )
        totals: dict[int, int] = {pid: total for pid, total in totals_rows.all()}

    # Текстовая сводка с балансами + inline-кнопки для переключения
    lines = [t("projects.list_header", locale)]
    for p in projects:
        marker = "🟢" if p.id == active_id else "⚪"
        total = totals.get(p.id, 0)
        spent = format_amount(total, p.currency)
        if p.budget_minor is not None:
            remaining = p.budget_minor - total
            line = f"{marker} <b>{p.name}</b>\n   потрачено: {spent} / бюджет: {format_amount(p.budget_minor, p.currency)}"
            if remaining < 0:
                line += f"  ⚠️ перерасход {format_amount(-remaining, p.currency)}"
        else:
            line = f"{marker} <b>{p.name}</b>  ·  потрачено: {spent}"
        lines.append(line)

    kb = project_switch_keyboard([(p.id, p.name, p.id == active_id) for p in projects])
    await message.answer("\n\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("proj:switch:"))
async def cb_switch(query: types.CallbackQuery, locale: str = "ru") -> None:
    if not query.data or not query.from_user:
        return
    try:
        project_id = int(query.data.split(":")[2])
    except (IndexError, ValueError):
        return
    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User).where(User.telegram_id == query.from_user.id))
        if not user:
            return
        member = await session.scalar(
            select(ProjectMember).where(
                ProjectMember.user_id == user.id,
                ProjectMember.project_id == project_id,
            )
        )
        if not member:
            await query.answer(t("projects.not_yours", locale), show_alert=True)
            return
        ctx = await session.get(ActiveContext, user.id)
        if ctx:
            ctx.current_project_id = project_id
        else:
            session.add(ActiveContext(user_id=user.id, current_project_id=project_id))
        project = await session.get(Project, project_id)
        await session.commit()
    await query.answer()
    if project and query.message:
        await query.message.answer(t("projects.switched", locale, name=project.name))
