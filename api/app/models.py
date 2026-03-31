from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class AdminUser(Base):
    __tablename__ = 'lp_admin_users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default='staff', index=True)  # admin/staff
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class User(Base):
    __tablename__ = 'lp_users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default='user', index=True)
    member_code: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    registered_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    initial_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referral_code: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    referral_last_sent_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    referred_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('lp_users.id', ondelete='SET NULL'), nullable=True)
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status_label: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    support_mark: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    acquisition_source: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class LineChannel(Base):
    __tablename__ = 'lp_line_channels'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    channel_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    destination_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    official_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    picture_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    basic_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_synced_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)  # sidejob/material
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class LineIdentity(Base):
    __tablename__ = 'lp_line_identities'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('lp_users.id', ondelete='CASCADE'), index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey('lp_line_channels.id', ondelete='SET NULL'), nullable=True)
    line_user_id: Mapped[str] = mapped_column(String(255), index=True)
    login_sub: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class Conversation(Base):
    __tablename__ = 'lp_conversations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('lp_users.id', ondelete='CASCADE'), index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey('lp_line_channels.id', ondelete='SET NULL'), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_read_message_id: Mapped[int] = mapped_column(Integer, default=0)
    is_pinned: Mapped[int] = mapped_column(Integer, default=0, index=True)

class Message(Base):
    __tablename__ = 'lp_messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey('lp_conversations.id', ondelete='CASCADE'), index=True)
    direction: Mapped[str] = mapped_column(String(20), index=True)  # inbound/outbound
    source: Mapped[str] = mapped_column(String(20), default='line')  # line/web
    message_type: Mapped[str] = mapped_column(String(20), default='text')
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class InterviewProfile(Base):
    __tablename__ = 'lp_interview_profiles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('lp_users.id', ondelete='CASCADE'), unique=True)
    desired_work: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    desired_reward: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    survey_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    survey_completed_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class WebhookEvent(Base):
    __tablename__ = 'lp_webhook_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), default='line', index=True)
    channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    user_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class ReferralEvent(Base):
    __tablename__ = 'lp_referral_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref_code: Mapped[str] = mapped_column(String(32), index=True)
    referrer_user_id: Mapped[int | None] = mapped_column(ForeignKey('lp_users.id', ondelete='SET NULL'), nullable=True)
    line_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), default='click')
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class OnboardingState(Base):
    __tablename__ = 'lp_onboarding_states'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('lp_users.id', ondelete='CASCADE'), unique=True, index=True)
    step: Mapped[int] = mapped_column(Integer, default=0)  # 0:none,100:consent,1..4 questions
    started_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ChannelInterviewProfile(Base):
    __tablename__ = 'lp_channel_interview_profiles'
    __table_args__ = (UniqueConstraint('user_id', 'channel_id', name='uq_user_channel_profile'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('lp_users.id', ondelete='CASCADE'), index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey('lp_line_channels.id', ondelete='SET NULL'), nullable=True, index=True)
    desired_work: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    desired_reward: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    survey_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    survey_completed_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class MessageTemplate(Base):
    __tablename__ = 'lp_message_templates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_name: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    transition_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transition_status_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transition_support_mark: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SavedLink(Base):
    __tablename__ = 'lp_saved_links'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_name: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TemplateFolder(Base):
    __tablename__ = 'lp_template_folders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    folder_type: Mapped[str] = mapped_column(String(20), default='shared', index=True)  # shared/fixed
    fixed_channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ProductItem(Base):
    __tablename__ = 'lp_products'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_type: Mapped[str] = mapped_column(String(30), default='material', index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class MemberRegistration(Base):
    __tablename__ = 'lp_member_registrations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), default='registered', index=True)
    session_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    registered_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class MemberBankAccount(Base):
    __tablename__ = 'lp_member_bank_accounts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_holder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class OfficialLineRegistration(Base):
    __tablename__ = 'lp_official_line_registrations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_key: Mapped[str] = mapped_column(String(20), index=True)
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    form_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(30), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    line_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class RewardLedger(Base):
    __tablename__ = 'lp_reward_ledgers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    channel_key: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
