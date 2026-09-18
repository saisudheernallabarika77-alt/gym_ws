"""Fitora - auth request/response schemas."""
from __future__ import annotations
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator


# --------------------------------------------------------------- user signup
class UserSignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=20)
    address: str = Field(min_length=3, max_length=500)
    locality: str | None = None
    district: str | None = None
    pincode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    password: str = Field(min_length=6, max_length=72)
    confirm_password: str

    @field_validator("phone")
    @classmethod
    def _clean_phone(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 10:
            raise ValueError("Enter a valid phone number")
        return "+91 " + digits[-10:]

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v: str, info) -> str:
        if info.data.get("password") and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)


class OTPResendRequest(BaseModel):
    email: EmailStr
    purpose: str = "signup"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in_minutes: int
    profile: dict


class MessageResponse(BaseModel):
    success: bool = True
    message: str
    data: dict | None = None


# ---------------------------------------------------------- owner signup
class OwnerSignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=20)
    business_name: str = Field(min_length=2, max_length=180)
    password: str = Field(min_length=6, max_length=72)
    confirm_password: str

    @field_validator("phone")
    @classmethod
    def _clean_phone(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 10:
            raise ValueError("Enter a valid phone number")
        return "+91 " + digits[-10:]

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v: str, info) -> str:
        if info.data.get("password") and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


# --------------------------------------------------------------- profile
class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    address: str | None = None
    locality: str | None = None
    district: str | None = None
    pincode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    height_cm: float | None = Field(default=None, ge=80, le=250)
    weight_kg: float | None = Field(default=None, ge=25, le=250)
    fitness_goal: str | None = None
    medical_notes: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    photo_url: str | None = None
