from fastapi import APIRouter, UploadFile, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import InspectionItem
from ..models import Inspection
from ..schemas import InspectionResponse
from ..auth import get_current_user
import shutil
import os

router = APIRouter(prefix="/inspection-items", tags=["inspection-items"])

UPLOAD_DIR = "uploaded_photos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/{item_id}/photo")
def upload_inspection_photo(item_id: int, file: UploadFile, db: Session = Depends(get_db)):
    item = db.query(InspectionItem).filter(InspectionItem.id == item_id).first()
    if not item:
        return {"error": "Item not found"}

    filename = f"{item_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    item.photo_url = f"/static/photos/{filename}"
    db.commit()

    return {"photo_url": item.photo_url}

@router.patch("/{inspection_id}/status")
def update_inspection_status(
    inspection_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Only lead engineer can approve/recheck
    if current_user.role != "LeadEngineer":
        raise HTTPException(status_code=403, detail="Not authorized")

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if new_status not in ["Approved", "NeedsRecheck"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    inspection.status = new_status
    db.commit()
    db.refresh(inspection)
    return inspection
