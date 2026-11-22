from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class CarbonGhostEventModel(Base):
    """Copie locale des événements carbone (topic carbon.events), lue par l'assistant."""
    __tablename__ = "carbon_ghost_events"

    id = Column(String, primary_key=True)
    machine_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    actual_energy_kwh = Column(Float)
    expected_energy_kwh = Column(Float)
    surconsommation_pct = Column(Float)
    avoidable_co2_kg = Column(Float)
    probable_cause = Column(String)
    confidence = Column(Float)
    recommendation = Column(String)
    status = Column(String)


class ReportModel(Base):
    """Rapports générés (automatiquement ou à la demande), conservés pour consultation."""
    __tablename__ = "reports"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    period_hours = Column(Float, nullable=False)
    generated_by = Column(String, nullable=False)  # "automatique" ou nom de l'utilisateur
    content = Column(String, nullable=False)
