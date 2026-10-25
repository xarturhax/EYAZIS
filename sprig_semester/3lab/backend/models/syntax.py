from sqlalchemy import Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class SyntaxResult(Base):
    __tablename__ = "syntax_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    dep_tree: Mapped[dict] = mapped_column(JSONB, nullable=False)
    const_tree: Mapped[str] = mapped_column(Text, nullable=False, default="")
    const_tree_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    roles: Mapped[dict] = mapped_column(JSONB, nullable=False)

    sentence: Mapped["Sentence"] = relationship("Sentence", back_populates="syntax")
