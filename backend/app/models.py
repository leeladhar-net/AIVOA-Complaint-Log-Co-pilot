from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Committed")
    complaint_source: Mapped[str] = mapped_column(String(100), default="")
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    product_name: Mapped[str] = mapped_column(String(255), default="")
    product_strength: Mapped[str] = mapped_column(String(100), default="")
    batch_number: Mapped[str] = mapped_column(String(100), default="", index=True)
    affected_quantity: Mapped[str] = mapped_column(String(100), default="")
    manufacturing_date: Mapped[str] = mapped_column(String(50), default="")
    expiry_date: Mapped[str] = mapped_column(String(50), default="")
    originating_site_block: Mapped[str] = mapped_column(String(255), default="")
    impacted_materials: Mapped[str] = mapped_column(Text, default="")
    complaint_category: Mapped[str] = mapped_column(String(255), default="")
    complaint_description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(50), default="")
    suggested_next_action: Mapped[str] = mapped_column(Text, default="")
    initial_risk_assessment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
