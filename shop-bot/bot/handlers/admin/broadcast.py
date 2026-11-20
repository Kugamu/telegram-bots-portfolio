"""Розсилка всім користувачам: будь-який тип повідомлення (текст, фото, відео…), з попереднім переглядом."""
import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import repo
from ...keyboards import admin as akb
from ...keyboards.callbacks import AdminCb
from ...states import BroadcastSG

router = Router(name="admin_broadcast")
log = logging.getLogger(__name__)


@router.callback_query(AdminCb.filter((F.section == "mail") & (F.action == "list")))
async def mail_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastSG.message)
    await call.message.answer(
        "📣 Надішліть повідомлення для розсилки — текст, фото з підписом, відео тощо.\n"
        "Я покажу попередній перегляд перед відправкою.\n/cancel — скасувати"
    )
    await call.answer()


@router.message(BroadcastSG.message)
async def mail_preview(message: Message, state: FSMContext) -> None:
    await state.update_data(chat_id=message.chat.id, message_id=message.message_id)
    await state.set_state(BroadcastSG.confirm)
    await message.answer("👆 Так виглядатиме розсилка. Надсилаємо?", reply_markup=akb.broadcast_confirm_kb())


@router.callback_query(BroadcastSG.confirm, AdminCb.filter((F.section == "mail") & (F.action == "send")))
async def mail_send(call: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    user_ids = await repo.active_user_ids(session)
    await call.message.edit_text(f"⏳ Розсилка запущена на {len(user_ids)} користувачів…")
    await call.answer()

    sent = failed = 0
    for uid in user_ids:
        try:
            await bot.copy_message(uid, data["chat_id"], data["message_id"])
            sent += 1
        except TelegramRetryAfter as e:  # flood-control: чекаємо скільки просить Telegram
            await asyncio.sleep(e.retry_after)
            try:
                await bot.copy_message(uid, data["chat_id"], data["message_id"])
                sent += 1
            except Exception:
                failed += 1
        except TelegramForbiddenError:  # користувач заблокував бота
            await repo.mark_blocked(session, uid)
            failed += 1
        except Exception as e:
            log.warning("Broadcast to %s failed: %s", uid, e)
            failed += 1
        await asyncio.sleep(0.05)  # ~20 повідомлень/сек — в межах лімітів Telegram

    await call.message.answer(f"✅ Розсилку завершено.\nДоставлено: <b>{sent}</b>\nНе доставлено: <b>{failed}</b>",
                              reply_markup=akb.back_to_menu_kb())


@router.callback_query(AdminCb.filter((F.section == "mail") & (F.action == "cancel")))
async def mail_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("Розсилку скасовано.", reply_markup=akb.back_to_menu_kb())
    await call.answer()


@router.callback_query(AdminCb.filter(F.section == "mail"))
async def mail_stale(call: CallbackQuery) -> None:
    await call.answer("Ця розсилка вже неактуальна. Почніть заново з /admin.", show_alert=True)
