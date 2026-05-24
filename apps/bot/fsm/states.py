from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class NewProjectStates(StatesGroup):
    name = State()
    budget = State()
    confirm = State()


class PhotoReviewStates(StatesGroup):
    waiting_ocr = State()
    review = State()
    edit_amount = State()
    edit_category = State()
    edit_vendor = State()
