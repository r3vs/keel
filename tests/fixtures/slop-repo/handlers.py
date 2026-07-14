"""API layer — carries a planted intentional stub and a planted SQL-injection defect."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/users/{user_id}")
async def get_user(user_id: str):
    # PLANTED: intentional stub — completeness should mark this incompleteness, NOT a defect
    raise NotImplementedError("wire up get_user")


@router.get("/users/search")
async def search_users(q: str, db):
    # PLANTED: raw SQL by string concatenation — a real defect (SQLi)
    rows = await db.execute("SELECT * FROM users WHERE email LIKE '%" + q + "%'")
    return rows
