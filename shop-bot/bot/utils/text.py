"""Форматування текстів повідомлень."""
from html import escape

from ..db.models import CartItem, Order, Product


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " ₴"


def product_card(p: Product) -> str:
    stock = f"✅ В наявності: {p.stock} шт." if p.stock > 0 else "⛔️ Немає в наявності"
    return (
        f"<b>{escape(p.name)}</b>\n\n"
        f"{escape(p.description)}\n\n"
        f"💰 Ціна: <b>{money(p.price)}</b>\n{stock}"
    )


def cart_text(items: list[CartItem]) -> str:
    if not items:
        return "🛒 Кошик порожній.\n\nЗазирніть у каталог — там багато смачного ☕️"
    lines = ["<b>🛒 Ваш кошик</b>\n"]
    total = 0
    for n, i in enumerate(items, 1):
        subtotal = i.product.price * i.quantity
        total += subtotal
        lines.append(f"{n}. {escape(i.product.name)}\n    {i.quantity} × {money(i.product.price)} = {money(subtotal)}")
    lines.append(f"\n<b>Разом: {money(total)}</b>")
    return "\n".join(lines)


def order_text(o: Order, for_admin: bool = False) -> str:
    items = "\n".join(
        f"• {escape(i.product_name)} — {i.quantity} × {money(i.price)}" for i in o.items
    )
    text = (
        f"<b>Замовлення №{o.id}</b>  {o.status.label}\n"
        f"🗓 {o.created_at:%d.%m.%Y %H:%M}\n\n"
        f"{items}\n\n"
        f"💰 <b>Сума: {money(o.total)}</b>\n"
        f"Оплата: {o.payment_method.label}"
    )
    if for_admin:
        text += (
            f"\n\n👤 {escape(o.customer_name)}\n"
            f"📞 {escape(o.phone)}\n"
            f"📍 {escape(o.address)}\n"
            f"🆔 <a href=\"tg://user?id={o.user_id}\">клієнт</a> (<code>{o.user_id}</code>)"
        )
    return text
