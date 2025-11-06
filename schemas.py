from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum as PyEnum

class Role(str, PyEnum):
    LeadEngineer = "LeadEngineer"
    Inspector = "Inspector"

class Location(str, PyEnum):
    Trackside = "Trackside"
    Garage = "Garage"

class Status(str, PyEnum):
    Assigned = "Assigned"
    InProgress = "InProgress"
    Completed = "Completed"
    Approved = "Approved"

# --- User schemas ---
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: Role

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    class Config:
        orm_mode = True

# --- Template schemas ---
class TemplateItemBase(BaseModel):
    description: str
    required: bool = True

class TemplateItemCreate(TemplateItemBase):
    pass

class InspectionTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    items: List[TemplateItemCreate]

class TemplateItemOut(TemplateItemBase):
    id: int
    class Config:
        orm_mode = True

class InspectionTemplateOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    items: List[TemplateItemOut]
    class Config:
        orm_mode = True

# --- Inspection schemas ---
class InspectionItemOut(BaseModel):
    id: int
    description: str
    checked: bool
    notes: Optional[str] = None
    photo_url: Optional[str] = None
    class Config:
        orm_mode = True

class InspectionCreate(BaseModel):
    template_id: Optional[int] = None
    assigned_to: Optional[int] = None
    location: Optional[Location] = None
    notes: Optional[str] = None

class InspectionOut(BaseModel):
    id: int
    template_id: Optional[int]
    assigned_to: Optional[int]
    assigned_by: Optional[int]
    status: Status
    location: Optional[Location]
    created_at: datetime
    completed_at: Optional[datetime]
    notes: Optional[str]
    items: List[InspectionItemOut] = []
    class Config:
        orm_mode = True

class InspectionItemUpdate(BaseModel):
    checked: Optional[bool] = None
    notes: Optional[str] = None
    photo_url: Optional[str] = None

# Auth
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[Role] = None

class InspectionCommentBase(BaseModel):
    action: str
    message: str

class InspectionCommentCreate(InspectionCommentBase):
    pass

class InspectionCommentResponse(InspectionCommentBase):
    id: int
    user_id: int
    created_at: datetime
    user_name: str

    class Config:
        orm_mode = True
