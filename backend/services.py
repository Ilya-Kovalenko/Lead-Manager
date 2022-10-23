import database as _database
import fastapi as _fastapi
import fastapi.security as _security
import sqlalchemy.orm as _orm
import models as _models
import schemas as _schemas
import passlib.hash as _hash
import jwt as _jwt
import datetime as _dt

oauth2schema = _security.OAuth2PasswordBearer(tokenUrl="/api/token")

JWT_SECRET = "myjwtsecret"  # нужно до конца разобраться с этим и хранить jwt_secret как переменную окружения


def create_database():
    return _database.Base.metadata.create_all(bind=_database.engine)


def get_db():
    db = _database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_user_by_email(email: str, db: _orm.Session):
    return db.query(_models.User).filter(_models.User.email == email).first()


async def create_user(user: _schemas.UserCreate, db: _orm.Session) -> _models.User:
    user_obj = _models.User(email=user.email, hashed_password=_hash.bcrypt.hash(user.hashed_password))
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)
    return user_obj


async def authenticate_user(email: str, password: str, db: _orm.Session) -> bool | _models.User:
    user = await get_user_by_email(email, db)
    if not user:
        return False

    if not user.verify_password(password):
        return False

    return user


async def create_token(user: _models.User):
    user_obj = _schemas.User.from_orm(user)  # создает оьъект _schemas.User и заполняет в нём поля в соответствии с объектом _models.User, который получает на вход

    token = _jwt.encode(user_obj.dict(), JWT_SECRET)

    return dict(access_token=token, token_type="bearer")


async def get_current_user(db: _orm.Session = _fastapi.Depends(get_db), token: str = _fastapi.Depends(oauth2schema)):
    try:
        payload = _jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user = db.query(_models.User).get(payload["id"])
    except:
        raise _fastapi.HTTPException(status_code=401, detail="Invalid Email or Password")

    return _schemas.User.from_orm(user)


async def create_lead(user: _schemas.User, db: _orm.Session, lead: _schemas.LeadCreate):
    lead_obj = _models.Lead(**lead.dict(), owner_id=user.id)  # ** производит распаковку lead_schema и делает lead.email = lead_schema.email, lead.first_name = lead_schema.first_name и тд
    db.add(lead_obj)
    db.commit()
    db.refresh(lead_obj)
    return _schemas.Lead.from_orm(lead_obj)


async def get_leads(user: _schemas.User, db: _orm.Session):
    leads = db.query(_models.Lead).filter_by(owner_id=user.id)

    return list(map(_schemas.Lead.from_orm, leads))


async def _lead_selector(lead_id: int, user: _schemas.User, db: _orm.Session):
    lead = db.query(_models.Lead)\
        .filter_by(owner_id=user.id)\
        .filter(_models.Lead.id == lead_id)\
        .first()

    if lead is None:
        raise _fastapi.HTTPException(status_code=404, detail=f"Lead id={lead_id} does not exist")

    return lead


async def get_lead(lead_id: int, user: _schemas.User, db: _orm.Session):
    lead = await _lead_selector(lead_id=lead_id, user=user, db=db)

    return _schemas.Lead.from_orm(lead)


async def delete_lead(lead_id: int, user: _schemas.User, db: _orm.Session):
    lead = await _lead_selector(lead_id=lead_id, user=user, db=db)
    db.delete(lead)
    db.commit()

    return {"message": "Successfully Deleted"}


async def update_lead(lead_id: int, lead: _schemas.LeadCreate, user: _schemas.User, db: _orm.Session):
    lead_db = await _lead_selector(lead_id=lead_id, user=user, db=db)

    lead_db.first_name = lead.first_name
    lead_db.last_name = lead.last_name
    lead_db.email = lead.email
    lead_db.company = lead.company
    lead_db.note = lead.note
    lead_db.date_last_updated = _dt.datetime.now()

    db.commit()
    db.refresh(lead_db)

    return _schemas.Lead.from_orm(lead_db)
