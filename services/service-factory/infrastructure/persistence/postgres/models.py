from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MachineModel(Base):
    __tablename__ = "machines"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    production_line = Column(String, nullable=False, index=True)
    location = Column(String, nullable=False, default="")
    machine_type = Column(String, nullable=False, default="")
    nominal_power_kw = Column(Float, nullable=False, default=0.0)
    expected_kwh_per_unit = Column(Float, nullable=False, default=0.1)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False)
