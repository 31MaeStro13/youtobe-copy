"""Initial database schema with RBAC, video feed composite indexes, and moderation

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enums
    user_role_enum = postgresql.ENUM("user", "moderator", "admin", name="user_role_enum", create_type=False)
    user_role_enum.create(op.get_bind(), checkfirst=True)

    video_status_enum = postgresql.ENUM("processing", "ready", "failed", name="video_status_enum", create_type=False)
    video_status_enum.create(op.get_bind(), checkfirst=True)

    video_privacy_enum = postgresql.ENUM("public", "unlisted", "private", name="video_privacy_enum", create_type=False)
    video_privacy_enum.create(op.get_bind(), checkfirst=True)

    report_reason_enum = postgresql.ENUM("spam", "inappropriate", "copyright", "violence", "other", name="report_reason_enum", create_type=False)
    report_reason_enum.create(op.get_bind(), checkfirst=True)

    report_status_enum = postgresql.ENUM("pending", "resolved", "dismissed", name="report_status_enum", create_type=False)
    report_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("user", "moderator", "admin", name="user_role_enum", create_type=False), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    # 3. Channels table
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("banner_url", sa.String(length=512), nullable=True),
        sa.Column("subscribers_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_channels_owner_id", "channels", ["owner_id"], unique=False)
    op.create_index("ix_channels_title", "channels", ["title"], unique=False)

    # 4. Subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscriber_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["subscriber_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscriber_id", "channel_id", name="uq_subscriber_channel"),
    )
    op.create_index("ix_subscriptions_subscriber_id", "subscriptions", ["subscriber_id"], unique=False)
    op.create_index("ix_subscriptions_channel_id", "subscriptions", ["channel_id"], unique=False)

    # 5. Videos table
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("video_s3_key", sa.String(length=512), nullable=False),
        sa.Column("thumbnail_s3_key", sa.String(length=512), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("views_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("likes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dislikes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Enum("processing", "ready", "failed", name="video_status_enum", create_type=False), nullable=False, server_default="processing"),
        sa.Column("privacy", sa.Enum("public", "unlisted", "private", name="video_privacy_enum", create_type=False), nullable=False, server_default="public"),
        sa.Column("is_hidden_by_mod", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_videos_channel_id", "videos", ["channel_id"], unique=False)
    op.create_index("ix_videos_status", "videos", ["status"], unique=False)
    op.create_index("ix_videos_privacy", "videos", ["privacy"], unique=False)
    op.create_index("ix_videos_is_hidden_by_mod", "videos", ["is_hidden_by_mod"], unique=False)
    op.create_index("ix_videos_title_search", "videos", ["title"], unique=False)
    op.create_index(
        "ix_videos_feed_lookup",
        "videos",
        ["is_hidden_by_mod", "privacy", "status", "created_at"],
        unique=False,
    )

    # 6. Video Access table (whitelist for private videos)
    op.create_table(
        "video_access",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id", "user_id", name="uq_video_user_access"),
    )
    op.create_index("ix_video_access_video_id", "video_access", ["video_id"], unique=False)
    op.create_index("ix_video_access_user_id", "video_access", ["user_id"], unique=False)

    # 7. Comments table
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("likes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_video_id", "comments", ["video_id"], unique=False)
    op.create_index("ix_comments_user_id", "comments", ["user_id"], unique=False)
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"], unique=False)

    # 8. Video Likes table
    op.create_table(
        "video_likes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("is_like", sa.Boolean(), nullable=False, comment="True - лайк, False - дизлайк"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "video_id", name="uq_user_video_like"),
    )
    op.create_index("ix_video_likes_user_id", "video_likes", ["user_id"], unique=False)
    op.create_index("ix_video_likes_video_id", "video_likes", ["video_id"], unique=False)

    # 9. Comment Likes table
    op.create_table(
        "comment_likes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "comment_id", name="uq_user_comment_like"),
    )
    op.create_index("ix_comment_likes_user_id", "comment_likes", ["user_id"], unique=False)
    op.create_index("ix_comment_likes_comment_id", "comment_likes", ["comment_id"], unique=False)

    # 10. Reports table (Moderation)
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Enum("spam", "inappropriate", "copyright", "violence", "other", name="report_reason_enum", create_type=False), nullable=False, server_default="other"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("pending", "resolved", "dismissed", name="report_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("moderator_id", sa.Integer(), nullable=True),
        sa.Column("moderator_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["moderator_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_video_id", "reports", ["video_id"], unique=False)
    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"], unique=False)
    op.create_index("ix_reports_status", "reports", ["status"], unique=False)
    op.create_index("ix_reports_reason", "reports", ["reason"], unique=False)
    op.create_index("ix_reports_moderator_id", "reports", ["moderator_id"], unique=False)
    op.create_index("ix_reports_status_created_at", "reports", ["status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("comment_likes")
    op.drop_table("video_likes")
    op.drop_table("comments")
    op.drop_table("video_access")
    op.drop_table("videos")
    op.drop_table("subscriptions")
    op.drop_table("channels")
    op.drop_table("users")

    bind = op.get_bind()
    postgresql.ENUM(name="report_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="report_reason_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="video_privacy_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="video_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="user_role_enum").drop(bind, checkfirst=True)
