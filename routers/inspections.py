from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, auth
from ..auth import get_db, require_role, get_current_user
from datetime import datetime
from ..models import InspectionComment, Inspection
from fastapi.responses import StreamingResponse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
import requests
import tempfile

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

@router.post("/{inspection_id}/comments", response_model=schemas.InspectionCommentResponse)
def add_comment(
    inspection_id: int,
    comment: schemas.InspectionCommentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    new_comment = InspectionComment(
        inspection_id=inspection_id,
        user_id=current_user.id,
        action=comment.action,
        message=comment.message,
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return {
        "id": new_comment.id,
        "user_id": new_comment.user_id,
        "user_name": current_user.name,
        "action": new_comment.action,
        "message": new_comment.message,
        "created_at": new_comment.created_at,
    }


@router.get("/{inspection_id}/comments", response_model=List[schemas.InspectionCommentResponse])
def get_comments(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    comments = (
        db.query(InspectionComment)
        .filter(InspectionComment.inspection_id == inspection_id)
        .order_by(InspectionComment.created_at.asc())
        .all()
    )
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "user_name": c.user.name,
            "action": c.action,
            "message": c.message,
            "created_at": c.created_at,
        }
        for c in comments
    ]

@router.post("/{inspection_id}/comments", response_model=schemas.InspectionCommentResponse)
def add_comment(
    inspection_id: int,
    comment: schemas.InspectionCommentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    new_comment = InspectionComment(
        inspection_id=inspection_id,
        user_id=current_user.id,
        action=comment.action,
        message=comment.message,
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return {
        "id": new_comment.id,
        "user_id": new_comment.user_id,
        "user_name": current_user.name,
        "action": new_comment.action,
        "message": new_comment.message,
        "created_at": new_comment.created_at,
    }


@router.get("/{inspection_id}/comments", response_model=List[schemas.InspectionCommentResponse])
def get_comments(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    comments = (
        db.query(InspectionComment)
        .filter(InspectionComment.inspection_id == inspection_id)
        .order_by(InspectionComment.created_at.asc())
        .all()
    )
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "user_name": c.user.name,
            "action": c.action,
            "message": c.message,
            "created_at": c.created_at,
        }
        for c in comments
    ]

@router.get("/{inspection_id}/report")
def generate_inspection_report(inspection_id: int, db: Session = Depends(get_db)):
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    comments = inspection.comments or []
    items = inspection.items or []

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>Inspection Report #{inspection.id}</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Template: {inspection.template.name}", styles["Normal"]))
    story.append(Paragraph(f"Location: {inspection.location}", styles["Normal"]))
    story.append(Paragraph(f"Assigned to: {inspection.assigned_to.name}", styles["Normal"]))
    story.append(Paragraph(f"Status: {inspection.status}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Checklist Items</b>", styles["Heading2"]))
    data = [["Item", "Checked", "Notes"]]
    for item in items:
        data.append([
            item.description,
            "✅" if item.checked else "❌",
            item.notes or ""
        ])

    table = Table(data, colWidths=[250, 60, 200])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER')
    ]))
    story.append(table)
    story.append(Spacer(1, 12))

    # Add photos (if any)
    story.append(Paragraph("<b>Photos</b>", styles["Heading2"]))
    for item in items:
        if item.photo_url:
            try:
                # Download image temporarily
                response = requests.get(item.photo_url)
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmpfile:
                        tmpfile.write(response.content)
                        tmpfile.flush()
                        story.append(Paragraph(item.description, styles["Normal"]))
                        story.append(Image(tmpfile.name, width=150, height=100))
                        story.append(Spacer(1, 8))
            except Exception:
                story.append(Paragraph("(Could not load photo)", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Comments section
    story.append(Paragraph("<b>Comments & Approval History</b>", styles["Heading2"]))
    for c in comments:
        story.append(Paragraph(
            f"<b>{c.user.name}</b> ({c.action}) [{c.created_at.strftime('%Y-%m-%d %H:%M:%S')}]<br/>{c.message}",
            styles["Normal"]
        ))
        story.append(Spacer(1, 8))

    # Sign-off
    if inspection.status == "Approved":
        story.append(Spacer(1, 24))
        story.append(Paragraph("<b>Approved by Lead Engineer:</b>", styles["Heading2"]))
        story.append(Paragraph(f"{inspection.assigned_by.name} on {inspection.completed_at.strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=inspection_{inspection.id}_report.pdf"
    })
