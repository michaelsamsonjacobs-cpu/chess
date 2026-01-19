from datetime import datetime
from pydantic import BaseModel, ConfigDict


class GameBase(BaseModel):
    opponent: str
    result: str
    moves: str | None = None


class GameCreate(GameBase):
    pass


class GameRead(GameBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileBase(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    rating: int | None = None


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileRead(UserProfileBase):
    id: int
    user_id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
