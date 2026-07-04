from __future__ import annotations

from pydantic import BaseModel


class PatientContext(BaseModel):
    name: str = "Eleanor Martinez"
    age: int = 72
    medicare: str = "Original Medicare Part B"
    equipment: str = "Standard manual wheelchair"
    equipment_code: str = "K0001"
    city: str = "Chicago"
    state: str = "IL"


class PcpContext(BaseModel):
    doctor_name: str = "Dr. Sarah Chen"
    practice_name: str = "Sunrise Family Medicine"
    phone: str = "(312) 555-0198"
    city: str = "Chicago"
    state: str = "IL"
