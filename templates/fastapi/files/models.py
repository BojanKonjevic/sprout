# Add your SQLAlchemy models here.
#
# When you're ready to add auth, you'll need at minimum:
#   - User         (id, email, hashed_password, is_active, created_at)
#   - RefreshToken (id, token, user_id FK, expires_at, revoked)
#
# Example:
#
# from uuid import uuid4
# from datetime import datetime
# from uuid import UUID
# from sqlalchemy import Boolean, DateTime, String, Uuid, func
# from sqlalchemy.orm import Mapped, mapped_column
# from .database import Base
#
# class User(Base):
#     __tablename__ = "users"
#     id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
#     email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
#     hashed_password: Mapped[str] = mapped_column(String(255))
#     is_active: Mapped[bool] = mapped_column(
#       Boolean, default=True, server_default="true"
#     )
#     created_at: Mapped[datetime] = mapped_column(
#       DateTime(timezone=True), server_default=func.now()
#     )

