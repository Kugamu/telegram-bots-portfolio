"""Шар доступу до даних: усі запити до БД зібрані тут, хендлери не пишуть SQL самі."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    CartItem,
    Category,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Product,
    User,
)

PAGE_SIZE = 6


# ---------- users ----------
async def upsert_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str) -> User:
    user = await session.get(User, tg_id)
    if user is None:
        user = User(id=tg_id, username=username, full_name=full_name)
        session.add(user)
    else:
        user.username, user.full_name, user.is_blocked = username, full_name, False
    await session.commit()
    return user


async def active_user_ids(session: AsyncSession) -> list[int]:
    return list(await session.scalars(select(User.id).where(User.is_blocked.is_(False))))


async def mark_blocked(session: AsyncSession, tg_id: int) -> None:
    await session.execute(update(User).where(User.id == tg_id).values(is_blocked=True))
    await session.commit()


# ---------- categories ----------
async def list_categories(session: AsyncSession) -> list[Category]:
    return list(await session.scalars(select(Category).order_by(Category.name)))


async def get_category(session: AsyncSession, cat_id: int) -> Category | None:
    return await session.get(Category, cat_id)


async def create_category(session: AsyncSession, name: str) -> Category:
    cat = Category(name=name)
    session.add(cat)
    await session.commit()
    return cat


async def count_products_in_category(session: AsyncSession, cat_id: int) -> int:
    return await session.scalar(select(func.count(Product.id)).where(Product.category_id == cat_id)) or 0


async def category_name_exists(session: AsyncSession, name: str) -> bool:
    return bool(await session.scalar(select(Category.id).where(Category.name == name)))


# ---------- products ----------
async def list_products(
    session: AsyncSession, cat_id: int, page: int = 0, only_active: bool = True
) -> tuple[list[Product], int]:
    """Повертає (товари на сторінці, кількість сторінок)."""
    cond = [Product.category_id == cat_id]
    if only_active:
        cond.append(Product.is_active.is_(True))
    total = await session.scalar(select(func.count(Product.id)).where(*cond)) or 0
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    rows = await session.scalars(
        select(Product).where(*cond).order_by(Product.name).offset(page * PAGE_SIZE).limit(PAGE_SIZE)
    )
    return list(rows), pages


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def search_products(session: AsyncSession, query: str, limit: int = 10) -> list[Product]:
    words = [w for w in query.casefold().split() if w]
    stmt = select(Product).where(Product.is_active.is_(True))
    for w in words:
        stmt = stmt.where(Product.search_text.contains(w))
    return list(await session.scalars(stmt.order_by(Product.name).limit(limit)))


# ---------- cart ----------
async def get_cart(session: AsyncSession, user_id: int) -> list[CartItem]:
    rows = await session.scalars(select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id))
    return list(rows)


async def add_to_cart(session: AsyncSession, user_id: int, product: Product) -> tuple[bool, int]:
    """Додає 1 шт. Повертає (успіх, нова кількість). False — якщо немає на складі."""
    item = await session.scalar(
        select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product.id)
    )
    current = item.quantity if item else 0
    if current + 1 > product.stock:
        return False, current
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=user_id, product_id=product.id, quantity=1)
        session.add(item)
    await session.commit()
    return True, current + 1


async def change_cart_qty(session: AsyncSession, user_id: int, item_id: int, delta: int) -> str:
    """Змінює кількість позиції. Повертає 'ok' | 'removed' | 'no_stock' | 'missing'."""
    item = await session.get(CartItem, item_id)
    if item is None or item.user_id != user_id:
        return "missing"
    new_qty = item.quantity + delta
    if new_qty <= 0:
        await session.delete(item)
        await session.commit()
        return "removed"
    if new_qty > item.product.stock:
        return "no_stock"
    item.quantity = new_qty
    await session.commit()
    return "ok"


async def remove_cart_item(session: AsyncSession, user_id: int, item_id: int) -> None:
    await session.execute(delete(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id))
    await session.commit()


async def clear_cart(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(CartItem).where(CartItem.user_id == user_id))
    await session.commit()


# ---------- orders ----------
class CheckoutError(Exception):
    """Товар закінчився/прихований між додаванням у кошик і оформленням."""


async def create_order_from_cart(
    session: AsyncSession,
    user_id: int,
    customer_name: str,
    phone: str,
    address: str,
    payment: PaymentMethod,
    receipt_file_id: str | None,
) -> Order:
    cart = await get_cart(session, user_id)
    if not cart:
        raise CheckoutError("Кошик порожній")
    problems = [
        i.product.name for i in cart if not i.product.is_active or i.product.stock < i.quantity
    ]
    if problems:
        raise CheckoutError("Недостатньо на складі: " + ", ".join(problems))

    order = Order(
        user_id=user_id,
        customer_name=customer_name,
        phone=phone,
        address=address,
        payment_method=payment,
        receipt_file_id=receipt_file_id,
        total=sum(i.product.price * i.quantity for i in cart),
    )
    for i in cart:
        order.items.append(
            OrderItem(product_id=i.product.id, product_name=i.product.name, price=i.product.price, quantity=i.quantity)
        )
        i.product.stock -= i.quantity  # резервуємо товар
        await session.delete(i)
    session.add(order)
    await session.commit()
    return order


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    return await session.get(Order, order_id)


async def user_orders(session: AsyncSession, user_id: int, limit: int = 10) -> list[Order]:
    rows = await session.scalars(
        select(Order).where(Order.user_id == user_id).order_by(Order.id.desc()).limit(limit)
    )
    return list(rows)


async def orders_by_status(session: AsyncSession, status: OrderStatus, limit: int = 20) -> list[Order]:
    rows = await session.scalars(
        select(Order).where(Order.status == status).order_by(Order.id.desc()).limit(limit)
    )
    return list(rows)


async def set_order_status(session: AsyncSession, order: Order, status: OrderStatus) -> None:
    # При скасуванні повертаємо товар на склад
    if status is OrderStatus.CANCELED and order.status is not OrderStatus.CANCELED:
        for item in order.items:
            if item.product_id and (p := await session.get(Product, item.product_id)):
                p.stock += item.quantity
    order.status = status
    await session.commit()


# ---------- stats ----------
async def stats(session: AsyncSession) -> dict:
    since = datetime.now() - timedelta(days=1)
    by_status = dict(
        (await session.execute(select(Order.status, func.count(Order.id)).group_by(Order.status))).all()
    )
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.status.in_([OrderStatus.SHIPPED, OrderStatus.DONE])
        )
    )
    top = (
        await session.execute(
            select(OrderItem.product_name, func.sum(OrderItem.quantity).label("q"))
            .join(Order)
            .where(Order.status != OrderStatus.CANCELED)
            .group_by(OrderItem.product_name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(5)
        )
    ).all()
    return {
        "users": await session.scalar(select(func.count(User.id))) or 0,
        "new_users_24h": await session.scalar(select(func.count(User.id)).where(User.created_at >= since)) or 0,
        "products": await session.scalar(select(func.count(Product.id))) or 0,
        "out_of_stock": await session.scalar(select(func.count(Product.id)).where(Product.stock <= 0)) or 0,
        "orders_24h": await session.scalar(select(func.count(Order.id)).where(Order.created_at >= since)) or 0,
        "by_status": by_status,
        "revenue": revenue or 0,
        "top": top,
    }
