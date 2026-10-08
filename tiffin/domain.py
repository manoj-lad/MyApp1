from dataclasses import dataclass
from enum import Enum


class TiffinType(str, Enum):
    FULL = "Full Tiffin"
    CHAPATI = "Chapati Bhaji"
    DAAL = "Daal-Rice"
    KHICHDI = "Sabudana Khichdi"

    @property
    def requires_bhaji(self):
        return self in (self.FULL, self.CHAPATI)


@dataclass(frozen=True)
class Employee:
    id: int
    name: str


@dataclass(frozen=True)
class Vendor:
    id: int
    name: str


@dataclass(frozen=True)
class Order:
    id: int
    menu_id: int
    tiffin_type: TiffinType
    recipient_id: int
    placed_by_id: int
    billed_to_id: int
    entered_by_id: int
    bhaji: str | None
    extra_chapatis: int
    base_price_paise: int
    extra_chapati_price_paise: int

    def calculate_total(self):
        return self.base_price_paise + self.extra_chapatis * self.extra_chapati_price_paise
