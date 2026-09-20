from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str
    name: Optional[str] = None
    address: Optional[str] = None


class AddressRequest(BaseModel):
    label: str = "Home"
    fullAddress: str
    house: str = ""
    landmark: str = ""
    city: str = ""
    pincode: str = ""
    placeId: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class PartnerProfileUpdate(BaseModel):
    name: str
    email: str
    logoUrl: str = ""
    password: Optional[str] = None


class RestaurantOnboardingRequest(BaseModel):
    name: str
    cuisine: str
    deliveryMinutes: str = "25–35 min"
    imageUrl: str = ""
    description: str = ""


class MenuItemRequest(BaseModel):
    name: str
    price: int = Field(ge=1)
    emoji: str = "🍽️"
    imageUrl: str = ""
    foodType: Optional[str] = None


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = Field(default=None, ge=1)
    emoji: Optional[str] = None
    imageUrl: Optional[str] = None
    available: Optional[bool] = None


class RestaurantStatusRequest(BaseModel):
    isOpen: bool


class OrderStatusRequest(BaseModel):
    status: str
    restaurantId: str


class OrderItemRequest(BaseModel):
    id: int
    quantity: int = Field(default=1, ge=1)


class OrderRequest(BaseModel):
    userId: Optional[UUID] = None
    userName: str = "Ananya"
    address: Optional[str] = None
    items: list[OrderItemRequest] = Field(default_factory=list)


class PaymentRequest(BaseModel):
    method: str = "upi"
