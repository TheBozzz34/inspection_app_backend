from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class UserRole(enum.Enum):
    LeadEngineer = "LeadEngineer"
    Inspector = "Inspector"

class InspectionStatus(enum.Enum):
    Assigned = "Assigned"
    InProgress = "InProgress"
    Completed = "Completed"
    Approved = "Approved"

class LocationType(enum.Enum):
    Trackside = "Trackside"
    Garage = "Garage"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)

class InspectionTemplate(Base):
    __tablename__ = "inspection_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    items = relationship("TemplateItem", back_populates="template", cascade="all, delete-orphan")

class TemplateItem(Base):
    __tablename__ = "template_items"
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("inspection_templates.id"))
    description = Column(String, nullable=False)
    required = Column(Boolean, default=True)

    template = relationship("InspectionTemplate", back_populates="items")

class Inspection(Base):
    __tablename__ = "inspections"
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("inspection_templates.id"), nullable=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(InspectionStatus), default=InspectionStatus.Assigned)
    location = Column(Enum(LocationType), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    template = relationship("InspectionTemplate")
    items = relationship("InspectionItem", back_populates="inspection", cascade="all, delete-orphan")
    assignee = relationship("User", foreign_keys=[assigned_to], lazy="joined")
    assigner = relationship("User", foreign_keys=[assigned_by], lazy="joined")

    comments = relationship("InspectionComment", back_populates="inspection", cascade="all, delete-orphan")

class InspectionItem(Base):
    __tablename__ = "inspection_items"
    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"))
    description = Column(String, nullable=False)
    checked = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    photo_url = Column(String, nullable=True)

    inspection = relationship("Inspection", back_populates="items")

class InspectionComment(Base):
    __tablename__ = "inspection_comments"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)  # e.g., 'Comment', 'Approve', 'Recheck'
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    inspection = relationship("Inspection", back_populates="comments")
