"""JWT 鉴权接口"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============ 常量和配置 ============
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = settings.JWT_SECRET_KEY.get_secret_value()
JWT_EXPIRATION_HOURS = 24


# ============ 数据模型 ============
class LoginRequest(BaseModel):
    """登录请求模型"""

    username: str = Field(min_length=3, max_length=50, description="用户名")
    password: str = Field(min_length=6, max_length=100, description="密码")


class LoginResponse(BaseModel):
    """登录响应模型"""

    access_token: str = Field(description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="过期时间（秒）")


class TokenPayload(BaseModel):
    """JWT 令牌负载"""

    sub: str = Field(description="用户标识")
    exp: int = Field(description="过期时间戳")
    iat: int = Field(description="发放时间戳")
    username: str = Field(description="用户名")


class CurrentUserInfo(BaseModel):
    """当前用户信息"""

    username: str = Field(description="用户名")
    user_id: str = Field(description="用户ID")


class VerifyTokenResponse(BaseModel):
    """验证令牌响应模型"""

    valid: bool = Field(description="令牌是否有效")
    username: str = Field(description="用户名")
    user_id: str = Field(description="用户ID")
    message: str = Field(description="验证消息")


# ============ 工具函数 ============
def _create_jwt_token(username: str, user_id: str | None = None, hours: int = JWT_EXPIRATION_HOURS) -> tuple[str, int]:
    """
    创建 JWT 令牌

    Args:
        username: 用户名
        user_id: 用户 ID（可选，默认与 username 相同）
        hours: 过期时间（小时）

    Returns:
        (token, expires_in): 令牌和过期时间（秒）
    """
    if user_id is None:
        user_id = username

    now = datetime.now(UTC)
    expire = now + timedelta(hours=hours)

    payload = {
        "sub": user_id,
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    expires_in = int((expire - now).total_seconds())

    return token, expires_in


def _verify_jwt_token(token: str) -> TokenPayload:
    """
    验证 JWT 令牌

    Args:
        token: JWT 令牌

    Returns:
        TokenPayload: 令牌负载

    Raises:
        HTTPException: 令牌无效或过期
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return TokenPayload.model_validate(payload)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌验证失败",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌负载无效",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def _extract_token(authorization: str | None = Header(default=None)) -> str:
    """
    从请求头中提取 JWT 令牌

    Args:
        authorization: Authorization 请求头值

    Returns:
        str: JWT 令牌

    Raises:
        HTTPException: 缺少或格式错误的 Authorization 请求头
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization 请求头",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Authorization 请求头格式，应为 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return parts[1]


async def get_current_user(token: str = Depends(_extract_token)) -> CurrentUserInfo:
    """
    获取当前用户信息（依赖注入函数）

    用于在路由中作为依赖注入，自动验证 JWT 令牌并获取用户信息

    Example:
        @router.get("/profile")
        async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
            return {"username": current_user.username}

    Args:
        token: 从请求头中自动提取的 JWT 令牌

    Returns:
        CurrentUser: 当前用户信息

    Raises:
        HTTPException: 令牌无效或过期
    """
    token_payload = _verify_jwt_token(token)
    return CurrentUserInfo(username=token_payload.username, user_id=token_payload.sub)


CurrentUser = Annotated[CurrentUserInfo, Depends(get_current_user)]


def RequiresLogin() -> Any:  # noqa: N802
    async def _requires_login(token: str = Depends(_extract_token)) -> None:
        _verify_jwt_token(token)

    return Depends(_requires_login)


# ============ 路由处理程序 ============
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """
    用户登录接口

    此接口接收用户名和密码，验证身份后返回 JWT 令牌。

    Args:
        request: 包含用户名和密码的登录请求

    Returns:
        LoginResponse: 包含 JWT 令牌的响应

    Raises:
        HTTPException: 凭证无效
    """
    if request.username != settings.ADMIN_USERNAME or request.password != settings.ADMIN_PASSWORD.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 创建 JWT 令牌
    token, expires_in = _create_jwt_token(username=request.username, user_id=request.username)

    return LoginResponse(
        access_token=token,
        token_type="bearer",  # noqa: S106
        expires_in=expires_in,
    )


@router.post("/verify", response_model=VerifyTokenResponse)
async def verify_token(current_user: CurrentUser) -> VerifyTokenResponse:
    """
    验证 JWT 令牌有效性

    此端点用于验证提供的 JWT 令牌是否有效。
    自动从 Authorization 请求头中提取并验证令牌。

    Args:
        current_user: 通过 JWT 令牌验证得到的当前用户

    Returns:
        包含验证结果和用户信息的字典
    """
    return VerifyTokenResponse(
        valid=True,
        username=current_user.username,
        user_id=current_user.user_id,
        message="令牌有效",
    )


@router.get("/me")
async def get_me(current_user: CurrentUser) -> CurrentUserInfo:
    """
    获取当前用户信息

    此端点返回当前认证用户的信息。

    Args:
        current_user: 通过 JWT 令牌验证得到的当前用户

    Returns:
        CurrentUser: 当前用户信息
    """
    return current_user
