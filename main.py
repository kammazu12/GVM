from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

import bcrypt
import secrets

# ---------------------------
# Config / DB setup
# ---------------------------
DATABASE_URL = "sqlite:///./app.db"  # dev: SQLite file; prod: switch to PostgreSQL URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ---------------------------
# Models
# ---------------------------
class Company(Base):
    __tablename__ = "companies"
    company_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    subscription_type = Column(String, nullable=True)
    country = Column(String, nullable=True)
    post_code = Column(String, nullable=True)
    address = Column(String, nullable=True)
    tax_number = Column(String, nullable=True)
    domestic_only = Column(Boolean, default=False)

    users = relationship("User", back_populates="company")
    invite_codes = relationship("InviteCode", back_populates="company")


class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    e_mail = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # e.g. carrier company / freight forwarder / consignor/consignee / admin / manager
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=True)
    is_company_admin = Column(Boolean, default=False)
    common_user = Column(Boolean, default=False)  # uses service occasionally or often
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="users")


class InviteCode(Base):
    __tablename__ = "invite_codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    role = Column(String, nullable=False)  # intended role for the invite
    expires_at = Column(DateTime, nullable=True)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="invite_codes")


Base.metadata.create_all(bind=engine)

# ---------------------------
# FastAPI app & templates
# ---------------------------
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(32))

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# ---------------------------
# Helpers / Dependencies
# ---------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def validate_password(password: str) -> bool:
    return (
        len(password) >= 8
        and any(c.islower() for c in password)
        and any(c.isupper() for c in password)
        and any(c.isdigit() for c in password)
    )

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def generate_invite_code(length: int = 10) -> str:
    return secrets.token_urlsafe(length)[:length]

# ---------------------------
# Routes
# ---------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    session = request.session
    user_id = session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    company = None
    if user.company:
        company = user.company

    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "company": company
    })


@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    # show registration form; it contains option to create company or join via invite code
    return templates.TemplateResponse("register.html", {"request": request, "message": ""})


@app.post("/register", response_class=HTMLResponse)
def register_post(
    request: Request,
    e_mail: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    action: str = Form(...),  # "create" or "join"
    # fields for create
    company_name: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    post_code: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    tax_number: Optional[str] = Form(None),
    subscription_type: Optional[str] = Form(None),
    # fields for join
    invite_code: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Basic checks
    e_mail = e_mail.strip().lower()
    if db.query(User).filter(User.e_mail == e_mail).first():
        return templates.TemplateResponse("register.html", {"request": request, "message": "E-mail already registered."})

    if password != confirm_password:
        return templates.TemplateResponse("register.html", {"request": request, "message": "Passwords do not match."})

    if not validate_password(password):
        return templates.TemplateResponse("register.html", {"request": request, "message": "Password must be minimum 8 chars, include upper & lower case letters and a number."})

    # CREATE new company flow
    if action == "create":
        if not company_name or company_name.strip() == "":
            return templates.TemplateResponse("register.html", {"request": request, "message": "Company name is required to create a new company."})

        # Ensure unique company name
        if db.query(Company).filter(Company.name == company_name.strip()).first():
            return templates.TemplateResponse("register.html", {"request": request, "message": "Company name already exists."})

        company = Company(
            name=company_name.strip(),
            subscription_type=subscription_type,
            country=country,
            post_code=post_code,
            address=address,
            tax_number=tax_number
        )
        db.add(company)
        db.commit()
        db.refresh(company)

        # create admin user for company
        user = User(
            e_mail=e_mail,
            hashed_password=hash_password(password),
            role="company_admin",
            company_id=company.company_id,
            is_company_admin=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Optionally: create an initial invite code for company admins or staff
        # invite = InviteCode(code=generate_invite_code(), company_id=company.company_id, role="freight forwarder", expires_at=datetime.utcnow() + timedelta(days=7))
        # db.add(invite); db.commit()

        # Set session and redirect to home
        request.session["user_id"] = user.user_id
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    # JOIN company via invite code flow
    elif action == "join":
        if not invite_code or invite_code.strip() == "":
            return templates.TemplateResponse("register.html", {"request": request, "message": "Invite code is required to join an existing company."})

        code = invite_code.strip()
        inv: Optional[InviteCode] = db.query(InviteCode).filter(InviteCode.code == code).first()
        if not inv:
            return templates.TemplateResponse("register.html", {"request": request, "message": "Invalid invite code."})
        if inv.is_used:
            return templates.TemplateResponse("register.html", {"request": request, "message": "Invite code already used."})
        if inv.expires_at and inv.expires_at < datetime.utcnow():
            return templates.TemplateResponse("register.html", {"request": request, "message": "Invite code expired."})

        # create user linked to company with the role specified by invite
        user = User(
            e_mail=e_mail,
            hashed_password=hash_password(password),
            role=inv.role,
            company_id=inv.company_id,
            is_company_admin=False
        )
        db.add(user)
        # mark invite used
        inv.is_used = True
        db.commit()
        db.refresh(user)

        # auto-login
        request.session["user_id"] = user.user_id
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    else:
        return templates.TemplateResponse("register.html", {"request": request, "message": "Unknown action."})


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "message": ""})


@app.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    e_mail: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    e_mail = e_mail.strip().lower()
    user = db.query(User).filter(User.e_mail == e_mail).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "message": "Invalid email or password."})

    # set session
    request.session["user_id"] = user.user_id
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


# Admin-like route to generate invite codes (for demo/testing).
# In production restrict access to company admins only.
@app.post("/generate_invite", response_class=HTMLResponse)
def generate_invite(
    request: Request,
    company_id: int = Form(...),
    role: str = Form(...),
    days_valid: int = Form(7),
    db: Session = Depends(get_db)
):
    # create invite
    code = generate_invite_code(12)
    expires_at = datetime.utcnow() + timedelta(days=days_valid)
    inv = InviteCode(code=code, company_id=company_id, role=role, expires_at=expires_at)
    db.add(inv)
    db.commit()
    return templates.TemplateResponse("invite_created.html", {"request": request, "code": code, "company_id": company_id, "role": role, "expires_at": expires_at})
