from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CapabilityView
from app.db.models import Partner
from app.db.session import get_db

router = APIRouter(prefix="/partners", tags=["partners"])


@router.get("/capabilities", response_model=list[CapabilityView])
def capabilities(db: Session = Depends(get_db)) -> list[CapabilityView]:
    partners = db.scalars(select(Partner).order_by(Partner.name)).all()
    return [
        CapabilityView(
            name=item.name,
            partner_type=item.partner_type,
            status=item.status,
            adapter_status=item.adapter_status,
            live=False,
        )
        for item in partners
    ]
