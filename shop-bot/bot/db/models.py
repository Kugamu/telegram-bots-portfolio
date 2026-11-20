"""ORM-моделі (SQLAlchemy 2.0, типізовані Mapped-колонки)."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OrderStatus(str, enum.Enum):
    NEW = "new"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DONE = "done"
    CANCELED = "canceled"

    @property
    def label(self) -> str:
        return STATUS_LABELS[self]


STATUS_LABELS = {
    OrderStatus.NEW: "🆕 Нове",
    OrderStatus.PROCESSING: "⏳ В обробці",
    OrderStatus.SHIPPED: "🚚 Відправлено",
    OrderStatus.DONE: "✅ Виконано",
    OrderStatus.CANCELED: "❌ Скасовано",
}


class PaymentMethod(str, enum.Enum):
    CARD = "card"
    COD = "cod"  # накладений платіж

    @property
    def label(self) -> str:
        return "💳 Переказ на карту" if self is PaymentMethod.CARD else "📦 Накладений платіж"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(128), default="")
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # заблокував бота
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)

    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)  # у гривнях
    stock: Mapped[int] = mapped_column(Integer, default=0)
    photo: Mapped[str | None] = mapped_column(String(512))  # file_id або URL
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Нормалізований текст для пошуку: SQLite LOWER() не працює з кирилицею,
    # тому зберігаємо вже приведену до нижнього регістру копію.
    search_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    category: Mapped[Category] = relationship(back_populates="products")


@event.listens_for(Product, "before_insert")
@event.listens_for(Product, "before_update")
def _fill_search_text(_mapper, _conn, target: Product) -> None:
    target.search_text = f"{target.name} {target.description or ''}".casefold()


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    product: Mapped[Product] = relationship(lazy="joined")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.NEW)
    customer_name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(Text)
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    receipt_file_id: Mapped[str | None] = mapped_column(String(256))
    total: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    # Назву й ціну копіюємо: замовлення не має змінюватися, якщо товар відредагують/видалять
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    product_name: Mapped[str] = mapped_column(String(128))
    price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
