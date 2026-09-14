from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from starlette import status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
import os, shutil
from db import get_db
from models import Users, AccountRequests
from auth import create_access_token, get_current_user
from domain.user import user_crud, user_schema
from domain.user.user_crud import passwd_context
from config import PROFILE_DIR

os.makedirs(PROFILE_DIR, exist_ok=True)

router = APIRouter(prefix="/api/user")


def require_admin(current_user: Users = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user


@router.post("/login", response_model=user_schema.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user, error, dormant_user = user_crud.check_login_by_email(db, form_data.username, form_data.password)
    if dormant_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="dormant")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error)
    access_token = create_access_token(data={"sub": user.name})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=user_schema.UserResponse)
def get_me(current_user: Users = Depends(get_current_user)):
    return current_user


@router.post("/request", status_code=status.HTTP_204_NO_CONTENT)
def submit_account_request(body: user_schema.AccountRequestCreate, db: Session = Depends(get_db)):
    if db.query(Users).filter(Users.name == body.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken.")
    if db.query(Users).filter(Users.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use.")
    existing = db.query(AccountRequests).filter(
        AccountRequests.name == body.name,
        AccountRequests.status == "pending"
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A request with this username is already pending.")
    req = AccountRequests(
        name=body.name,
        email=body.email,
        passwd=passwd_context.hash(body.passwd1),
        message=body.message,
        status="pending"
    )
    db.add(req)
    db.commit()


@router.post("/settings/verify")
def verify_password_for_settings(
    body: user_schema.UserVerifyPassword,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user_crud.verify_password(db, current_user, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")
    return {"message": "Password verified."}


@router.patch("/settings/name")
def update_name(
    body: user_schema.UserUpdateName,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user_crud.verify_password(db, current_user, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")
    if db.query(Users).filter(Users.name == body.new_name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken.")
    user_crud.update_name(db, current_user, body.new_name)
    new_token = create_access_token(data={"sub": body.new_name})
    return {"message": "Username updated.", "access_token": new_token}


@router.patch("/settings/email")
def update_email(
    body: user_schema.UserUpdateEmail,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user_crud.verify_password(db, current_user, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")
    if db.query(Users).filter(Users.email == body.new_email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use.")
    user_crud.update_email(db, current_user, body.new_email)
    return {"message": "Email updated."}


@router.patch("/settings/password")
def update_password(
    body: user_schema.UserUpdatePassword,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user_crud.verify_password(db, current_user, body.current_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")
    user_crud.update_password(db, current_user, body.new_password)
    return {"message": "Password updated."}


@router.post("/settings/profile-image")
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only image files are allowed.")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    filename = f"{current_user.id}_profile.{ext}"
    file_path = os.path.join(PROFILE_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    user_crud.update_profile_image(db, current_user, file_path)
    return {"message": "Profile image updated.", "path": f"/api/user/profile-image/{current_user.id}"}


@router.delete("/settings/profile-image", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile_image(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.profile_image and os.path.exists(current_user.profile_image):
        os.remove(current_user.profile_image)
    user_crud.update_profile_image(db, current_user, None)


@router.get("/profile-image/{user_id}")
def get_profile_image(user_id: int, db: Session = Depends(get_db)):
    user = user_crud.get_user_by_id(db, user_id)
    if not user or not user.profile_image or not os.path.exists(user.profile_image):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile image not found.")
    return FileResponse(user.profile_image)


@router.delete("/settings/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: user_schema.UserDelete,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin account cannot be deleted this way.")
    if not user_crud.verify_password(db, current_user, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")
    user_crud.delete_user(db, current_user)


@router.get("/admin/users", response_model=list[user_schema.UserResponse])
def admin_get_users(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    return user_crud.get_all_users(db)


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete admin account.")
    user_crud.delete_user(db, user)


@router.patch("/admin/users/{user_id}/lock", status_code=status.HTTP_204_NO_CONTENT)
def admin_lock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot lock admin account.")
    user_crud.lock_user(db, user)


@router.patch("/admin/users/{user_id}/unlock", status_code=status.HTTP_204_NO_CONTENT)
def admin_unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user_crud.unlock_user(db, user)


@router.patch("/admin/users/{user_id}/dormant-unlock", status_code=status.HTTP_204_NO_CONTENT)
def admin_dormant_unlock(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user_crud.activate_dormant(db, user)


@router.patch("/admin/users/{user_id}/storage-limit")
def admin_set_storage_limit(
    user_id: int,
    limit_gb: float = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    limit_bytes = int(limit_gb * 1073741824) if limit_gb is not None else None
    user_crud.set_storage_limit(db, user, limit_bytes)
    return {"message": "Storage limit updated."}


@router.get("/admin/config")
def get_config(current_user: Users = Depends(require_admin)):
    from config import MAX_ACCOUNT
    return {"max_account": MAX_ACCOUNT}


@router.get("/admin/requests", response_model=list[user_schema.AccountRequestResponse])
def admin_get_requests(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    return db.query(AccountRequests).filter(
        AccountRequests.status == "pending"
    ).order_by(AccountRequests.created_at.desc()).all()


@router.post("/admin/requests/{req_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
def admin_approve_request(
    req_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    req = db.query(AccountRequests).filter(AccountRequests.id == req_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    if db.query(Users).filter(Users.name == req.name).first():
        req.status = "rejected"
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken. Request rejected.")
    if db.query(Users).filter(Users.email == req.email).first():
        req.status = "rejected"
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use. Request rejected.")

    from config import MAX_ACCOUNT, UPLOAD_DIR
    from datetime import datetime
    user_count = db.query(Users).filter(Users.is_admin == False).count()
    if user_count >= MAX_ACCOUNT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Max account limit ({MAX_ACCOUNT}) reached.")

    new_user = Users(
        name=req.name,
        passwd=req.passwd,
        email=req.email,
        is_admin=False
    )
    db.add(new_user)
    db.flush()

    date_str = datetime.now().strftime("%Y%m%d")
    dir_name = f"{new_user.id}_{new_user.name}_{date_str}"
    storage_path = os.path.join(UPLOAD_DIR, dir_name)
    os.makedirs(storage_path, exist_ok=True)
    new_user.storage_path = storage_path

    db.delete(req)
    db.commit()


@router.delete("/admin/requests/{req_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def admin_reject_request(
    req_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_admin)
):
    req = db.query(AccountRequests).filter(AccountRequests.id == req_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    db.delete(req)
    db.commit()
