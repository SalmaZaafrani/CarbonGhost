from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AnomalyModel(Base):
    __tablename__ = "anomalies"

    id = Column(String, primary_key=True)
    registered_at = Column(DateTime(timezone=True), nullable=False)
    machine_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    features = Column(String, nullable=False)  # séparés par des virgules
    score = Column(Float, nullable=False)
    severity = Column(String, nullable=False)

    status = Column(String, nullable=False, default="active", index=True)
    occurrences = Column(Integer, nullable=False, default=1)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    ack_comment = Column(String, nullable=True)
