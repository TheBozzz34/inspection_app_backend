from fastapi import APIRouter, UploadFile, Form, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import InspectionItem
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
