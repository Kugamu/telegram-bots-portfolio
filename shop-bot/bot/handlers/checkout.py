"""Оформлення замовлення (FSM): ім'я → телефон → адреса → оплата → [фото чека] → підтвердження."""
import logging
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import repo
from ..db.models import PaymentMethod
from ..keyboards import user as kb
from ..keyboards.callbacks import CartCb, CheckoutCb
from ..services.notify import notify_admins_new_order
from ..states import CheckoutSG
from ..utils.text import cart_text, money

router = Router(name="checkout")
log = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{10,18}$")


def normalize_phone(raw: str) -> str | None:
    if not PHONE_RE.match(raw.strip()):
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits.startswith("0"):  # 0671234567 → +380671234567
        digits = "38" + digits
    return "+" + digits if 11 <= len(digits) <= 15 else None


@router.callback_query(CartCb.filter(F.action == "checkout"))
async def checkout_start(call: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    items = await repo.get_cart(session, call.from_user.id)
    if not items:
        await call.answer("Кошик порожній", show_alert=True)
        return
    await state.clear()
    await state.set_state(CheckoutSG.name)
    name_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=call.from_user.full_name[:60])], [KeyboardButton(text=kb.BTN_CANCEL)]],
        resize_keyboard=True,
    )
    await call.message.answer("📝 <b>Оформлення замовлення</b> (крок 1/4)\n\nЯк до вас звертатися? Введіть ім'я та прізвище:",
                              reply_markup=name_kb)
    await call.answer()


@router.message(CheckoutSG.name, F.text)
async def checkout_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 60:
        await message.answer("Ім'я має містити від 2 до 60 символів. Спробуйте ще раз:")
        return
    await state.update_data(name=name)
    await state.set_state(CheckoutSG.phone)
    await message.answer("📞 Крок 2/4. Надішліть номер телефону кнопкою нижче або введіть вручну (+380…):",
                         reply_markup=kb.phone_kb())


@router.message(CheckoutSG.phone, F.contact)
async def checkout_phone_contact(message: Message, state: FSMContext) -> None:
    await _save_phone(message, state, message.contact.phone_number)


@router.message(CheckoutSG.phone, F.text)
async def checkout_phone_text(message: Message, state: FSMContext) -> None:
    await _save_phone(message, state, message.text)


async def _save_phone(message: Message, state: FSMContext, raw: str) -> None:
    phone = normalize_phone(raw if raw.startswith("+") or raw.startswith("0") else "+" + raw)
    if phone is None:
        await message.answer("Схоже, номер некоректний 🤔 Приклад: <code>+380671234567</code>")
        return
    await state.update_data(phone=phone)
    await state.set_state(CheckoutSG.address)
    await message.answer("📍 Крок 3/4. Вкажіть місто та відділення Нової Пошти (наприклад: <i>Київ, відділення 25</i>):",
                         reply_markup=kb.cancel_kb())


@router.message(CheckoutSG.address, F.text)
async def checkout_address(message: Message, state: FSMContext) -> None:
    address = message.text.strip()
    if len(address) < 5:
        await message.answer("Будь ласка, вкажіть адресу детальніше:")
        return
    await state.update_data(address=address)
    await state.set_state(CheckoutSG.payment)
    await message.answer("💳 Крок 4/4. Оберіть спосіб оплати:", reply_markup=kb.payment_kb())


@router.callback_query(CheckoutSG.payment, CheckoutCb.filter(F.action.in_({"pay_card", "pay_cod"})))
async def checkout_payment(call: CallbackQuery, callback_data: CheckoutCb, session: AsyncSession, state: FSMContext) -> None:
    items = await repo.get_cart(session, call.from_user.id)
    total = sum(i.product.price * i.quantity for i in items)
    if callback_data.action == "pay_card":
        await state.update_data(payment=PaymentMethod.CARD.value)
        await state.set_state(CheckoutSG.receipt)
        await call.message.edit_text(
            f"💳 Переказ на карту\n\nСума до сплати: <b>{money(total)}</b>\n"
            f"Реквізити: <code>{escape(get_settings().payment_details)}</code>\n\n"
            "Після оплати надішліть сюди <b>фото або скріншот квитанції</b> 📸"
        )
    else:
        await state.update_data(payment=PaymentMethod.COD.value, receipt=None)
        await _ask_confirm(call.message, session, state, call.from_user.id)
    await call.answer()


@router.message(CheckoutSG.receipt, F.photo)
async def checkout_receipt_photo(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.update_data(receipt=message.photo[-1].file_id)
    await _ask_confirm(message, session, state, message.from_user.id)


@router.message(CheckoutSG.receipt, F.document.mime_type.startswith("image/"))
async def checkout_receipt_doc(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await message.answer("Будь ласка, надішліть квитанцію саме як <b>фото</b> (не файлом) 🙏")


@router.message(CheckoutSG.receipt)
async def checkout_receipt_wrong(message: Message) -> None:
    await message.answer("Очікую фото квитанції 📸 Або натисніть «✖️ Скасувати».")


async def _ask_confirm(message: Message, session: AsyncSession, state: FSMContext, user_id: int) -> None:
    data = await state.get_data()
    items = await repo.get_cart(session, user_id)
    await state.set_state(CheckoutSG.confirm)
    pay = PaymentMethod(data["payment"]).label
    receipt = "\n🧾 Квитанцію отримано" if data.get("receipt") else ""
    await message.answer(
        f"{cart_text(items)}\n\n"
        f"👤 {escape(data['name'])}\n📞 {data['phone']}\n📍 {escape(data['address'])}\n"
        f"Оплата: {pay}{receipt}\n\nВсе вірно?",
        reply_markup=kb.confirm_kb(),
    )


@router.callback_query(CheckoutSG.confirm, CheckoutCb.filter(F.action == "confirm"))
async def checkout_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    try:
        order = await repo.create_order_from_cart(
            session,
            user_id=call.from_user.id,
            customer_name=data["name"],
            phone=data["phone"],
            address=data["address"],
            payment=PaymentMethod(data["payment"]),
            receipt_file_id=data.get("receipt"),
        )
    except repo.CheckoutError as e:
        await state.clear()
        await call.message.edit_text(f"⚠️ Не вдалося оформити замовлення: {escape(str(e))}\nПеревірте кошик.")
        await call.answer()
        return
    await state.clear()
    await call.message.edit_text(
        f"🎉 Дякуємо! Замовлення <b>№{order.id}</b> на суму <b>{money(order.total)}</b> прийнято.\n"
        "Менеджер зв'яжеться з вами найближчим часом. Статус можна відстежити в «📦 Мої замовлення»."
    )
    await call.message.answer("Головне меню 👇", reply_markup=kb.main_menu())
    await call.answer("Замовлення оформлено!")
    log.info("New order #%s from %s, total=%s", order.id, call.from_user.id, order.total)
    await notify_admins_new_order(bot, order)


@router.callback_query(CheckoutCb.filter(F.action == "cancel"))
async def checkout_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("Оформлення скасовано. Товари залишилися в кошику 🛒")
    await call.message.answer("Головне меню 👇", reply_markup=kb.main_menu())
    await call.answer()


@router.callback_query(CheckoutCb.filter())
async def checkout_stale(call: CallbackQuery) -> None:
    # Кнопка з попереднього (вже завершеного/скасованого) оформлення
    await call.answer("Ця кнопка вже неактуальна. Відкрийте 🛒 Кошик, щоб оформити замовлення знову.", show_alert=True)


# Текст замість кнопки на кроках, де очікується натискання inline-кнопки
@router.message(CheckoutSG.payment)
@router.message(CheckoutSG.confirm)
async def checkout_expect_button(message: Message) -> None:
    await message.answer("Будь ласка, скористайтеся кнопками під повідомленням вище 👆 або натисніть «✖️ Скасувати».")


@router.message(CheckoutSG.name)
@router.message(CheckoutSG.phone)
@router.message(CheckoutSG.address)
async def checkout_expect_text(message: Message) -> None:
    await message.answer("Очікую текстову відповідь 🙂 Або натисніть «✖️ Скасувати».")
