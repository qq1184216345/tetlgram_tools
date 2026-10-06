"""纸翼授权云服务 — FastAPI + SQLAlchemy."""
from __future__ import annotations

import json
import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Generator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ROOT.parent
PORTS_FILE = PROJECT_ROOT / "config" / "ports.json"
try:
    PORTS = json.loads(PORTS_FILE.read_text(encoding="utf-8"))
except Exception:
    PORTS = {
        "license": {"host": "127.0.0.1", "port": 28180},
        "postgres": {"host": "127.0.0.1", "port": 25432},
    }

DATA_DIR = Path(os.environ.get("LICENSE_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_email(email: str) -> str:
    value = (email or "").strip().lower()
    if "@" not in value or len(value) < 5:
        raise ValueError("邮箱格式不正确")
    return value


def _default_database_url() -> str:
    pg = PORTS.get("postgres") or {}
    host = pg.get("host") or "127.0.0.1"
    port = int(pg.get("port") or 25432)
    return f"postgresql+psycopg://paperwing:paperwing@{host}:{port}/paperwing_license"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 监听地址默认全网卡，便于上云；端口来自 config/ports.json
    host: str = "0.0.0.0"
    port: int = int((PORTS.get("license") or {}).get("port") or 28180)
    # 默认 PostgreSQL；本地可用 docker compose 起库，或用环境变量覆盖
    database_url: str = Field(default_factory=_default_database_url)
    jwt_secret: str = Field(default_factory=lambda: secrets.token_hex(32))
    admin_email: str = "nb@zhiyinb.cc"
    admin_password: str = "xmm123456"
    token_ttl_days: int = 30
    heartbeat_grace_minutes: int = 30

    smtp_host: str = "mail.spacemail.com"
    smtp_port: int = 465
    smtp_user: str = "nb@zhiyinb.cc"
    smtp_password: str = ""
    smtp_from: str = "nb@zhiyinb.cc"
    imap_host: str = "mail.spacemail.com"
    imap_port: int = 993
    email_code_ttl_minutes: int = 10
    email_code_cooldown_seconds: int = 60


settings = Settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active|banned
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")
    cards: Mapped[list["LicenseCard"]] = relationship(back_populates="used_by")


class LicenseCard(Base):
    __tablename__ = "license_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    duration_days: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="unused")  # unused|used|revoked
    batch_note: Mapped[str] = mapped_column(String(255), default="")
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    used_by: Mapped[User | None] = relationship(back_populates="cards")


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    device_label: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(255), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class EmailCode(Base):
    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    purpose: Mapped[str] = mapped_column(String(32))  # register | reset
    code: Mapped[str] = mapped_column(String(16))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AppVersionConfig(Base):
    """桌面端更新清单（单行配置，id 固定为 1）。"""

    __tablename__ = "app_version_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    download_url: Mapped[str] = mapped_column(String(1024), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    force_update: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_by: Mapped[str] = mapped_column(String(255), default="")


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Annotated[Session, Depends(get_db)]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def generate_card_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    parts = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)]
    return "PW-" + "-".join(parts)


def audit(db: Session, action: str, actor: str, detail: str = "") -> None:
    db.add(AuditLog(action=action, actor=actor, detail=detail))


def _gen_email_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _consume_email_code(db: Session, email: str, purpose: str, code: str) -> None:
    now = _utcnow()
    row = db.scalars(
        select(EmailCode)
        .where(
            EmailCode.email == email,
            EmailCode.purpose == purpose,
            EmailCode.code == code.strip(),
            EmailCode.used.is_(False),
        )
        .order_by(EmailCode.id.desc())
    ).first()
    if not row:
        raise HTTPException(status_code=400, detail="验证码错误")
    if row.expires_at <= now:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    row.used = True


def _send_code_mail(email: str, purpose: str, code: str) -> None:
    if not settings.smtp_password:
        raise HTTPException(status_code=500, detail="邮件服务未配置 SMTP_PASSWORD")
    if purpose == "register":
        subject = "纸翼 — 注册验证码"
        body = (
            f"您正在注册纸翼账号。\n\n验证码：{code}\n\n"
            f"{settings.email_code_ttl_minutes} 分钟内有效，如非本人操作请忽略。"
        )
    else:
        subject = "纸翼 — 修改/找回密码验证码"
        body = (
            f"您正在修改或重置纸翼账号密码。\n\n验证码：{code}\n\n"
            f"{settings.email_code_ttl_minutes} 分钟内有效，如非本人操作请忽略。"
        )
    from license_server.mailer import send_email

    try:
        send_email(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            mail_from=settings.smtp_from or settings.smtp_user,
            mail_to=email,
            subject=subject,
            body=body,
            use_ssl=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"验证码发送失败: {exc}") from exc


def user_licensed(user: User) -> bool:
    if user.status == "banned":
        return False
    if not user.expires_at:
        return False
    return user.expires_at > _utcnow()


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
        "status": user.status,
        "expires_at": user.expires_at.isoformat() + "Z" if user.expires_at else None,
        "licensed": user_licensed(user),
        "created_at": user.created_at.isoformat() + "Z" if user.created_at else None,
    }


def create_session(db: Session, user: User, device_label: str = "") -> UserSession:
    # 单点：撤销旧会话
    now = _utcnow()
    old = db.scalars(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        )
    ).all()
    for s in old:
        s.revoked_at = now
    if old:
        audit(db, "kick_session", user.email, f"revoked {len(old)} old session(s)")

    token = secrets.token_urlsafe(48)
    session = UserSession(
        user_id=user.id,
        session_token=token,
        device_label=device_label[:200],
        created_at=now,
        last_seen_at=now,
    )
    db.add(session)
    return session


def get_session_user(
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> tuple[User, UserSession]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ", 1)[1].strip()
    session = db.scalars(
        select(UserSession).where(UserSession.session_token == token)
    ).first()
    if not session:
        raise HTTPException(status_code=401, detail="会话无效")
    if session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="kicked", headers={"X-License-Status": "kicked"})
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status == "banned":
        raise HTTPException(status_code=403, detail="账号已被封禁")
    return user, session


AuthUser = Annotated[tuple[User, UserSession], Depends(get_session_user)]


def require_admin(auth: AuthUser) -> tuple[User, UserSession]:
    user, session = auth
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user, session


AdminUser = Annotated[tuple[User, UserSession], Depends(require_admin)]

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    email_code: str = Field(min_length=4, max_length=16)
    device_label: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str
    device_label: str = ""


class SendEmailCodeRequest(BaseModel):
    email: str
    purpose: str = "register"  # register | reset


class ResetPasswordRequest(BaseModel):
    email: str
    email_code: str = Field(min_length=4, max_length=16)
    new_password: str = Field(min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)
    old_password: str | None = None
    email_code: str | None = None


class UpdateAppVersionRequest(BaseModel):
    version: str = Field(min_length=1, max_length=32)
    download_url: str = Field(default="", max_length=1024)
    notes: str = Field(default="", max_length=4000)
    force_update: bool = False


class RedeemRequest(BaseModel):
    code: str


class HeartbeatRequest(BaseModel):
    device_label: str = ""


class GenerateCardsRequest(BaseModel):
    duration_days: int = Field(ge=1, le=3650)
    count: int = Field(ge=1, le=500)
    batch_note: str = ""


class ExtendUserRequest(BaseModel):
    days: int = Field(ge=-3650, le=3650)
    expires_at: str | None = None  # ISO, optional absolute


class BanUserRequest(BaseModel):
    banned: bool = True


class RevokeCardRequest(BaseModel):
    pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="纸翼授权服务", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_app_version(row: AppVersionConfig) -> dict:
    return {
        "version": row.version,
        "url": row.download_url or "",
        "download_url": row.download_url or "",
        "notes": row.notes or "",
        "force": bool(row.force_update),
        "force_update": bool(row.force_update),
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
        "updated_by": row.updated_by or "",
    }


def get_or_create_app_version(db: Session) -> AppVersionConfig:
    row = db.get(AppVersionConfig, 1)
    if row:
        return row
    row = AppVersionConfig(
        id=1,
        version="0.1.0",
        download_url="",
        notes="初始版本",
        force_update=False,
        updated_at=_utcnow(),
        updated_by="system",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        email = _normalize_email(settings.admin_email)
        admin = db.scalars(select(User).where(User.email == email)).first()
        if not admin:
            legacy = db.scalars(
                select(User).where(User.email == "admin@paperwing.com")
            ).first()
            if legacy:
                legacy.email = email
                admin = legacy
                audit(db, "seed_admin", email, "migrated legacy admin email")
            else:
                admin = User(
                    email=email,
                    password_hash=hash_password(settings.admin_password),
                    is_admin=True,
                    status="active",
                    expires_at=_utcnow() + timedelta(days=3650),
                )
                db.add(admin)
                audit(db, "seed_admin", email, "created seed admin")
        admin.password_hash = hash_password(settings.admin_password)
        admin.is_admin = True
        admin.status = "active"
        if not admin.expires_at or admin.expires_at < _utcnow():
            admin.expires_at = _utcnow() + timedelta(days=3650)
        db.commit()
        get_or_create_app_version(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "paperwing-license"}


# ---- Auth ----


@app.post("/auth/send-code")
def send_email_code(payload: SendEmailCodeRequest, db: DbDep) -> dict:
    try:
        email = _normalize_email(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    purpose = (payload.purpose or "register").strip().lower()
    if purpose not in {"register", "reset"}:
        raise HTTPException(status_code=400, detail="purpose 仅支持 register 或 reset")

    exists = db.scalars(select(User).where(User.email == email)).first()
    if purpose == "register" and exists:
        raise HTTPException(status_code=400, detail="邮箱已注册")
    if purpose == "reset" and not exists:
        raise HTTPException(status_code=400, detail="该邮箱未注册")

    now = _utcnow()
    latest = db.scalars(
        select(EmailCode)
        .where(EmailCode.email == email, EmailCode.purpose == purpose)
        .order_by(EmailCode.id.desc())
    ).first()
    if latest and (now - latest.created_at).total_seconds() < settings.email_code_cooldown_seconds:
        wait = settings.email_code_cooldown_seconds - int((now - latest.created_at).total_seconds())
        raise HTTPException(status_code=429, detail=f"发送过于频繁，请 {wait} 秒后再试")

    code = _gen_email_code()
    db.add(
        EmailCode(
            email=email,
            purpose=purpose,
            code=code,
            used=False,
            created_at=now,
            expires_at=now + timedelta(minutes=settings.email_code_ttl_minutes),
        )
    )
    db.commit()
    _send_code_mail(email, purpose, code)
    audit(db, "send_email_code", email, purpose)
    db.commit()
    return {
        "success": True,
        "message": "验证码已发送，请查收邮箱",
        "cooldown_seconds": settings.email_code_cooldown_seconds,
        "ttl_minutes": settings.email_code_ttl_minutes,
    }


@app.post("/auth/register")
def register(payload: RegisterRequest, db: DbDep) -> dict:
    try:
        email = _normalize_email(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=400, detail="邮箱已注册")
    _consume_email_code(db, email, "register", payload.email_code)
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        is_admin=False,
        status="active",
        expires_at=None,
    )
    db.add(user)
    db.flush()
    session = create_session(db, user, payload.device_label)
    audit(db, "register", email, "email_code_ok")
    db.commit()
    return {
        "access_token": session.session_token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@app.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest, db: DbDep) -> dict:
    try:
        email = _normalize_email(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = db.scalars(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=400, detail="该邮箱未注册")
    if user.status == "banned":
        raise HTTPException(status_code=403, detail="账号已被封禁")
    _consume_email_code(db, email, "reset", payload.email_code)
    user.password_hash = hash_password(payload.new_password)
    # 重置密码后踢掉所有会话
    now = _utcnow()
    for s in db.scalars(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        )
    ).all():
        s.revoked_at = now
    audit(db, "reset_password", email, "")
    db.commit()
    return {"success": True, "message": "密码已重置，请使用新密码登录"}


@app.post("/auth/change-password")
def change_password(payload: ChangePasswordRequest, auth: AuthUser, db: DbDep) -> dict:
    user, _ = auth
    old_password = (payload.old_password or "").strip()
    email_code = (payload.email_code or "").strip()
    if bool(old_password) == bool(email_code):
        raise HTTPException(status_code=400, detail="请选择当前密码或邮箱验证码其中一种方式")

    if old_password:
        if not verify_password(old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="当前密码不正确")
        if old_password == payload.new_password:
            raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
        method = "old_password"
    else:
        _consume_email_code(db, user.email, "reset", email_code)
        method = "email_code"

    user.password_hash = hash_password(payload.new_password)
    audit(db, "change_password", user.email, method)
    db.commit()
    return {"success": True, "message": "密码已修改"}


@app.post("/auth/login")
def login(payload: LoginRequest, db: DbDep) -> dict:
    try:
        email = _normalize_email(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = db.scalars(select(User).where(User.email == email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    if user.status == "banned":
        raise HTTPException(status_code=403, detail="账号已被封禁")
    session = create_session(db, user, payload.device_label)
    audit(db, "login", email, payload.device_label)
    db.commit()
    return {
        "access_token": session.session_token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@app.post("/auth/logout")
def logout(auth: AuthUser, db: DbDep) -> dict:
    user, session = auth
    session.revoked_at = _utcnow()
    audit(db, "logout", user.email, "")
    db.commit()
    return {"success": True}


@app.get("/auth/me")
def me(auth: AuthUser) -> dict:
    user, _ = auth
    return serialize_user(user)


@app.post("/auth/heartbeat")
def heartbeat(payload: HeartbeatRequest, auth: AuthUser, db: DbDep) -> dict:
    user, session = auth
    session.last_seen_at = _utcnow()
    if payload.device_label:
        session.device_label = payload.device_label[:200]
    db.commit()
    return {
        "ok": True,
        "kicked": False,
        "user": serialize_user(user),
    }


# ---- License ----


@app.post("/license/redeem")
def redeem(payload: RedeemRequest, auth: AuthUser, db: DbDep) -> dict:
    user, _ = auth
    code = payload.code.strip().upper()
    card = db.scalars(select(LicenseCard).where(LicenseCard.code == code)).first()
    if not card:
        raise HTTPException(status_code=400, detail="卡密无效")
    if card.status == "revoked":
        raise HTTPException(status_code=400, detail="卡密已作废")
    if card.status == "used":
        raise HTTPException(status_code=400, detail="卡密已被使用")

    now = _utcnow()
    base = user.expires_at if user.expires_at and user.expires_at > now else now
    user.expires_at = base + timedelta(days=card.duration_days)
    card.status = "used"
    card.used_by_user_id = user.id
    card.used_at = now
    audit(
        db,
        "redeem",
        user.email,
        f"code={code} days={card.duration_days} expires={user.expires_at.isoformat()}",
    )
    db.commit()
    return {"success": True, "user": serialize_user(user)}


@app.post("/license/verify")
def verify_license(auth: AuthUser) -> dict:
    """供本地 backend / 桌面校验。"""
    user, session = auth
    return {
        "ok": True,
        "kicked": False,
        "licensed": user_licensed(user),
        "user": serialize_user(user),
        "session_id": session.id,
    }


# ---- Admin ----


@app.post("/admin/cards/generate")
def admin_generate_cards(payload: GenerateCardsRequest, admin: AdminUser, db: DbDep) -> dict:
    actor, _ = admin
    codes: list[str] = []
    for _ in range(payload.count):
        for _try in range(20):
            code = generate_card_code()
            if not db.scalars(select(LicenseCard).where(LicenseCard.code == code)).first():
                break
        else:
            raise HTTPException(status_code=500, detail="生成卡密冲突，请重试")
        db.add(
            LicenseCard(
                code=code,
                duration_days=payload.duration_days,
                status="unused",
                batch_note=payload.batch_note[:200],
            )
        )
        codes.append(code)
    audit(
        db,
        "generate_cards",
        actor.email,
        f"count={payload.count} days={payload.duration_days} note={payload.batch_note}",
    )
    db.commit()
    return {"success": True, "codes": codes, "count": len(codes)}


@app.get("/admin/cards")
def admin_list_cards(
    admin: AdminUser,
    db: DbDep,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    _ = admin
    q = select(LicenseCard).order_by(LicenseCard.id.desc())
    if status:
        q = q.where(LicenseCard.status == status)
    rows = db.scalars(q.offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "id": c.id,
                "code": c.code,
                "duration_days": c.duration_days,
                "status": c.status,
                "batch_note": c.batch_note,
                "used_by_user_id": c.used_by_user_id,
                "used_at": c.used_at.isoformat() + "Z" if c.used_at else None,
                "created_at": c.created_at.isoformat() + "Z" if c.created_at else None,
            }
            for c in rows
        ]
    }


@app.post("/admin/cards/{card_id}/revoke")
def admin_revoke_card(card_id: int, admin: AdminUser, db: DbDep) -> dict:
    actor, _ = admin
    card = db.get(LicenseCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="卡密不存在")
    if card.status == "used":
        raise HTTPException(status_code=400, detail="已使用的卡密不能作废")
    card.status = "revoked"
    audit(db, "revoke_card", actor.email, card.code)
    db.commit()
    return {"success": True}


@app.get("/admin/users")
def admin_list_users(
    admin: AdminUser,
    db: DbDep,
    q: str = "",
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    _ = admin
    stmt = select(User).order_by(User.id.desc())
    if q.strip():
        stmt = stmt.where(User.email.contains(q.strip().lower()))
    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return {"items": [serialize_user(u) for u in rows]}


@app.post("/admin/users/{user_id}/ban")
def admin_ban_user(user_id: int, payload: BanUserRequest, admin: AdminUser, db: DbDep) -> dict:
    actor, _ = admin
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="不能封禁管理员")
    user.status = "banned" if payload.banned else "active"
    if payload.banned:
        now = _utcnow()
        for s in db.scalars(
            select(UserSession).where(
                UserSession.user_id == user.id,
                UserSession.revoked_at.is_(None),
            )
        ).all():
            s.revoked_at = now
    audit(db, "ban" if payload.banned else "unban", actor.email, user.email)
    db.commit()
    return {"success": True, "user": serialize_user(user)}


@app.post("/admin/users/{user_id}/extend")
def admin_extend_user(user_id: int, payload: ExtendUserRequest, admin: AdminUser, db: DbDep) -> dict:
    actor, _ = admin
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    now = _utcnow()
    if payload.expires_at:
        raw = payload.expires_at.replace("Z", "")
        user.expires_at = datetime.fromisoformat(raw)
    else:
        base = user.expires_at if user.expires_at and user.expires_at > now else now
        user.expires_at = base + timedelta(days=payload.days)
    audit(
        db,
        "extend",
        actor.email,
        f"{user.email} -> {user.expires_at.isoformat() if user.expires_at else None}",
    )
    db.commit()
    return {"success": True, "user": serialize_user(user)}


@app.get("/admin/audit")
def admin_audit(
    admin: AdminUser,
    db: DbDep,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    _ = admin
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": a.id,
                "action": a.action,
                "actor": a.actor,
                "detail": a.detail,
                "created_at": a.created_at.isoformat() + "Z" if a.created_at else None,
            }
            for a in rows
        ]
    }


# ---- App version (desktop update manifest) ----


@app.get("/app/version")
def public_app_version(db: DbDep) -> dict:
    """桌面端 / 官网公开拉取的更新清单（无需登录）。"""
    return serialize_app_version(get_or_create_app_version(db))


@app.get("/admin/app-version")
def admin_get_app_version(admin: AdminUser, db: DbDep) -> dict:
    _ = admin
    return serialize_app_version(get_or_create_app_version(db))


@app.put("/admin/app-version")
def admin_put_app_version(payload: UpdateAppVersionRequest, admin: AdminUser, db: DbDep) -> dict:
    actor, _ = admin
    version = payload.version.strip()
    if not version:
        raise HTTPException(status_code=400, detail="版本号不能为空")
    row = get_or_create_app_version(db)
    row.version = version[:32]
    row.download_url = (payload.download_url or "").strip()[:1024]
    row.notes = (payload.notes or "").strip()[:4000]
    row.force_update = bool(payload.force_update)
    row.updated_at = _utcnow()
    row.updated_by = actor.email
    audit(
        db,
        "update_app_version",
        actor.email,
        f"version={row.version} force={row.force_update} url={row.download_url[:80]}",
    )
    db.commit()
    db.refresh(row)
    return {"success": True, "item": serialize_app_version(row)}


# ---- Public website + admin static UI ----

WEBSITE_DIR = PROJECT_ROOT / "website"
WEBSITE_ASSETS = WEBSITE_DIR / "assets"
ADMIN_DIR = ROOT / "admin"


@app.get("/")
def public_website() -> FileResponse:
    index = WEBSITE_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="官网未部署")
    return FileResponse(index)


if WEBSITE_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=WEBSITE_ASSETS), name="website-assets")

WEBSITE_DOWNLOADS = WEBSITE_DIR / "downloads"
WEBSITE_DOWNLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=WEBSITE_DOWNLOADS), name="website-downloads")

if ADMIN_DIR.exists():
    app.mount("/admin/assets", StaticFiles(directory=ADMIN_DIR / "assets"), name="admin-assets")


@app.get("/admin")
@app.get("/admin/")
def admin_index() -> FileResponse:
    index = ADMIN_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="管理后台未部署")
    return FileResponse(index)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "license_server.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
