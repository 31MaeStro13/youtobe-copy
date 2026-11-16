"""
Comments API — CRUD комментариев, лайки комментариев.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.src.database import get_db
from backend.src.models.comment import Comment
from backend.src.models.like import CommentLike
from backend.src.models.user import User
from backend.src.schemas.comment import CommentCreate, CommentOut
from backend.src.services.video_service import get_video_by_id
from backend.src.api.v1.deps import get_current_user, get_current_user_optional

router = APIRouter(prefix="/videos/{video_id}/comments", tags=["comments"])


@router.get("/", response_model=list[CommentOut])
async def list_comments(
    video_id: int,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Возвращает корневые комментарии (parent_id=None) с проверкой доступа к видео."""
    video = await get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404, "Видео не найдено или доступ запрещён")
    result = await session.execute(
        select(Comment)
        .where(Comment.video_id == video_id, Comment.parent_id == None, Comment.is_hidden == False)
        .options(joinedload(Comment.user))
        .order_by(Comment.created_at.desc())
    )
    comments = result.scalars().all()

    # Считаем replies за 1 запрос вместо N
    comment_ids = [c.id for c in comments]
    replies_count_map: dict[int, int] = {}
    if comment_ids:
        from sqlalchemy import func
        rows = await session.execute(
            select(Comment.parent_id, func.count(Comment.id))
            .where(Comment.parent_id.in_(comment_ids))
            .group_by(Comment.parent_id)
        )
        replies_count_map = {row[0]: row[1] for row in rows}

    return [
        CommentOut(
            id=c.id,
            video_id=c.video_id,
            user_id=c.user_id,
            parent_id=c.parent_id,
            text=c.text,
            likes_count=c.likes_count,
            is_hidden=c.is_hidden,
            created_at=c.created_at,
            author_username=c.user.username,
            author_avatar=c.user.avatar_url,
            replies_count=replies_count_map.get(c.id, 0),
        )
        for c in comments
    ]


@router.get("/{comment_id}/replies", response_model=list[CommentOut])
async def list_replies(
    video_id: int,
    comment_id: int,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    video = await get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404, "Видео не найдено или доступ запрещён")
    result = await session.execute(
        select(Comment)
        .where(Comment.parent_id == comment_id, Comment.is_hidden == False)
        .options(joinedload(Comment.user))
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    return [
        CommentOut(
            id=c.id, video_id=c.video_id, user_id=c.user_id, parent_id=c.parent_id,
            text=c.text, likes_count=c.likes_count, is_hidden=c.is_hidden,
            created_at=c.created_at,
            author_username=c.user.username, author_avatar=c.user.avatar_url,
        )
        for c in comments
    ]


@router.post("/", response_model=CommentOut, status_code=201)
async def add_comment(
    video_id: int,
    data: CommentCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = await get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404)

    if data.parent_id:
        parent = await session.get(Comment, data.parent_id)
        if not parent or parent.video_id != video_id:
            raise HTTPException(400, "Невалидный parent_id")
        if parent.is_hidden:
            raise HTTPException(400, "Нельзя отвечать на скрытый комментарий")
        if parent.parent_id is not None:
            raise HTTPException(400, "Ответы разрешены только к комментариям первого уровня")

    comment = Comment(video_id=video_id, user_id=user.id, text=data.text, parent_id=data.parent_id)
    session.add(comment)
    await session.flush()

    return CommentOut(
        id=comment.id, video_id=comment.video_id, user_id=comment.user_id,
        parent_id=comment.parent_id, text=comment.text, likes_count=0,
        is_hidden=False, created_at=comment.created_at,
        author_username=user.username, author_avatar=user.avatar_url,
    )


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    video_id: int,
    comment_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.src.models.user import UserRole
    comment = await session.get(Comment, comment_id)
    if not comment or comment.video_id != video_id:
        raise HTTPException(404)
    if comment.user_id != user.id and user.role not in (UserRole.MODERATOR, UserRole.ADMIN):
        raise HTTPException(403)
    await session.delete(comment)


@router.post("/{comment_id}/like", status_code=200)
async def like_comment(
    video_id: int,
    comment_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = await get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404, "Видео не найдено")

    comment = await session.get(Comment, comment_id)
    if not comment or comment.video_id != video_id or comment.is_hidden:
        raise HTTPException(404, "Комментарий не найден")

    existing = await session.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id, CommentLike.user_id == user.id
        )
    )
    if existing.scalar_one_or_none():
        # снимаем лайк
        from sqlalchemy import delete as sql_delete
        await session.execute(
            sql_delete(CommentLike).where(
                CommentLike.comment_id == comment_id, CommentLike.user_id == user.id
            )
        )
        await session.execute(
            update(Comment).where(Comment.id == comment_id)
            .values(likes_count=func.greatest(Comment.likes_count - 1, 0))
        )
        return {"liked": False}
    else:
        try:
            session.add(CommentLike(comment_id=comment_id, user_id=user.id))
            await session.flush()
            await session.execute(
                update(Comment).where(Comment.id == comment_id)
                .values(likes_count=Comment.likes_count + 1)
            )
        except IntegrityError:
            await session.rollback()
        return {"liked": True}
