from pydantic import BaseModel
from typing import Optional, Any

class HealthOut(BaseModel):
    status: str
    app: str

class LoginIn(BaseModel):
    email: str
    password: str

class WebhookIn(BaseModel):
    destination: Optional[str] = None
    events: list[dict[str, Any]] = []

class MessageCreate(BaseModel):
    conversation_id: int
    body: str
    source: str = 'web'

class InterviewUpsert(BaseModel):
    user_id: int
    desired_work: Optional[str] = None
    available_time: Optional[str] = None
    desired_reward: Optional[str] = None
    experience_level: Optional[str] = None
    notes: Optional[str] = None

class MemoUpdate(BaseModel):
    notes: str

class UserAttributesUpdate(BaseModel):
    tag: Optional[str] = None
    status_label: Optional[str] = None
    support_mark: Optional[str] = None

class RegistrationUpsert(BaseModel):
    user_id: int
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None  # 男性/女性/未回答
    phone_number: Optional[str] = None
    initial_tag: Optional[str] = None

class LineSendCreate(BaseModel):
    conversation_id: int
    body: str


class SurveyStartIn(BaseModel):
    message: Optional[str] = None


class TemplateCreateIn(BaseModel):
    folder_name: str
    title: str
    body: str
    url: Optional[str] = None
    transition_tag: Optional[str] = None
    transition_status_label: Optional[str] = None
    transition_support_mark: Optional[str] = None


class TemplateFromMessageIn(BaseModel):
    message_id: int
    folder_name: str
    title: str
    url: Optional[str] = None


class SavedLinkCreateIn(BaseModel):
    folder_name: str
    title: str
    url: str
    note: Optional[str] = None


class LineChannelCreateIn(BaseModel):
    slot: Optional[int] = None
    name: Optional[str] = None
    channel_id: str
    destination_id: Optional[str] = None
    channel_secret: str
    access_token: str
    friend_add_url: Optional[str] = None


class TemplatePreviewIn(BaseModel):
    conversation_id: int
    body: str


class ChannelMergeIn(BaseModel):
    from_channel_id: int
    to_channel_id: int
    deactivate_from: bool = True


class ThanksConfigIn(BaseModel):
    image_url: Optional[str] = None
    wait_sec: Optional[int] = None



class TemplateFolderCreateIn(BaseModel):
    folder_name: str
    folder_type: str = 'shared'  # shared/fixed
    fixed_channel_name: Optional[str] = None


class TemplateUpdateIn(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    url: Optional[str] = None
    transition_tag: Optional[str] = None
    transition_status_label: Optional[str] = None
    transition_support_mark: Optional[str] = None



class TemplateFolderRenameIn(BaseModel):
    new_folder_name: str
    folder_type: Optional[str] = None
    fixed_channel_name: Optional[str] = None



class ProductCreateIn(BaseModel):
    business_type: str = 'material'
    name: str
    price: Optional[int] = None
    description: Optional[str] = None
    purchase_url: Optional[str] = None


class ProductUpdateIn(BaseModel):
    business_type: Optional[str] = None
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    purchase_url: Optional[str] = None
    is_active: Optional[int] = None



class TemplatedSendIn(BaseModel):
    conversation_id: int
    body: str
    template_title: Optional[str] = None
    transition_tag: Optional[str] = None
    transition_status_label: Optional[str] = None
    transition_support_mark: Optional[str] = None


class MemberRegisterIn(BaseModel):
    name: str
    phone_number: str
    email: str
    address: str
    password: str


class MemberBankIn(BaseModel):
    session_token: str
    bank_name: str
    branch_name: str
    account_type: str
    account_number: str
    account_holder: str
