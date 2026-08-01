from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# SQLite is a file-based database and needs no server, Docker, or extra setup.
DATABASE_URL = "sqlite:///./aivoa.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    complaint_source: Mapped[Optional[str]] = mapped_column(String(120))
    customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    product_name: Mapped[Optional[str]] = mapped_column(String(255))
    product_strength: Mapped[Optional[str]] = mapped_column(String(120))
    batch_lot_number: Mapped[Optional[str]] = mapped_column(String(120))
    manufacturing_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    quantity_affected: Mapped[Optional[str]] = mapped_column(String(120))
    complaint_type: Mapped[Optional[str]] = mapped_column(String(120))
    complaint_date: Mapped[Optional[date]] = mapped_column(Date)
    detailed_description: Mapped[Optional[str]] = mapped_column(Text)
    initial_severity: Mapped[Optional[str]] = mapped_column(String(32))
    priority: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(64), default="Pending Triage")
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)
    risk_rationale: Mapped[Optional[str]] = mapped_column(Text)
    source_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DuplicateAlert(Base):
    """An auditable QA alert created when a saved complaint resembles an earlier one."""
    __tablename__ = "duplicate_alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    matching_complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    notification_note: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="Open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
