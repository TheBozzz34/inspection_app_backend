from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, auth
from ..auth import get_db, require_role, get_current_user
from datetime import datetime

router = APIRouter(prefix="/inspections", tags=["inspections"])

# Create/Assign an inspection (LeadEngineer)
@router.post("/", response_model=schemas.InspectionOut, dependencies=[Depends(require_role("LeadEngineer"))])
def create_inspection(payload: schemas.InspectionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Optional: create from template
    insp = models.Inspection(
        template_id=payload.template_id,
        assigned_to=payload.assigned_to,
        assigned_by=current_user.id,
        location=payload.location,
        notes=payload.notes,
        status=models.InspectionStatus.Assigned
    )
    db.add(insp)
    db.flush()
    # If created from template, copy items
    if payload.template_id:
        tmpl = db.query(models.InspectionTemplate).filter(models.InspectionTemplate.id == payload.template_id).first()
        if not tmpl:
            raise HTTPException(status_code=404, detail="Template not found")
        for titem in tmpl.items:
            ii = models.InspectionItem(inspection_id=insp.id, description=titem.description, checked=False)
            db.add(ii)
    db.commit()
    db.refresh(insp)
    return insp

# List inspections (filter by assigned_to optional)
@router.get("/", response_model=List[schemas.InspectionOut])
def list_inspections(assigned_to: int | None = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    q = db.query(models.Inspection)
    if assigned_to:
        q = q.filter(models.Inspection.assigned_to == assigned_to)
    return q.order_by(models.Inspection.created_at.desc()).all()

# Get single inspection
@router.get("/{inspection_id}", response_model=schemas.InspectionOut)
def get_inspection(inspection_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    insp = db.query(models.Inspection).filter(models.Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return insp

# Update an inspection item (Inspector or Lead)
@router.patch("/{inspection_id}/items/{item_id}", response_model=schemas.InspectionItemOut)
def update_item(inspection_id: int, item_id: int, payload: schemas.InspectionItemUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    insp = db.query(models.Inspection).filter(models.Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    item = db.query(models.InspectionItem).filter(models.InspectionItem.id == item_id, models.InspectionItem.inspection_id == inspection_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    # Allow inspectors assigned to this inspection or leads to update
    if current_user.role != models.UserRole.LeadEngineer and insp.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to edit this inspection")
    if payload.checked is not None:
        item.checked = payload.checked
    if payload.notes is not None:
        item.notes = payload.notes
    if payload.photo_url is not None:
        item.photo_url = payload.photo_url
    # If all required items checked, optionally set Completed
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

# Set inspection status (e.g., Approve) - Lead only
@router.post("/{inspection_id}/approve", dependencies=[Depends(require_role("LeadEngineer"))])
def approve_inspection(inspection_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    insp = db.query(models.Inspection).filter(models.Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    insp.status = models.InspectionStatus.Approved
    insp.completed_at = datetime.utcnow()
    db.add(insp)
    db.commit()
    db.refresh(insp)
    return {"detail": "approved", "inspection_id": insp.id}

# Inspector can mark inspection in progress or completed
@router.post("/{inspection_id}/start", dependencies=[Depends(auth.get_current_user)])
def start_inspection(inspection_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    insp = db.query(models.Inspection).filter(models.Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if insp.assigned_to != current_user.id and current_user.role != models.UserRole.LeadEngineer:
        raise HTTPException(status_code=403, detail="Not allowed to start this inspection")
    insp.status = models.InspectionStatus.InProgress
    db.add(insp)
    db.commit()
    db.refresh(insp)
    return {"detail": "started", "inspection_id": insp.id}

@router.post("/{inspection_id}/complete", dependencies=[Depends(auth.get_current_user)])
def complete_inspection(inspection_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    insp = db.query(models.Inspection).filter(models.Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if insp.assigned_to != current_user.id and current_user.role != models.UserRole.LeadEngineer:
        raise HTTPException(status_code=403, detail="Not allowed to complete this inspection")
    insp.status = models.InspectionStatus.Completed
    insp.completed_at = datetime.utcnow()
    db.add(insp)
    db.commit()
    db.refresh(insp)
    return {"detail": "completed", "inspection_id": insp.id}
