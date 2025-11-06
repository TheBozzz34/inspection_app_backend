from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import schemas, models, auth
from ..auth import get_db, require_role

router = APIRouter(prefix="/templates", tags=["templates"])

@router.post("/", response_model=schemas.InspectionTemplateOut, dependencies=[Depends(require_role("LeadEngineer"))])
def create_template(payload: schemas.InspectionTemplateCreate, db: Session = Depends(get_db)):
    tmpl = models.InspectionTemplate(name=payload.name, description=payload.description)
    db.add(tmpl)
    db.flush()  # to get tmpl.id
    for it in payload.items:
        item = models.TemplateItem(template_id=tmpl.id, description=it.description, required=it.required)
        db.add(item)
    db.commit()
    db.refresh(tmpl)
    return tmpl

@router.get("/", response_model=List[schemas.InspectionTemplateOut])
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(models.InspectionTemplate).all()
    return templates

@router.get("/{template_id}", response_model=schemas.InspectionTemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.query(models.InspectionTemplate).filter(models.InspectionTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl

@router.delete("/{template_id}", dependencies=[Depends(require_role("LeadEngineer"))])
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.query(models.InspectionTemplate).filter(models.InspectionTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tmpl)
    db.commit()
    return {"detail": "deleted"}
