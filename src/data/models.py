"""数据模型定义"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import date


@dataclass
class ProductItem:
    """商品项"""
    hs_code: str
    product_name: str
    quantity: float
    unit: str
    unit_price: float
    total_value: float
    weight: float
    origin: str
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hs_code": self.hs_code,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "total_value": self.total_value,
            "weight": self.weight,
            "origin": self.origin,
            **self.additional_info
        }


@dataclass
class CustomsData:
    """海关数据主模型"""
    exporter: str
    importer: str
    products: List[ProductItem]
    declaration_date: Optional[date] = None
    invoice_number: Optional[str] = None
    contract_number: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    currency: str = "CNY"
    additional_fields: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_quantity(self) -> float:
        """总数量"""
        return sum(p.quantity for p in self.products)

    @property
    def total_value(self) -> float:
        """总价值"""
        return sum(p.total_value for p in self.products)

    @property
    def total_weight(self) -> float:
        """总重量"""
        return sum(p.weight for p in self.products)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "exporter": self.exporter,
            "importer": self.importer,
            "products": [p.to_dict() for p in self.products],
            "declaration_date": self.declaration_date.isoformat() if self.declaration_date else None,
            "invoice_number": self.invoice_number,
            "contract_number": self.contract_number,
            "port_of_loading": self.port_of_loading,
            "port_of_discharge": self.port_of_discharge,
            "currency": self.currency,
            "totals": {
                "quantity": self.total_quantity,
                "value": self.total_value,
                "weight": self.total_weight
            },
            **self.additional_fields
        }
