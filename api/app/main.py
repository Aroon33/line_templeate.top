from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, text, func
from .config import settings
from .database import Base, engine, get_db
from . import models, schemas
import os, re, hmac, base64, hashlib, secrets, urllib.parse, subprocess, json
from pathlib import Path
import httpx
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone

app = FastAPI(title='line-platform-api')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

LOGIN_STATE: dict[str, bool] = {}
pwd = CryptContext(schemes=['pbkdf2_sha256','bcrypt'], deprecated='auto')
JWT_SECRET = os.getenv('JWT_SECRET', 'change-me-jwt-secret')
JWT_ALG = 'HS256'
JWT_EXP_HOURS = int(os.getenv('JWT_EXP_HOURS', '24'))


SURVEY_QUESTIONS = [
    {'key':'work_style','q':'Q1: 希望する働き方を選んでください。','options':['在宅メイン','通勤メイン','どちらでも可']},
    {'key':'hours_per_week','q':'Q2: 週あたりの稼働希望時間を選んでください。','options':['5時間未満','5-10時間','10-20時間','20時間以上']},
    {'key':'job_type','q':'Q3: 興味のある業務を選んでください。','options':['チャット対応','SNS運用','事務サポート','営業/案内']},
    {'key':'device_env','q':'Q4: 作業環境を選んでください。','options':['スマホのみ','PCのみ','PC+スマホ']},
    {'key':'sidejob_exp','q':'Q5: 副業経験を選んでください。','options':['未経験','少し経験あり','1年以上経験あり']},
    {'key':'start_timing','q':'Q6: 開始希望時期を選んでください。','options':['すぐ開始したい','1週間以内','今月中','来月以降']},
    {'key':'contact_time','q':'Q7: 連絡が取りやすい時間帯を選んでください。','options':['午前','昼','夕方','夜']},
]

SURVEY_QUESTIONS_BY_CATEGORY = {
    'side': [
        {'key':'current_status','q':'Q1: 現在の状況を選んでください。','options':['会社員','主婦','フリーランス','学生']},
        {'key':'sidejob_exp','q':'Q2: 副業経験を選んでください。','options':['なし','少しある','収益化済']},
        {'key':'income_goal','q':'Q3: 目標収益を選んでください。','options':['月1〜5万','5〜10万','10万以上']},
        {'key':'interest','q':'Q4: 興味分野を選んでください。','options':['SNS','AI','物販','投資']},
        {'key':'problem','q':'Q5: 主な悩みを選んでください。','options':['時間がない','何から始めるか不明','継続できない','稼げない']},
        {'key':'start_timing','q':'Q6: 開始希望時期を選んでください。','options':['今すぐ','1週間以内','今月中','未定']},
        {'key':'contact_time','q':'Q7: 連絡しやすい時間帯を選んでください。','options':['午前','昼','夕方','夜']},
    ],
    'estate': [
        {'key':'property_type','q':'Q1: 物件種別を選んでください。','options':['マンション','戸建て','土地']},
        {'key':'area','q':'Q2: エリアを選んでください。','options':['東京','神奈川','千葉','埼玉']},
        {'key':'sell_timing','q':'Q3: 売却予定時期を選んでください。','options':['すぐ','3ヶ月以内','半年以内','未定']},
        {'key':'appraisal','q':'Q4: 査定希望を選んでください。','options':['希望する','検討中','まだ不要']},
        {'key':'loan_balance','q':'Q5: ローン残債の有無を選んでください。','options':['あり','なし','不明']},
        {'key':'purpose','q':'Q6: 売却理由を選んでください。','options':['住み替え','相続','資産整理','その他']},
        {'key':'contact_time','q':'Q7: 連絡しやすい時間帯を選んでください。','options':['午前','昼','夕方','夜']},
    ],
    'ai': [
        {'key':'ai_exp','q':'Q1: AI使用経験を選んでください。','options':['未経験','少し','日常的']},
        {'key':'use_purpose','q':'Q2: 利用目的を選んでください。','options':['副業','業務効率','情報収集']},
        {'key':'interest','q':'Q3: 興味分野を選んでください。','options':['ChatGPT','画像生成','自動化']},
        {'key':'income_goal','q':'Q4: 収益目標を選んでください。','options':['月〜5万','5〜10万','10万以上']},
        {'key':'problem','q':'Q5: 主な悩みを選んでください。','options':['使い方が不明','継続できない','成果が出ない','時間不足']},
        {'key':'level','q':'Q6: 現在レベルを選んでください。','options':['初心者','中級','上級']},
        {'key':'contact_time','q':'Q7: 連絡しやすい時間帯を選んでください。','options':['午前','昼','夕方','夜']},
    ],
}

SURVEY_TEMPLATE_FILE = Path('/var/www/line-template.top/runtime/survey_templates.json')
SURVEY_LIBRARY_FILE = Path('/var/www/line-template.top/runtime/survey_library.json')
DEFAULT_SURVEY_LIBRARY = [
    {'key': 'age', 'label': '年齢', 'options': ['18-24', '25-34', '35-44', '45-54', '55+']},
    {'key': 'gender', 'label': '性別', 'options': ['男性', '女性', '未回答']},
    {'key': 'address', 'label': '住所', 'options': ['都心', '近郊', '地方', '未回答']},
    {'key': 'name', 'label': '名前', 'options': []},
    {'key': 'cohabit', 'label': '同居', 'options': ['一人暮らし', '家族同居', 'その他']},
    {'key': 'marriage', 'label': '結婚', 'options': ['未婚', '既婚', 'その他']},
    {'key': 'debt', 'label': '借入', 'options': ['なし', 'あり(100万未満)', 'あり(100万以上)']},
    {'key': 'job', 'label': '仕事', 'options': ['会社員', '自営業', '主婦/主夫', '学生', 'その他']},
    {'key': 'time', 'label': '時間', 'options': ['午前', '昼', '夕方', '夜']},
]


def _load_survey_templates() -> dict:
    if not SURVEY_TEMPLATE_FILE.exists():
        return {'side': SURVEY_QUESTIONS_BY_CATEGORY.get('side', []), 'estate': SURVEY_QUESTIONS_BY_CATEGORY.get('estate', []), 'ai': SURVEY_QUESTIONS_BY_CATEGORY.get('ai', [])}
    try:
        data = json.loads(SURVEY_TEMPLATE_FILE.read_text(encoding='utf-8'))
        out = {}
        for k in ('side', 'estate', 'ai'):
            arr = data.get(k) or []
            out[k] = [
                {
                    'key': str(x.get('key') or ''),
                    'q': str(x.get('q') or ''),
                    'options': [str(o) for o in (x.get('options') or []) if str(o).strip()],
                }
                for x in arr if (x.get('key') or x.get('q'))
            ]
        return out
    except Exception:
        return {'side': SURVEY_QUESTIONS_BY_CATEGORY.get('side', []), 'estate': SURVEY_QUESTIONS_BY_CATEGORY.get('estate', []), 'ai': SURVEY_QUESTIONS_BY_CATEGORY.get('ai', [])}


def _save_survey_templates(payload: dict):
    SURVEY_TEMPLATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SURVEY_TEMPLATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _load_survey_library() -> list:
    if not SURVEY_LIBRARY_FILE.exists():
        return DEFAULT_SURVEY_LIBRARY
    try:
        data = json.loads(SURVEY_LIBRARY_FILE.read_text(encoding='utf-8'))
        out = []
        for x in (data or []):
            key = str(x.get('key') or '').strip()
            label = str(x.get('label') or '').strip()
            if not key or not label:
                continue
            opts = [str(o).strip() for o in (x.get('options') or []) if str(o).strip()]
            out.append({'key': key, 'label': label, 'options': opts})
        return out or DEFAULT_SURVEY_LIBRARY
    except Exception:
        return DEFAULT_SURVEY_LIBRARY


def _save_survey_library(items: list):
    cleaned = []
    for x in (items or []):
        key = str(x.get('key') or '').strip()
        label = str(x.get('label') or '').strip()
        if not key or not label:
            continue
        opts = [str(o).strip() for o in (x.get('options') or []) if str(o).strip()]
        cleaned.append({'key': key, 'label': label, 'options': opts})
    SURVEY_LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SURVEY_LIBRARY_FILE.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding='utf-8')

def _detect_line_category(ch) -> str:
    if not ch:
        return 'side'
    cid = str(getattr(ch, 'channel_id', '') or '')
    dest = str(getattr(ch, 'destination_id', '') or '')

    slot2_keys = {
        os.getenv('LINE_CHANNEL_2_ID', '').strip(),
        os.getenv('LINE_CHANNEL_2_DESTINATION', '').strip(),
    }
    slot3_keys = {
        os.getenv('LINE_CHANNEL_3_ID', '').strip(),
        os.getenv('LINE_CHANNEL_3_DESTINATION', '').strip(),
    }
    slot2_keys.discard('')
    slot3_keys.discard('')

    if cid in slot2_keys or dest in slot2_keys:
        return 'estate'
    if cid in slot3_keys or dest in slot3_keys:
        return 'ai'
    return 'side'

def _get_questions_for_category(category: str):
    live = _load_survey_templates()
    return live.get(category) or SURVEY_QUESTIONS_BY_CATEGORY.get(category) or SURVEY_QUESTIONS

def _post_survey_register_prompt(category: str) -> str:
    # ログイン不要の公式LINE別フォームへ誘導
    ch_key = 'ch1'
    if category == 'estate':
        ch_key = 'ch2'
    elif category == 'ai':
        ch_key = 'ch3'
    form_url = f'https://line-template.top/register?ch={ch_key}'

    if category == 'estate':
        return (
            "アンケートありがとうございます🏠\n"
            "会員登録フォーム完了で、持ち家の売却希望者には3万円プレゼント対象のご案内を行います。\n"
            f"{form_url}"
        )
    if category == 'ai':
        return (
            "アンケートありがとうございます🤖\n"
            "会員登録フォーム完了で、AIエージェント設定を無料で行います。\n"
            f"{form_url}"
        )
    return (
        "アンケートありがとうございます🎁\n"
        "会員登録フォーム完了で、即日報酬の対象案内を行います。\n"
        f"{form_url}"
    )



def _simple_auto_reply(category: str, txt: str) -> str | None:
    t = (txt or '').strip().lower()
    if not t:
        return None

    if category == 'estate':
        if '査定' in txt or '売却' in txt:
            return '不動産LINEです🏠 無料査定の案内が可能です。まず「売却予定（すぐ/3ヶ月/半年/未定）」を教えてください。'
        if 'ローン' in txt:
            return 'ローン残債があっても売却可能です。差額計算のため、概算の残債有無を教えてください。'
        if 'エリア' in txt:
            return 'ありがとうございます。市区町村レベルで教えていただければ次の案内に進めます。'
        return '不動産LINEです。売却相談は「査定希望」または「売却相談」と送ってください。'

    if category == 'ai':
        if 'note' in t or 'ノート' in txt:
            return 'AIマネジメントLINEです🤖 NOTE導線をご案内します。初心者ですか？経験者ですか？'
        if 'chatgpt' in t or '自動化' in txt or '画像' in txt:
            return '興味分野ありがとうございます。用途（副業/業務効率/情報収集）を教えてください。'
        return 'AIマネジメントLINEです。AI活用の質問はそのまま送ってください。基礎/応用NOTEへ案内します。'

    # side business default
    if '副業' in txt or '稼' in txt or '収益' in txt:
        return '副業LINEです🎁 現在の状況（会社員/主婦/フリーランス/学生）を教えてください。'
    if '初心者' in txt:
        return '初心者向け導線があります。目標収益（月1〜5万 / 5〜10万 / 10万以上）を教えてください。'
    return '副業LINEです。まず「副業相談」と送っていただければ、最適な導線に案内します。'

def _next_member_code(db: Session) -> str:
    max_id = db.execute(select(func.max(models.User.id))).scalar_one_or_none() or 0
    return f'U{(max_id + 1):06d}'


def _new_referral_code() -> str:
    return secrets.token_urlsafe(6).replace('-', '').replace('_', '')[:10]


def _ensure_user_codes(db: Session, user: models.User):
    changed = False
    if not user.member_code:
        user.member_code = _next_member_code(db)
        changed = True
    if not user.referral_code:
        for _ in range(5):
            c = _new_referral_code()
            exists = db.execute(select(models.User).where(models.User.referral_code == c)).scalar_one_or_none()
            if not exists:
                user.referral_code = c
                changed = True
                break
    if changed:
        db.flush()


def _affiliate_base_url(channel_slot: int | None = None) -> str:
    if channel_slot in (1,2,3):
        v = os.getenv(f'LINE_CHANNEL_{channel_slot}_FRIEND_ADD_URL','').strip()
        if v:
            return v
    return os.getenv('DEFAULT_FRIEND_ADD_URL','https://line-template.top')

def _line_push_quick_reply(token: str, to: str, text_value: str, options: list[str]) -> bool:
    try:
        items = []
        for op in (options or [])[:13]:
            items.append({'type':'action','action':{'type':'message','label':op[:20],'text':op}})
        r = httpx.post(
            'https://api.line.me/v2/bot/message/push',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'to': to, 'messages': [{'type': 'text', 'text': text_value, 'quickReply': {'items': items}}]},
            timeout=20,
        )
        return r.status_code < 400
    except Exception:
        return False


def _line_push_buttons(token: str, to: str, text_value: str, options: list[str]) -> bool:
    try:
        actions = []
        for op in (options or [])[:4]:
            actions.append({'type':'message','label':op[:20],'text':op})
        r = httpx.post(
            'https://api.line.me/v2/bot/message/push',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'to': to, 'messages': [{'type': 'template', 'altText': text_value, 'template': {'type':'buttons','text':text_value[:160],'actions':actions}}]},
            timeout=20,
        )
        return r.status_code < 400
    except Exception:
        return False


def _line_push_text(token: str, to: str, text_value: str) -> bool:
    try:
        r = httpx.post(
            'https://api.line.me/v2/bot/message/push',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'to': to, 'messages': [{'type': 'text', 'text': text_value}]},
            timeout=20,
        )
        return r.status_code < 400
    except Exception:
        return False




def _get_identity_by_conversation(db: Session, conversation_id: int):
    conv = db.get(models.Conversation, conversation_id)
    if not conv:
        return None, None, None, None
    ident = db.execute(
        select(models.LineIdentity).where(
            models.LineIdentity.user_id == conv.user_id,
            models.LineIdentity.channel_id == conv.channel_id,
        )
    ).scalar_one_or_none()
    if not ident:
        # fallback: any identity for user
        ident = db.execute(select(models.LineIdentity).where(models.LineIdentity.user_id == conv.user_id)).scalars().first()
    ch = db.get(models.LineChannel, conv.channel_id) if conv.channel_id else None
    channel_key = ch.channel_id if ch else None
    token = _line_channel_tokens().get(channel_key)
    return conv, ident, ch, token
def _get_user_channel_and_token(db: Session, user_id: int):
    ident = db.execute(select(models.LineIdentity).where(models.LineIdentity.user_id == user_id)).scalar_one_or_none()
    if not ident:
        return None, None, None
    ch = db.get(models.LineChannel, ident.channel_id) if ident.channel_id else None
    channel_key = ch.channel_id if ch else None
    token = _line_channel_tokens().get(channel_key)
    return ident, ch, token


def _get_or_create_conv(db: Session, user_id: int, channel_id: int | None):
    q = select(models.Conversation).where(models.Conversation.user_id == user_id, models.Conversation.channel_id == channel_id)
    conv = db.execute(q).scalar_one_or_none()
    if not conv:
        conv = models.Conversation(user_id=user_id, channel_id=channel_id)
        db.add(conv)
        db.flush()
    return conv

def _get_channel_profile(db: Session, user_id: int, channel_id: int | None, create: bool=False):
    q = select(models.ChannelInterviewProfile).where(
        models.ChannelInterviewProfile.user_id == user_id,
        models.ChannelInterviewProfile.channel_id == channel_id,
    )
    row = db.execute(q).scalar_one_or_none()
    if not row and create:
        row = models.ChannelInterviewProfile(user_id=user_id, channel_id=channel_id)
        db.add(row)
        db.flush()
    return row



def _render_template_text(raw: str, user: models.User, profile=None, channel_name: str | None = None) -> str:
    if not raw:
        return ''
    mapping = {
        '{{USER_NAME}}': (user.display_name or f'USER{user.id}'),
        '{{CHANNEL_NAME}}': (channel_name or '-'),
        '{{MEMBER_CODE}}': (user.member_code or f'U{user.id:06d}'),
        '{{USER_ID}}': str(user.id),
        '{{REGISTERED_AT}}': (str(user.registered_at) if user.registered_at else '-'),
        '{{AGE}}': (str(user.age) if user.age is not None else '-'),
        '{{GENDER}}': (user.gender or '-'),
        '{{PHONE}}': (user.phone_number or '-'),
        '{{TAG}}': (user.tag or '-'),
        '{{INITIAL_TAG}}': (user.initial_tag or '-'),
        '{{REFERRAL_LINK}}': (f'https://line-template.top/r/{user.referral_code}' if user.referral_code else '-'),
        '{{DESIRED_WORK}}': (getattr(profile,'desired_work',None) or '-'),
        '{{AVAILABLE_TIME}}': (getattr(profile,'available_time',None) or '-'),
        '{{DESIRED_REWARD}}': (getattr(profile,'desired_reward',None) or '-'),
        '{{EXPERIENCE_LEVEL}}': (getattr(profile,'experience_level',None) or '-'),
    }
    out = raw
    for k,v in mapping.items():
        out = out.replace(k, v)
    return out


def _handle_onboarding_text(db: Session, user: models.User, line_user_id: str, destination: str | None, text_in: str):
    txt = (text_in or '').strip()
    if not txt:
        return
    st = db.execute(select(models.OnboardingState).where(models.OnboardingState.user_id == user.id)).scalar_one_or_none()
    if not st:
        st = models.OnboardingState(user_id=user.id, step=0)
        db.add(st)
        db.flush()

    ch = None
    if destination:
        ch = db.execute(select(models.LineChannel).where(models.LineChannel.channel_id == destination)).scalar_one_or_none()
    ident = None
    if ch:
        ident = db.execute(select(models.LineIdentity).where(models.LineIdentity.user_id == user.id, models.LineIdentity.channel_id == ch.id)).scalar_one_or_none()
    if not ident:
        ident = db.execute(select(models.LineIdentity).where(models.LineIdentity.user_id == user.id)).scalar_one_or_none()
    token = _line_channel_tokens().get(destination) if destination else None
    if not token and ch:
        token = _line_channel_tokens().get(ch.channel_id)
    if not ident or not token:
        return
    conv = _get_or_create_conv(db, user.id, ch.id if ch else None)

    if (user.support_mark or '') in ('購入者','スタッフ対応','サポート対応'):
        return

    def send_bot(msg: str):
        ok = _line_push_text(token, line_user_id, msg)
        if ok:
            db.add(models.Message(conversation_id=conv.id, direction='outbound', source='line', message_type='text', body=msg))

    def send_choice(msg: str, options: list[str], mode: str='quick'):
        ok = _line_push_buttons(token, line_user_id, msg, options) if mode=='buttons' else _line_push_quick_reply(token, line_user_id, msg, options)
        if ok:
            db.add(models.Message(conversation_id=conv.id, direction='outbound', source='line', message_type='text', body=msg + '\n選択肢: ' + ' / '.join(options)))

    category = _detect_line_category(ch)

    # フォーム直送モード: アンケート回答済みとしてフォームのみ案内
    if txt in ('フォーム', '登録フォーム', '会員登録フォーム', 'form'):
        st.step = 0
        st.completed_at = datetime.now()
        user.tag = '回答済み'
        user.status_label = 'アンケート完了'
        send_bot(_post_survey_register_prompt(category))
        return

    if txt in ('アンケート', '登録') and st.step == 0:
        st.step = 100
        send_choice('登録アンケートを開始しますか？', ['はい', 'いいえ'], mode='buttons')
        return

    if st.step == 100:
        if txt == 'はい':
            st.step = 10
            st.started_at = datetime.now()
            user.tag = '回答中'
            user.status_label = 'アンケート待ち'
            send_bot('まず登録情報です。お名前（漢字フルネーム）を入力してください。')
            return
        elif txt == 'いいえ':
            st.step = 0
            send_bot('了解しました。必要な時に「アンケート」と送ってください。')
            return
        # 未回答時でもカテゴリ別の簡易自動応答を返す
        category = _detect_line_category(ch)
        auto = _simple_auto_reply(category, txt)
        if auto:
            send_bot(auto)
        send_choice('アンケートを開始する場合は「はい」を選んでください。', ['はい', 'いいえ'], mode='buttons')
        return

    profile = _get_channel_profile(db, user.id, ch.id if ch else None, create=True)
    category = _detect_line_category(ch)
    questions = _get_questions_for_category(category)

    if st.step == 10:
        ans = dict(profile.survey_answers or {})
        ans['reg_name'] = txt
        profile.survey_answers = ans
        st.step = 11
        send_bot('電話番号を入力してください（例: 09012345678）')
        return

    if st.step == 11:
        phone = re.sub(r'[^0-9]', '', txt)
        if len(phone) < 10:
            send_bot('電話番号の形式で入力してください（例: 09012345678）')
            return
        ans = dict(profile.survey_answers or {})
        ans['reg_phone'] = phone
        profile.survey_answers = ans
        st.step = 12
        send_choice('年齢帯を選択してください。', ['10代','20代','30代','40代','50代以上'])
        return

    if st.step == 12:
        if txt not in ('10代','20代','30代','40代','50代以上'):
            send_choice('年齢帯を選択してください。', ['10代','20代','30代','40代','50代以上'])
            return
        ans = dict(profile.survey_answers or {})
        ans['reg_age_band'] = txt
        profile.survey_answers = ans
        st.step = 13
        send_choice('性別を選択してください。', ['男性', '女性', '未回答'])
        return

    if st.step == 13:
        if txt not in ('男性', '女性', '未回答'):
            send_choice('性別を選択してください。', ['男性', '女性', '未回答'])
            return
        ans = dict(profile.survey_answers or {})
        ans['reg_gender'] = txt
        profile.survey_answers = ans
        st.step = 20
        q = questions[0]
        if (q.get('type') or 'single') == 'text':
            send_bot(q['q'])
        else:
            send_choice(q['q'], q.get('options') or ['はい','いいえ'])
        return

    if 20 <= st.step <= (20 + len(questions) - 1):
        idx = st.step - 20
        q = questions[idx]
        options = q.get('options') or []
        q_type = q.get('type') or 'single'

        if q_type == 'text':
            answer_value = txt
        elif q_type == 'multi':
            picks = [x.strip() for x in re.split(r'[,、/\n]', txt or '') if x.strip()]
            valid = [p for p in picks if p in options]
            if not valid:
                send_choice(q['q'], options)
                return
            answer_value = valid
        else:
            if txt not in options:
                send_choice(q['q'], options)
                return
            answer_value = txt

        ans = dict(profile.survey_answers or {})
        ans[q['key']] = answer_value
        profile.survey_answers = ans

        if st.step < (20 + len(questions) - 1):
            st.step += 1
            nq = questions[st.step - 20]
            if (nq.get('type') or 'single') == 'text':
                send_bot(nq['q'])
            else:
                send_choice(nq['q'], nq.get('options') or ['はい','いいえ'])
            return
        else:
            st.step = 0
            st.completed_at = datetime.now()
            profile.survey_completed_at = datetime.now()
            user.tag = '回答済み'
            user.status_label = 'アンケート完了'
            ans0 = dict(profile.survey_answers or {})
            summary_lines = [
                f"・名前: {ans0.get('reg_name') or '-'}",
                f"・電話: {ans0.get('reg_phone') or '-'}",
                f"・年齢: {ans0.get('reg_age_band') or '-'}",
                f"・性別: {ans0.get('reg_gender') or '-'}",
            ]
            labels = {
                'current_status':'現在の状況','sidejob_exp':'副業経験','income_goal':'目標収益','interest':'興味分野','problem':'悩み',
                'start_timing':'開始時期','contact_time':'連絡時間帯','property_type':'物件種別','area':'エリア','sell_timing':'売却予定',
                'appraisal':'査定希望','loan_balance':'ローン残債','purpose':'売却理由','ai_exp':'AI使用経験','use_purpose':'利用目的','level':'レベル'
            }
            ans_all = dict(profile.survey_answers or {})
            for k in ['reg_name','reg_phone','reg_age_band','reg_gender','acquisition_source']:
                ans_all.pop(k, None)
            ordered_keys = [q.get('key') for q in questions]
            for k in ordered_keys:
                if k in ans_all:
                    summary_lines.append(f"・{labels.get(k,k)}: {ans_all.get(k)}")
            send_bot('ありがとうございます。初回アンケート完了です。\n' + '\n'.join(summary_lines))
            send_bot(_post_survey_register_prompt(category))
            user.status_label = '会員登録中'
            return




    auto = _simple_auto_reply(category, txt)
    if auto:
        send_bot(auto)
        return

def _apply_post_send_state(user: models.User, template_title: str | None, body: str | None):
    t = ((template_title or '') + ' ' + (body or '')).strip()
    if not t:
        return

    # registration flow
    if '会員登録' in t and '済' not in t:
        user.tag = '会員登録中'
        user.status_label = '会員登録中'
    if '回答内容確認' in t or 'アンケート完了' in t:
        user.tag = '回答済み'
        user.status_label = 'アンケート完了'

    # project flow
    if '案件紹介' in t:
        user.tag = '案件紹介中'
        user.status_label = '案件紹介中'

    for i in range(1, 6):
        if f'案件{i}済' in t:
            user.tag = f'案件{i}済'
            user.status_label = f'案件{i}済'
        elif f'案件{i}' in t and ('中' in t or '開始' in t or '案内' in t or '提案' in t):
            user.tag = f'案件{i}中'
            user.status_label = f'案件{i}中'

    # purchase flow
    if ('購入' in t and ('完了' in t or 'ありがとうございます' in t)) or '購入者' in t:
        user.tag = 'フロント商品購入'
        user.status_label = 'フロント販売完了'
        user.support_mark = '購入者'


def _send_welcome_sequence(db: Session, user: models.User, line_user_id: str, channel_id: int | None, token: str | None):
    if not token or not line_user_id:
        return
    conv = _get_or_create_conv(db, user.id, channel_id)
    # set default ops markers
    user.tag = user.tag or '登録時'
    user.status_label = user.status_label or '新規受付'
    user.support_mark = user.support_mark or 'AI対応中'

    ch = db.get(models.LineChannel, channel_id) if channel_id else None
    ch_name = (ch.official_account_name or ch.name) if ch else '公式LINE'
    category = _detect_line_category(ch)
    if category == 'estate':
        greet = f"{(user.display_name or 'ご登録者様')}、{ch_name}にご登録ありがとうございます🏠\n持ち家売却希望の方向け特典があります。まずは30秒アンケートをお願いします。"
    elif category == 'ai':
        greet = f"{(user.display_name or 'ご登録者様')}、{ch_name}にご登録ありがとうございます🤖\n会員登録でAIエージェント設定を無料対応します。まずは30秒アンケートをお願いします。"
    else:
        greet = f"{(user.display_name or 'ご登録者様')}、{ch_name}にご登録ありがとうございます🎁\n会員登録で即日報酬対象の案内があります。まずは30秒アンケートをお願いします。"
    ok1 = _line_push_text(token, line_user_id, greet)
    if ok1:
        db.add(models.Message(conversation_id=conv.id, direction='outbound', source='line', message_type='text', body=greet))

    ask = '登録アンケートを開始しますか？'
    ok2 = _line_push_buttons(token, line_user_id, ask, ['はい', 'いいえ'])
    if ok2:
        db.add(models.Message(conversation_id=conv.id, direction='outbound', source='line', message_type='text', body=ask + '\n選択肢: はい / いいえ'))

    st = db.execute(select(models.OnboardingState).where(models.OnboardingState.user_id == user.id)).scalar_one_or_none()
    if not st:
        st = models.OnboardingState(user_id=user.id, step=100)
        db.add(st)
    else:
        st.step = 100

def make_token(admin_id: int, role: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {'sub': str(admin_id), 'role': role, 'email': email, 'iat': int(now.timestamp()), 'exp': int((now + timedelta(hours=JWT_EXP_HOURS)).timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def current_admin(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(401, 'missing bearer token')
    token = authorization.split(' ',1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(401, 'invalid token')
    admin_id = int(payload.get('sub', '0'))
    admin = db.get(models.AdminUser, admin_id)
    if not admin or admin.is_active != 1:
        raise HTTPException(401, 'admin not active')
    return admin




def _update_env_file(updates: dict[str, str], env_path: str = '/var/www/line-template.top/.env'):
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []

    keys = set(updates.keys())
    new_lines = []
    found = set()
    for ln in lines:
        if '=' in ln and not ln.strip().startswith('#'):
            k = ln.split('=',1)[0]
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                found.add(k)
                continue
        new_lines.append(ln)
    for k in keys - found:
        new_lines.append(f"{k}={updates[k]}")

    with open(env_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines) + '\n')


def _next_channel_slot_from_env() -> int:
    used=[]
    for i in (1,2,3):
        if os.getenv(f'LINE_CHANNEL_{i}_ID','').strip() or os.getenv(f'LINE_CHANNEL_{i}_DESTINATION','').strip():
            used.append(i)
    for i in (1,2,3):
        if i not in used:
            return i
    return 3
def _line_channel_secrets() -> dict[str, str]:
    out = {}
    for i in (1,2,3):
        dest = os.getenv(f'LINE_CHANNEL_{i}_DESTINATION','').strip()
        cid = os.getenv(f'LINE_CHANNEL_{i}_ID','').strip()
        sec = os.getenv(f'LINE_CHANNEL_{i}_SECRET','').strip()
        if sec:
            out[(dest or cid)] = sec
    return out


def _line_channel_tokens() -> dict[str, str]:
    out = {}
    for i in (1,2,3):
        dest = os.getenv(f'LINE_CHANNEL_{i}_DESTINATION','').strip()
        cid = os.getenv(f'LINE_CHANNEL_{i}_ID','').strip()
        tok = os.getenv(f'LINE_CHANNEL_{i}_ACCESS_TOKEN','').strip()
        if tok:
            out[(dest or cid)] = tok
    return out


def _verify_line_signature(raw: bytes, signature: str, channel_secret: str) -> bool:
    mac = hmac.new(channel_secret.encode('utf-8'), raw, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode('utf-8')
    return hmac.compare_digest(expected, signature)

def _fetch_line_profile(line_user_id: str, channel_key: str | None) -> dict:
    if not line_user_id or not channel_key:
        return {}
    token = _line_channel_tokens().get(channel_key)
    if not token:
        return {}
    try:
        r = httpx.get(
            f'https://api.line.me/v2/bot/profile/{line_user_id}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=10
        )
        if r.status_code >= 400:
            return {}
        j = r.json()
        return {'display_name': j.get('displayName'), 'picture_url': j.get('pictureUrl')}
    except Exception:
        return {}


def _ensure_schema_columns():
    # For existing DBs where create_all won't alter existing tables.
    stmts = [
        "ALTER TABLE lp_users ADD COLUMN profile_image_url VARCHAR(1024) NULL",
        "ALTER TABLE lp_users ADD COLUMN tag VARCHAR(100) NULL",
        "ALTER TABLE lp_users ADD COLUMN status_label VARCHAR(100) NULL",
        "ALTER TABLE lp_users ADD COLUMN support_mark VARCHAR(100) NULL",
        "ALTER TABLE lp_users ADD COLUMN acquisition_source VARCHAR(50) NULL",
        "ALTER TABLE lp_conversations ADD COLUMN last_read_message_id INT NOT NULL DEFAULT 0",
        "ALTER TABLE lp_conversations ADD COLUMN is_pinned INT NOT NULL DEFAULT 0",
        "ALTER TABLE lp_line_channels ADD COLUMN destination_id VARCHAR(255) NULL",
        "ALTER TABLE lp_line_channels ADD COLUMN official_account_name VARCHAR(255) NULL",
        "ALTER TABLE lp_line_channels ADD COLUMN picture_url VARCHAR(1024) NULL",
        "ALTER TABLE lp_line_channels ADD COLUMN status_message VARCHAR(1024) NULL",
        "ALTER TABLE lp_line_channels ADD COLUMN basic_id VARCHAR(100) NULL",
        "ALTER TABLE lp_line_channels ADD COLUMN follower_count INT NULL",
        "ALTER TABLE lp_line_channels ADD COLUMN last_synced_at DATETIME NULL",
        "ALTER TABLE lp_line_channels ADD COLUMN business_type VARCHAR(30) NULL",
        "ALTER TABLE lp_users ADD COLUMN member_code VARCHAR(20) NULL",
        "ALTER TABLE lp_users ADD COLUMN age INT NULL",
        "ALTER TABLE lp_users ADD COLUMN gender VARCHAR(20) NULL",
        "ALTER TABLE lp_users ADD COLUMN phone_number VARCHAR(30) NULL",
        "ALTER TABLE lp_users ADD COLUMN registered_at DATETIME NULL",
        "ALTER TABLE lp_users ADD COLUMN initial_tag VARCHAR(100) NULL",
        "ALTER TABLE lp_users ADD COLUMN referral_code VARCHAR(32) NULL",
        "ALTER TABLE lp_users ADD COLUMN referred_by_user_id INT NULL",
        "ALTER TABLE lp_users ADD COLUMN referral_last_sent_at DATETIME NULL",
        "ALTER TABLE lp_referral_events ADD COLUMN line_user_id VARCHAR(255) NULL",
        "ALTER TABLE lp_message_templates ADD COLUMN transition_tag VARCHAR(100) NULL",
        "ALTER TABLE lp_message_templates ADD COLUMN transition_status_label VARCHAR(100) NULL",
        "ALTER TABLE lp_message_templates ADD COLUMN transition_support_mark VARCHAR(100) NULL",
        "ALTER TABLE lp_channel_interview_profiles ADD COLUMN survey_answers JSON NULL",
        "ALTER TABLE lp_channel_interview_profiles ADD COLUMN survey_completed_at DATETIME NULL",
    ]
    with engine.begin() as conn:
        for sql in stmts:
            try:
                conn.execute(text(sql))
            except Exception:
                # Column may already exist
                pass


@app.on_event('startup')
def startup():
    Base.metadata.create_all(bind=engine)
    _ensure_schema_columns()
    with engine.begin() as conn:
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS lp_referral_events (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    ref_code VARCHAR(32) NOT NULL,
                    referrer_user_id INT NULL,
                    line_user_id VARCHAR(255) NULL,
                    event_type VARCHAR(30) NOT NULL DEFAULT 'click',
                    raw_payload JSON NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_ref_code (ref_code),
                    CONSTRAINT fk_referrer_user FOREIGN KEY (referrer_user_id) REFERENCES lp_users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
        except Exception:
            pass
    seed_email = os.getenv('ADMIN_SEED_EMAIL', 'admin@sns-template.com')
    seed_pw = os.getenv('ADMIN_SEED_PASSWORD', 'ChangeMe123!')
    admin = engine.connect()
    admin.close()


@app.get('/health', response_model=schemas.HealthOut)
def health():
    return {'status':'ok','app':settings.app_name}


@app.post('/auth/admin/login')
def admin_login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    row = db.execute(select(models.AdminUser).where(models.AdminUser.email == payload.email)).scalar_one_or_none()
    if not row:
        # auto-seed first admin from env
        seed_email = os.getenv('ADMIN_SEED_EMAIL', 'admin@sns-template.com')
        seed_pw = os.getenv('ADMIN_SEED_PASSWORD', 'ChangeMe123!')
        if payload.email == seed_email and payload.password == seed_pw:
            row = models.AdminUser(role='admin', name='Administrator', email=seed_email, password_hash=pwd.hash(seed_pw), is_active=1)
            db.add(row); db.commit(); db.refresh(row)
        else:
            raise HTTPException(401, 'invalid credentials')
    if not pwd.verify(payload.password, row.password_hash):
        raise HTTPException(401, 'invalid credentials')
    token = make_token(row.id, row.role, row.email)
    return {'access_token': token, 'token_type':'bearer', 'role': row.role, 'name': row.name, 'email': row.email}


@app.get('/auth/admin/me')
def admin_me(admin: models.AdminUser = Depends(current_admin)):
    return {'id': admin.id, 'role': admin.role, 'name': admin.name, 'email': admin.email}


@app.get('/auth/line/login')
def line_login_start(state: str | None = None):
    channel_id = os.getenv('LINE_LOGIN_CHANNEL_ID','').strip()
    callback = os.getenv('LINE_LOGIN_CALLBACK','').strip()
    if not channel_id or not callback:
        raise HTTPException(500,'LINE login env not configured')
    state = (state or secrets.token_urlsafe(24)); nonce = secrets.token_urlsafe(24); LOGIN_STATE[state]=True
    q={'response_type':'code','client_id':channel_id,'redirect_uri':callback,'state':state,'scope':'profile openid email','nonce':nonce}
    url='https://access.line.me/oauth2/v2.1/authorize?' + urllib.parse.urlencode(q)
    return RedirectResponse(url=url)


@app.get('/auth/line/callback')
def line_login_callback(code: str, state: str, db: Session = Depends(get_db)):
    if not LOGIN_STATE.pop(state, None):
        raise HTTPException(400,'invalid state')
    channel_id = os.getenv('LINE_LOGIN_CHANNEL_ID','').strip()
    channel_secret = os.getenv('LINE_LOGIN_CHANNEL_SECRET','').strip()
    callback = os.getenv('LINE_LOGIN_CALLBACK','').strip()
    token_res = httpx.post('https://api.line.me/oauth2/v2.1/token', data={'grant_type':'authorization_code','code':code,'redirect_uri':callback,'client_id':channel_id,'client_secret':channel_secret}, timeout=20)
    if token_res.status_code >= 400:
        raise HTTPException(400, f'line token error: {token_res.text}')
    access_token = token_res.json().get('access_token')
    acq_src = None
    try:
        st = urllib.parse.unquote_plus(state or '')
        q = urllib.parse.parse_qs(st)
        acq_src = (q.get('src') or [None])[0]
    except Exception:
        acq_src = None
    prof_res = httpx.get('https://api.line.me/v2/profile', headers={'Authorization': f'Bearer {access_token}'}, timeout=20)
    if prof_res.status_code >= 400:
        raise HTTPException(400, f'line profile error: {prof_res.text}')
    p = prof_res.json(); line_user_id = p.get('userId'); display_name = p.get('displayName'); picture_url = p.get('pictureUrl')
    ident = db.execute(select(models.LineIdentity).where(models.LineIdentity.line_user_id == line_user_id)).scalar_one_or_none()
    if ident: user = db.get(models.User, ident.user_id)
    else:
        user = models.User(role='user', display_name=display_name, profile_image_url=picture_url, acquisition_source=(acq_src or 'normal'), tag='登録時', status_label='新規受付', support_mark='AI対応中'); db.add(user); db.flush(); _ensure_user_codes(db, user)
        db.add(models.LineIdentity(user_id=user.id, line_user_id=line_user_id, login_sub=line_user_id))
    if display_name:
        # Keep LINE profile name as canonical display name in chat UI.
        user.display_name = display_name
    if picture_url: user.profile_image_url = picture_url
    if acq_src: user.acquisition_source = acq_src
    _ensure_user_codes(db, user)

    # prepare registration session token (LINEログイン後に会員登録フォームへ遷移)
    reg = db.execute(select(models.MemberRegistration).where(models.MemberRegistration.user_id == user.id).order_by(models.MemberRegistration.id.desc()).limit(1)).scalar_one_or_none()
    if not reg:
        reg = models.MemberRegistration(user_id=user.id, status='line_logged_in')
        db.add(reg)
        db.flush()

    # prefill from latest survey answers when available
    prof = db.execute(select(models.ChannelInterviewProfile).where(models.ChannelInterviewProfile.user_id == user.id).order_by(models.ChannelInterviewProfile.updated_at.desc()).limit(1)).scalar_one_or_none()
    ans = (prof.survey_answers or {}) if prof else {}
    survey_name = (ans.get('reg_name') or '').strip() if isinstance(ans, dict) else ''
    survey_phone = re.sub(r'[^0-9]', '', str(ans.get('reg_phone') or '')) if isinstance(ans, dict) else ''

    if survey_name and not reg.name:
        reg.name = survey_name
    if survey_phone and not reg.phone_number:
        reg.phone_number = survey_phone

    token_for_form = secrets.token_urlsafe(32)
    reg.session_token = token_for_form

    db.commit()
    return RedirectResponse(url=f'https://line-template.top/register?token={token_for_form}')


@app.post('/webhooks/line')
@app.post('/webhooks/line/ch1')
@app.post('/webhooks/line/ch2')
@app.post('/webhooks/line/ch3')
async def line_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body(); body = await request.json(); signature = request.headers.get('x-line-signature','')
    destination = body.get('destination'); events = body.get('events',[]) or []

    # endpoint-specific override (for stable multi-channel separation)
    path = str(request.url.path or '')
    slot = None
    if path.endswith('/ch1'):
        slot = 1
    elif path.endswith('/ch2'):
        slot = 2
    elif path.endswith('/ch3'):
        slot = 3
    if slot:
        destination = (os.getenv(f'LINE_CHANNEL_{slot}_DESTINATION','').strip() or os.getenv(f'LINE_CHANNEL_{slot}_ID','').strip() or destination)

    secrets_map = _line_channel_secrets()
    if destination and destination in secrets_map:
        if not signature or not _verify_line_signature(raw, signature, secrets_map[destination]):
            raise HTTPException(401,'invalid line signature')

    channel_row = None
    if destination:
        channel_row = db.execute(select(models.LineChannel).where(models.LineChannel.channel_id == destination)).scalar_one_or_none()
        if not channel_row:
            channel_row = models.LineChannel(name=f'LINE-{destination[-6:]}', channel_id=destination, destination_id=destination); db.add(channel_row); db.flush()
        elif destination and not channel_row.destination_id:
            channel_row.destination_id = destination

    saved = 0
    for ev in events:
        src = ev.get('source',{}) or {}
        db.add(models.WebhookEvent(provider='line', channel_id=destination, event_type=ev.get('type'), user_key=src.get('userId'), payload=ev)); saved += 1
        user = None
        if src.get('userId'):
            ident = db.execute(select(models.LineIdentity).where(models.LineIdentity.line_user_id == src['userId'])).scalar_one_or_none()
            if ident:
                user = db.get(models.User, ident.user_id)
                if channel_row and ident.channel_id is None:
                    ident.channel_id = channel_row.id
            else:
                user = models.User(role='user', tag='登録時', status_label='新規受付', support_mark='AI対応中', acquisition_source='normal')
                db.add(user)
                db.flush()
                _ensure_user_codes(db, user)
                db.add(models.LineIdentity(user_id=user.id, line_user_id=src['userId'], channel_id=(channel_row.id if channel_row else None)))

            _ensure_user_codes(db, user)
            prof = _fetch_line_profile(src['userId'], destination)
            if user and prof:
                if prof.get('display_name'):
                    # Always sync to current LINE display name.
                    user.display_name = prof.get('display_name')
                if prof.get('picture_url'):
                    user.profile_image_url = prof.get('picture_url')
        if user:
            if ev.get('type') == 'follow':
                _send_welcome_sequence(db, user, src.get('userId'), (channel_row.id if channel_row else None), _line_channel_tokens().get(destination))
            q = select(models.Conversation).where(models.Conversation.user_id == user.id)
            q = q.where(models.Conversation.channel_id == (channel_row.id if channel_row else None))
            conv = db.execute(q).scalar_one_or_none()
            if not conv:
                conv = models.Conversation(user_id=user.id, channel_id=(channel_row.id if channel_row else None)); db.add(conv); db.flush()
            txt = ev.get('message',{}).get('text') if ev.get('message',{}).get('type')=='text' else None
            db.add(models.Message(conversation_id=conv.id, direction='inbound', source='line', message_type=ev.get('message',{}).get('type','event'), body=txt, raw_payload=ev))

            # fallback: if follow event is not delivered, trigger welcome on first inbound message
            if txt:
                try:
                    has_outbound = db.execute(
                        select(func.count(models.Message.id)).where(
                            models.Message.conversation_id == conv.id,
                            models.Message.direction == 'outbound',
                            models.Message.source == 'line'
                        )
                    ).scalar_one() or 0
                except Exception:
                    has_outbound = 0
                if has_outbound == 0:
                    _send_welcome_sequence(db, user, src.get('userId'), (channel_row.id if channel_row else None), _line_channel_tokens().get(destination))
                _handle_onboarding_text(db, user, src.get('userId'), destination, txt)
    db.commit()
    return {'ok':True,'saved':saved}


@app.get('/conversations')
def list_conversations(db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    rows = db.execute(select(models.Conversation).order_by(models.Conversation.is_pinned.desc(), models.Conversation.updated_at.desc())).scalars().all()
    ch_map = {
      (os.getenv('LINE_CHANNEL_1_DESTINATION','').strip() or os.getenv('LINE_CHANNEL_1_ID','').strip()):1,
      (os.getenv('LINE_CHANNEL_2_DESTINATION','').strip() or os.getenv('LINE_CHANNEL_2_ID','').strip()):2,
      (os.getenv('LINE_CHANNEL_3_DESTINATION','').strip() or os.getenv('LINE_CHANNEL_3_ID','').strip()):3,
    }
    out=[]
    for r in rows:
        ch = db.get(models.LineChannel, r.channel_id) if r.channel_id else None
        ckey = (ch.channel_id if ch else None)
        user = db.get(models.User, r.user_id)
        last_msg = db.execute(
            select(models.Message).where(models.Message.conversation_id == r.id).order_by(models.Message.id.desc()).limit(1)
        ).scalar_one_or_none()
        last_inbound_id = db.execute(
            select(func.max(models.Message.id)).where(models.Message.conversation_id == r.id, models.Message.direction == 'inbound')
        ).scalar_one_or_none() or 0
        last_outbound_id = db.execute(
            select(func.max(models.Message.id)).where(models.Message.conversation_id == r.id, models.Message.direction == 'outbound')
        ).scalar_one_or_none() or 0
        unread = last_inbound_id > (r.last_read_message_id or 0)
        reply_pending = last_inbound_id > last_outbound_id
        preview = (last_msg.body or '')[:10] if last_msg else ''

        out.append({
            'id':r.id,
            'user_id':r.user_id,
            'user_name': (user.display_name if user else None),
            'member_code': (user.member_code if user else None),
            'profile_image_url': (user.profile_image_url if user else None),
            'tag': (user.tag if user else None),
            'status_label': (user.status_label if user else None),
            'support_mark': (user.support_mark if user else None),
            'status':r.status,
            'is_pinned': bool(r.is_pinned),
            'updated_at':str(r.updated_at),
            'channel_id':r.channel_id,
            'channel_name':((ch.official_account_name or ch.name) if ch else None),
            'channel_picture_url': (ch.picture_url if ch else None),
            'channel_key':ckey,
            'channel_slot':(ch_map.get(ckey) if ckey else None),
            'last_message_preview': preview,
            'is_unread': unread,
            'read_status': ('未読' if unread else '既読'),
            'reply_status': ('未返信' if reply_pending else '返信済み'),
        })
    return out


@app.get('/conversations/{conversation_id}/messages')
def list_messages(conversation_id: int, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    conv = db.get(models.Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, 'conversation not found')
    rows = db.execute(select(models.Message).where(models.Message.conversation_id == conversation_id).order_by(models.Message.created_at.asc())).scalars().all()
    last_id = rows[-1].id if rows else 0
    if last_id > (conv.last_read_message_id or 0):
        conv.last_read_message_id = last_id
        db.commit()
    return [{'id':r.id,'direction':r.direction,'source':r.source,'body':r.body,'created_at':str(r.created_at)} for r in rows]


@app.post('/messages')
def create_message(payload: schemas.MessageCreate, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    conv = db.get(models.Conversation, payload.conversation_id)
    if not conv: raise HTTPException(404,'conversation not found')
    row = models.Message(conversation_id=payload.conversation_id, direction='outbound', source=payload.source, message_type='text', body=payload.body)
    db.add(row); db.commit(); db.refresh(row)
    return {'ok':True,'id':row.id}


@app.post('/line/send')
def send_line_message(payload: schemas.LineSendCreate, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    conv = db.get(models.Conversation, payload.conversation_id)
    if not conv: raise HTTPException(404,'conversation not found')
    ident = db.execute(select(models.LineIdentity).where(models.LineIdentity.user_id == conv.user_id)).scalar_one_or_none()
    if not ident: raise HTTPException(400,'line identity not found')
    channel = db.get(models.LineChannel, conv.channel_id) if conv.channel_id else None
    channel_key = channel.channel_id if channel else None
    token = _line_channel_tokens().get(channel_key)
    if not token: raise HTTPException(500, f'line access token not configured for channel: {channel_key}')
    r = httpx.post('https://api.line.me/v2/bot/message/push', headers={'Authorization': f'Bearer {token}','Content-Type':'application/json'}, json={'to': ident.line_user_id, 'messages':[{'type':'text','text':payload.body}]}, timeout=20)
    if r.status_code >= 400: raise HTTPException(400, f'line send failed: {r.text}')
    db.add(models.Message(conversation_id=payload.conversation_id, direction='outbound', source='line', message_type='text', body=payload.body)); db.commit()
    return {'ok':True}


@app.post('/interview/upsert')
def upsert_interview(payload: schemas.InterviewUpsert, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, payload.user_id)
    if not user: raise HTTPException(404,'user not found')
    conv = db.execute(select(models.Conversation).where(models.Conversation.user_id == payload.user_id).order_by(models.Conversation.updated_at.desc())).scalar_one_or_none()
    channel_id = conv.channel_id if conv else None
    row = _get_channel_profile(db, payload.user_id, channel_id, create=True)
    row.desired_work = payload.desired_work; row.available_time = payload.available_time; row.desired_reward = payload.desired_reward; row.experience_level = payload.experience_level; row.notes = payload.notes
    db.commit(); return {'ok':True}


@app.get('/users/{user_id}/profile')
def get_user_profile(user_id: int, conversation_id: int | None = None, channel_id: int | None = None, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, user_id)
    if not user: raise HTTPException(404,'user not found')
    if conversation_id:
        conv = db.get(models.Conversation, conversation_id)
        if conv and conv.user_id == user_id:
            channel_id = conv.channel_id
    if channel_id is None:
        latest = db.execute(select(models.Conversation).where(models.Conversation.user_id == user_id).order_by(models.Conversation.updated_at.desc())).scalar_one_or_none()
        channel_id = latest.channel_id if latest else None
    profile = _get_channel_profile(db, user_id, channel_id, create=False)
    if not profile:
        profile = db.execute(select(models.ChannelInterviewProfile).where(models.ChannelInterviewProfile.user_id == user_id).order_by(models.ChannelInterviewProfile.updated_at.desc())).scalar_one_or_none()
    if not profile:
        legacy = db.execute(select(models.InterviewProfile).where(models.InterviewProfile.user_id == user_id)).scalar_one_or_none()
        if legacy:
            class O: pass
            profile = O()
            profile.desired_work = legacy.desired_work
            profile.available_time = legacy.available_time
            profile.desired_reward = legacy.desired_reward
            profile.experience_level = legacy.experience_level
            profile.notes = legacy.notes
    return {'user':{'id':user.id,'member_code': user.member_code,'role':user.role,'display_name':user.display_name,'email':user.email,'profile_image_url': user.profile_image_url,'age': user.age,'gender': user.gender,'phone_number': user.phone_number,'registered_at': (str(user.registered_at) if user.registered_at else None),'initial_tag': user.initial_tag,'referral_code': user.referral_code,'referral_link': f"https://line-template.top/r/{user.referral_code}" if user.referral_code else None,'referral_last_sent_at': (str(user.referral_last_sent_at) if user.referral_last_sent_at else None),'tag': user.tag,'status_label': user.status_label,'support_mark': user.support_mark,'acquisition_source': user.acquisition_source,'created_at':str(user.created_at)}, 'interview':{'desired_work':(profile.desired_work if profile else None),'available_time':(profile.available_time if profile else None),'desired_reward':(profile.desired_reward if profile else None),'experience_level':(profile.experience_level if profile else None),'notes':(profile.notes if profile else None), 'survey_answers': (profile.survey_answers if profile else None), 'survey_completed_at': (str(profile.survey_completed_at) if (profile and profile.survey_completed_at) else None)}}


@app.post('/users/{user_id}/memo')
def save_user_memo(user_id: int, payload: schemas.MemoUpdate, conversation_id: int | None = None, channel_id: int | None = None, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, user_id)
    if not user: raise HTTPException(404,'user not found')
    if conversation_id:
        conv = db.get(models.Conversation, conversation_id)
        if conv and conv.user_id == user_id:
            channel_id = conv.channel_id
    if channel_id is None:
        latest = db.execute(select(models.Conversation).where(models.Conversation.user_id == user_id).order_by(models.Conversation.updated_at.desc())).scalar_one_or_none()
        channel_id = latest.channel_id if latest else None
    profile = _get_channel_profile(db, user_id, channel_id, create=True)
    profile.notes = payload.notes; db.commit(); return {'ok':True}


@app.post('/users/{user_id}/attributes')
def save_user_attributes(user_id: int, payload: schemas.UserAttributesUpdate, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404,'user not found')
    user.tag = payload.tag
    user.status_label = payload.status_label
    user.support_mark = payload.support_mark
    db.commit()
    return {'ok': True}


@app.post('/line/channels/sync')
def sync_line_channels(db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    token_map = _line_channel_tokens()
    out = []
    for channel_key, token in token_map.items():
        if not channel_key or not token:
            continue
        ch = db.execute(select(models.LineChannel).where(models.LineChannel.channel_id == channel_key)).scalar_one_or_none()
        if not ch:
            ch = models.LineChannel(name=f'LINE-{channel_key[-6:]}', channel_id=channel_key, destination_id=channel_key)
            db.add(ch)
            db.flush()

        try:
            info_res = httpx.get('https://api.line.me/v2/bot/info', headers={'Authorization': f'Bearer {token}'}, timeout=15)
            if info_res.status_code < 400:
                info = info_res.json()
                display = info.get('displayName')
                if display:
                    ch.official_account_name = display
                    ch.name = display
                if info.get('pictureUrl'):
                    ch.picture_url = info.get('pictureUrl')
                if info.get('statusMessage'):
                    ch.status_message = info.get('statusMessage')
                if info.get('basicId'):
                    ch.basic_id = info.get('basicId')
                if info.get('userId'):
                    uid = info.get('userId')
                    ch.destination_id = uid
                    if ch.channel_id != uid:
                        # avoid duplicate unique key collision: if another row already has uid, merge to it
                        exists_uid = db.execute(select(models.LineChannel).where(models.LineChannel.channel_id == uid)).scalar_one_or_none()
                        if exists_uid and exists_uid.id != ch.id:
                            # keep existing uid row as canonical, copy latest metadata into it
                            exists_uid.name = (display or exists_uid.name)
                            exists_uid.official_account_name = (display or exists_uid.official_account_name)
                            exists_uid.picture_url = (info.get('pictureUrl') or exists_uid.picture_url)
                            exists_uid.status_message = (info.get('statusMessage') or exists_uid.status_message)
                            exists_uid.destination_id = uid
                            ch.is_active = 0
                            ch.name = f"{ch.name}-merged"
                        else:
                            ch.channel_id = uid
        except Exception:
            pass

        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS lp_saved_links (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    folder_name VARCHAR(120) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    url VARCHAR(1024) NOT NULL,
                    note TEXT NULL,
                    is_active INT NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_folder (folder_name),
                    INDEX idx_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
        except Exception:
            pass
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS lp_message_templates (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    folder_name VARCHAR(120) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    body TEXT NOT NULL,
                    url VARCHAR(1024) NULL,
                    is_active INT NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_folder (folder_name),
                    INDEX idx_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
        except Exception:
            pass
        try:
            # follower count endpoint requires target date (yyyyMMdd), use today JST-ish by local date
            date_str = datetime.now().strftime('%Y%m%d')
            fc_res = httpx.get(f'https://api.line.me/v2/bot/insight/followers?date={date_str}', headers={'Authorization': f'Bearer {token}'}, timeout=15)
            if fc_res.status_code < 400:
                fc = fc_res.json()
                if isinstance(fc.get('followers'), int):
                    ch.follower_count = fc.get('followers')
        except Exception:
            pass

        ch.last_synced_at = datetime.now()
        out.append({'channel_id': ch.channel_id, 'name': (ch.official_account_name or ch.name), 'destination_id': ch.destination_id, 'follower_count': ch.follower_count})

    db.commit()
    return {'ok': True, 'count': len(out), 'channels': out}


@app.get('/line/channels')
def list_line_channels(db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    rows = db.execute(select(models.LineChannel).order_by(models.LineChannel.id.asc())).scalars().all()
    webhook_url = os.getenv('LINE_WEBHOOK_URL','').strip() or 'https://line-template.top/webhooks/line'
    provider_name = os.getenv('LINE_PROVIDER_NAME','LINE Messaging API')
    friend_map = {}
    for i in (1,2,3):
        key = (os.getenv(f'LINE_CHANNEL_{i}_DESTINATION','').strip() or os.getenv(f'LINE_CHANNEL_{i}_ID','').strip())
        furl = os.getenv(f'LINE_CHANNEL_{i}_FRIEND_ADD_URL','').strip()
        if key and furl:
            friend_map[key] = furl
    return [
        {
            'id': r.id,
            'channel_id': r.channel_id,
            'destination_id': r.destination_id,
            'bot_id': (r.destination_id or r.channel_id),
            'name': (r.official_account_name or r.name),
            'picture_url': r.picture_url,
            'status_message': r.status_message,
            'basic_id': r.basic_id,
            'follower_count': r.follower_count,
            'last_synced_at': str(r.last_synced_at) if r.last_synced_at else None,
            'is_active': r.is_active,
            'provider': 'line',
            'provider_name': provider_name,
            'webhook_url': webhook_url,
            'official_line_url': friend_map.get(r.channel_id) or friend_map.get(r.destination_id) or (f"https://line.me/R/ti/p/{r.basic_id}" if r.basic_id else None),
        }
        for r in rows
    ]


@app.post('/users/registration/upsert')
def upsert_registration(payload: schemas.RegistrationUpsert, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, payload.user_id)
    if not user:
        raise HTTPException(404,'user not found')
    _ensure_user_codes(db, user)
    if payload.name:
        user.display_name = payload.name
    if payload.age is not None:
        user.age = payload.age
    if payload.gender in (None, '男性', '女性', '未回答'):
        user.gender = payload.gender
    if payload.phone_number is not None:
        user.phone_number = payload.phone_number
    if payload.initial_tag is not None:
        user.initial_tag = payload.initial_tag
        user.tag = payload.initial_tag
    if not user.registered_at:
        user.registered_at = datetime.now()
    db.commit()
    return {'ok': True, 'user_id': user.id, 'member_code': user.member_code, 'referral_code': user.referral_code}


@app.get('/r/{ref_code}', response_class=HTMLResponse)
def referral_redirect(ref_code: str, line_user_id: str | None = None, ch: int | None = None, db: Session = Depends(get_db)):
    owner = db.execute(select(models.User).where(models.User.referral_code == ref_code)).scalar_one_or_none()
    db.add(models.ReferralEvent(ref_code=ref_code, referrer_user_id=(owner.id if owner else None), line_user_id=line_user_id, event_type='click', raw_payload={'ch': ch}))
    db.commit()

    target = f"{_affiliate_base_url(ch)}?ref={ref_code}"
    wait_sec = int(os.getenv('REFERRAL_THANKS_WAIT_SEC', '2'))
    img_url = os.getenv('REFERRAL_THANKS_IMAGE_URL', 'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=900&q=60')
    html = f"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>ご案内中…</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1020;color:#e5e7eb;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
.card{{width:min(92vw,520px);background:#111827;border:1px solid #1f2937;border-radius:14px;padding:20px;text-align:center}}
img{{max-width:100%;border-radius:10px;margin:10px 0}}
a.btn{{display:inline-block;margin-top:12px;padding:10px 14px;border-radius:10px;background:#14532d;color:#fff;text-decoration:none}}
.small{{color:#94a3b8;font-size:12px;margin-top:8px}}
</style>
</head><body>
  <div class="card">
    <h3>ご紹介ありがとうございます</h3>
    <p>公式LINEへ移動します。しばらくお待ちください…</p>
    <img src="{img_url}" alt="thanks" />
    <div><a class="btn" href="{target}">すぐに進む</a></div>
    <div class="small">{wait_sec}秒後に自動で移動します</div>
  </div>
<script>setTimeout(function(){{ location.href = {target!r}; }}, {wait_sec}*1000);</script>
</body></html>"""
    return HTMLResponse(content=html)


@app.post('/rewards/credit')
def credit_reward(user_id: int | None = None, registration_id: int | None = None, channel_key: str | None = None, amount: int = 0, note: str = '', api_key: str = Header(default=''), db: Session = Depends(get_db)):
    expected = os.getenv('PARTNER_API_KEY', '').strip()
    if expected and api_key != expected:
        raise HTTPException(401, 'invalid api key')
    if amount == 0:
        raise HTTPException(422, 'amount must not be 0')

    ledger = models.RewardLedger(
        user_id=user_id,
        registration_id=registration_id,
        channel_key=((channel_key or '').lower().strip() or None),
        amount=amount,
        note=(note or '').strip() or None,
    )
    db.add(ledger)
    db.commit()
    db.refresh(ledger)

    total = None
    if registration_id:
        total = db.execute(
            select(func.coalesce(func.sum(models.RewardLedger.amount), 0)).where(models.RewardLedger.registration_id == registration_id)
        ).scalar_one() or 0

    return {'ok': True, 'ledger_id': ledger.id, 'user_id': user_id, 'registration_id': registration_id, 'channel_key': ledger.channel_key, 'amount': amount, 'note': note, 'registration_reward_total': (int(total) if total is not None else None)}


@app.get('/survey/templates')
def get_survey_templates(admin: models.AdminUser = Depends(current_admin)):
    return {
        'library': _load_survey_library(),
        'categories': _load_survey_templates(),
    }


@app.post('/survey/templates')
def save_survey_templates(payload: dict, admin: models.AdminUser = Depends(current_admin)):
    cats = payload.get('categories') or {}
    out = {}
    for k in ('side', 'estate', 'ai'):
        arr = cats.get(k) or []
        cleaned = []
        for i, q in enumerate(arr, start=1):
            q_key = str(q.get('key') or f'q{i}').strip() or f'q{i}'
            q_text = str(q.get('q') or f'Q{i}: 質問を入力してください。').strip()
            q_type = str(q.get('type') or 'single').strip()
            options = [str(o).strip() for o in (q.get('options') or []) if str(o).strip()]
            if q_type == 'text':
                options = ['自由入力']
            elif not options:
                options = ['はい', 'いいえ']
            cleaned.append({'key': q_key, 'q': q_text, 'options': options, 'type': q_type})
        out[k] = cleaned
    _save_survey_templates(out)
    return {'ok': True, 'saved': {k: len(v) for k, v in out.items()}}


@app.post('/survey/library')
def save_survey_library(payload: dict, admin: models.AdminUser = Depends(current_admin)):
    items = payload.get('items') or []
    _save_survey_library(items)
    return {'ok': True, 'count': len(_load_survey_library())}


@app.post('/users/{user_id}/survey/start')
def start_user_survey(user_id: int, conversation_id: int, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, 'user not found')
    conv, ident, ch, token = _get_identity_by_conversation(db, conversation_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(400, 'conversation/user mismatch')
    if not ident or not token:
        raise HTTPException(400, 'line identity/token not found for conversation channel')
    st = db.execute(select(models.OnboardingState).where(models.OnboardingState.user_id == user_id)).scalar_one_or_none()
    if not st:
        st = models.OnboardingState(user_id=user_id, step=100)
        db.add(st)
    else:
        st.step = 100
    conv = _get_or_create_conv(db, user_id, ch.id if ch else None)
    msg = 'ご登録ありがとうございます。登録アンケートを開始しますか？「はい」で開始できます。'
    ok = _line_push_text(token, ident.line_user_id, msg)
    if ok:
        db.add(models.Message(conversation_id=conv.id, direction='outbound', source='line', message_type='text', body=msg))
    db.commit()
    return {'ok': ok}


@app.post('/users/{user_id}/survey/start-template')
def start_user_survey_template(user_id: int, payload: schemas.SurveyStartIn, conversation_id: int, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, 'user not found')
    conv, ident, ch, token = _get_identity_by_conversation(db, conversation_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(400, 'conversation/user mismatch')
    if not ident or not token:
        raise HTTPException(400, 'line identity/token not found for conversation channel')
    st = db.execute(select(models.OnboardingState).where(models.OnboardingState.user_id == user_id)).scalar_one_or_none()
    if not st:
        st = models.OnboardingState(user_id=user_id, step=100)
        db.add(st)
    else:
        st.step = 100
    conv = _get_or_create_conv(db, user_id, ch.id if ch else None)
    base_msg = payload.message or 'ご登録ありがとうございます。登録アンケートを開始しますか？'
    prof = db.execute(select(models.ChannelInterviewProfile).where(models.ChannelInterviewProfile.user_id == user_id).order_by(models.ChannelInterviewProfile.updated_at.desc()).limit(1)).scalar_one_or_none()
    msg = _render_template_text(base_msg, user, prof, (ch.official_account_name or ch.name) if ch else None)
    ok = _line_push_buttons(token, ident.line_user_id, msg, ['はい','いいえ'])
    if ok:
        db.add(models.Message(conversation_id=conv.id, direction='outbound', source='line', message_type='text', body=msg + '\n選択肢: はい / いいえ'))
    db.commit()
    return {'ok': ok}


@app.post('/users/{user_id}/send-referral-link')
def send_referral_link(user_id: int, conversation_id: int, channel_slot: int | None = None, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, 'user not found')
    _ensure_user_codes(db, user)
    conv, ident, ch, token = _get_identity_by_conversation(db, conversation_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(400, 'conversation/user mismatch')
    if not ident or not token:
        raise HTTPException(400, 'line identity/token not found for conversation channel')
    conv = _get_or_create_conv(db, user_id, ch.id if ch else None)
    # resolve channel slot from conversation channel key when not provided
    if channel_slot not in (1,2,3):
        ch_map = {
            (os.getenv('LINE_CHANNEL_1_DESTINATION','').strip() or os.getenv('LINE_CHANNEL_1_ID','').strip()):1,
            (os.getenv('LINE_CHANNEL_2_DESTINATION','').strip() or os.getenv('LINE_CHANNEL_2_ID','').strip()):2,
            (os.getenv('LINE_CHANNEL_3_DESTINATION','').strip() or os.getenv('LINE_CHANNEL_3_ID','').strip()):3,
        }
        channel_slot = ch_map.get((ch.channel_id if ch else None))

    link = f'https://line-template.top/r/{user.referral_code}' + (f'?ch={channel_slot}' if channel_slot in (1,2,3) else '')
    msg = f'あなたの紹介リンクです。お友だち紹介にご利用ください。\n{link}'
    ok = _line_push_text(token, ident.line_user_id, msg)
    if ok:
        db.add(models.Message(conversation_id=conv.id, direction='outbound', source='line', message_type='text', body=msg))
        user.referral_last_sent_at = datetime.now()

    # also store to saved links registry for visibility/reuse
    try:
        db.add(models.SavedLink(
            folder_name='紹介リンク',
            title=f"{(user.display_name or ('USER'+str(user.id)))} / CH{channel_slot or '-'}",
            url=link,
            note=f"referral_code={user.referral_code}",
            is_active=1,
        ))
    except Exception:
        pass

    db.commit()
    return {'ok': ok, 'referral_link': link, 'last_sent_at': (str(user.referral_last_sent_at) if user.referral_last_sent_at else None), 'channel_slot': channel_slot}


@app.get('/templates')
def list_templates(active_only: int = 1, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    q = select(models.MessageTemplate)
    if active_only == 1:
        q = q.where(models.MessageTemplate.is_active == 1)
    rows = db.execute(q.order_by(models.MessageTemplate.folder_name.asc(), models.MessageTemplate.id.desc())).scalars().all()
    out=[]
    for r in rows:
        msg = r.body + (f"\n{r.url}" if r.url else "")
        out.append({
            'id': r.id,
            'folder_name': r.folder_name,
            'title': r.title,
            'body': r.body,
            'url': r.url,
            'message': msg,
            'is_active': r.is_active,
            'created_at': str(r.created_at),
        })
    return out


@app.post('/templates')
def create_template(payload: schemas.TemplateCreateIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = models.MessageTemplate(
        folder_name=payload.folder_name.strip(),
        title=payload.title.strip(),
        body=payload.body.strip(),
        url=(payload.url.strip() if payload.url else None),
        transition_tag=(payload.transition_tag.strip() if payload.transition_tag else None),
        transition_status_label=(payload.transition_status_label.strip() if payload.transition_status_label else None),
        transition_support_mark=(payload.transition_support_mark.strip() if payload.transition_support_mark else None),
        is_active=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'ok': True, 'id': row.id}

@app.post('/templates/from-message')
def create_template_from_message(payload: schemas.TemplateFromMessageIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    m = db.get(models.Message, payload.message_id)
    if not m:
        raise HTTPException(404, 'message not found')
    body = (m.body or '').strip()
    if not body:
        raise HTTPException(400, 'message body empty')
    row = models.MessageTemplate(
        folder_name=payload.folder_name.strip(),
        title=payload.title.strip(),
        body=body,
        url=(payload.url.strip() if payload.url else None),
        transition_tag=(payload.transition_tag.strip() if payload.transition_tag else None),
        transition_status_label=(payload.transition_status_label.strip() if payload.transition_status_label else None),
        transition_support_mark=(payload.transition_support_mark.strip() if payload.transition_support_mark else None),
        is_active=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'ok': True, 'id': row.id}


@app.get('/links')
def list_links(active_only: int = 1, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    q = select(models.SavedLink)
    if active_only == 1:
        q = q.where(models.SavedLink.is_active == 1)
    rows = db.execute(q.order_by(models.SavedLink.folder_name.asc(), models.SavedLink.id.desc())).scalars().all()
    return [
        {
            'id': r.id,
            'folder_name': r.folder_name,
            'title': r.title,
            'url': r.url,
            'note': r.note,
            'is_active': r.is_active,
            'created_at': str(r.created_at),
        }
        for r in rows
    ]


@app.post('/links')
def create_link(payload: schemas.SavedLinkCreateIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = models.SavedLink(
        folder_name=payload.folder_name.strip(),
        title=payload.title.strip(),
        url=payload.url.strip(),
        note=(payload.note.strip() if payload.note else None),
        is_active=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'ok': True, 'id': row.id}


@app.get('/users')
def list_users(db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    rows = db.execute(select(models.User).order_by(models.User.id.desc())).scalars().all()
    out=[]
    for u in rows:
        conv_count = db.execute(select(func.count(models.Conversation.id)).where(models.Conversation.user_id == u.id)).scalar_one() or 0
        latest_conv = db.execute(select(models.Conversation).where(models.Conversation.user_id == u.id).order_by(models.Conversation.updated_at.desc()).limit(1)).scalar_one_or_none()
        ch = db.get(models.LineChannel, latest_conv.channel_id) if latest_conv and latest_conv.channel_id else None
        out.append({
            'id': u.id,
            'member_code': u.member_code,
            'display_name': u.display_name,
            'profile_image_url': u.profile_image_url,
            'age': u.age,
            'gender': u.gender,
            'phone_number': u.phone_number,
            'tag': u.tag,
            'status_label': u.status_label,
            'support_mark': u.support_mark,
            'acquisition_source': u.acquisition_source,
            'registered_at': str(u.registered_at) if u.registered_at else None,
            'created_at': str(u.created_at),
            'conversation_count': int(conv_count),
            'latest_channel_name': (ch.official_account_name or ch.name) if ch else None,
        })
    return out


@app.get('/users/{user_id}/detail')
def get_user_detail(user_id: int, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, 'user not found')
    identities = db.execute(select(models.LineIdentity).where(models.LineIdentity.user_id == user_id)).scalars().all()
    channels = []
    for i in identities:
        ch = db.get(models.LineChannel, i.channel_id) if i.channel_id else None
        channels.append({
            'line_user_id': i.line_user_id,
            'channel_id': i.channel_id,
            'channel_name': (ch.official_account_name or ch.name) if ch else None,
        })

    profiles = db.execute(select(models.ChannelInterviewProfile).where(models.ChannelInterviewProfile.user_id == user_id).order_by(models.ChannelInterviewProfile.updated_at.desc())).scalars().all()
    p = profiles[0] if profiles else None
    profile_rows = []
    for pr in profiles:
        ch = db.get(models.LineChannel, pr.channel_id) if pr.channel_id else None
        profile_rows.append({
            'channel_id': pr.channel_id,
            'channel_name': (ch.official_account_name or ch.name) if ch else '未紐付け',
            'desired_work': pr.desired_work,
            'available_time': pr.available_time,
            'desired_reward': pr.desired_reward,
            'experience_level': pr.experience_level,
            'notes': pr.notes,
        })

    return {
        'user': {
            'id': user.id,
            'member_code': user.member_code,
            'display_name': user.display_name,
            'email': user.email,
            'profile_image_url': user.profile_image_url,
            'age': user.age,
            'gender': user.gender,
            'phone_number': user.phone_number,
            'registered_at': str(user.registered_at) if user.registered_at else None,
            'initial_tag': user.initial_tag,
            'tag': user.tag,
            'status_label': user.status_label,
            'support_mark': user.support_mark,
            'acquisition_source': user.acquisition_source,
            'referral_code': user.referral_code,
            'referral_link': f'https://line-template.top/r/{user.referral_code}' if user.referral_code else None,
            'referral_last_sent_at': str(user.referral_last_sent_at) if user.referral_last_sent_at else None,
            'created_at': str(user.created_at),
        },
        'interview': {
            'desired_work': (p.desired_work if p else None),
            'available_time': (p.available_time if p else None),
            'desired_reward': (p.desired_reward if p else None),
            'experience_level': (p.experience_level if p else None),
            'notes': (p.notes if p else None),
            'survey_answers': (p.survey_answers if p else None),
            'survey_completed_at': (str(p.survey_completed_at) if (p and p.survey_completed_at) else None),
        },
        'channel_profiles': profile_rows,
        'channels': channels,
    }


@app.post('/users/{user_id}/detail')
def save_user_detail(user_id: int, payload: dict, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, 'user not found')
    user.display_name = payload.get('display_name', user.display_name)
    user.email = payload.get('email', user.email)
    user.age = payload.get('age', user.age)
    user.gender = payload.get('gender', user.gender)
    user.phone_number = payload.get('phone_number', user.phone_number)
    user.initial_tag = payload.get('initial_tag', user.initial_tag)
    user.tag = payload.get('tag', user.tag)
    user.status_label = payload.get('status_label', user.status_label)
    if not user.registered_at and payload.get('registered_at'):
        try:
            user.registered_at = datetime.fromisoformat(payload.get('registered_at'))
        except Exception:
            pass

    # save selected channel profile (or latest as fallback)
    target_channel_id = payload.get('channel_id', None)
    if target_channel_id is not None:
        prof = db.execute(select(models.ChannelInterviewProfile).where(
            models.ChannelInterviewProfile.user_id == user_id,
            models.ChannelInterviewProfile.channel_id == target_channel_id,
        )).scalar_one_or_none()
        if not prof:
            prof = models.ChannelInterviewProfile(user_id=user_id, channel_id=target_channel_id)
            db.add(prof)
    else:
        prof = db.execute(select(models.ChannelInterviewProfile).where(models.ChannelInterviewProfile.user_id == user_id).order_by(models.ChannelInterviewProfile.updated_at.desc()).limit(1)).scalar_one_or_none()
        if not prof:
            prof = models.ChannelInterviewProfile(user_id=user_id, channel_id=None)
            db.add(prof)

    prof.desired_work = payload.get('desired_work', prof.desired_work)
    prof.available_time = payload.get('available_time', prof.available_time)
    prof.desired_reward = payload.get('desired_reward', prof.desired_reward)
    prof.experience_level = payload.get('experience_level', prof.experience_level)
    prof.notes = payload.get('notes', prof.notes)

    db.commit()
    return {'ok': True}


@app.post('/line/channels/add')
def add_line_channel(payload: schemas.LineChannelCreateIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    slot = payload.slot or _next_channel_slot_from_env()
    if slot not in (1,2,3):
        raise HTTPException(400, 'slot must be 1..3')

    channel_id = (payload.channel_id or '').strip()
    channel_secret = (payload.channel_secret or '').strip()
    access_token = (payload.access_token or '').strip()
    if not channel_id or not channel_secret or not access_token:
        raise HTTPException(400, 'channel_id/channel_secret/access_token are required')

    auto_name = None
    auto_dest = None
    try:
        info_res = httpx.get('https://api.line.me/v2/bot/info', headers={'Authorization': f'Bearer {access_token}'}, timeout=15)
        if info_res.status_code < 400:
            info = info_res.json()
            auto_name = info.get('displayName')
            auto_dest = info.get('userId')
    except Exception:
        pass

    destination_id = ((payload.destination_id or '').strip() or (auto_dest or '')).strip()
    if not destination_id:
        raise HTTPException(400, 'destination_id could not be resolved; set BOT ID or use valid token')

    display_name = ((payload.name or '').strip() or (auto_name or '')).strip()
    business_type = (payload.business_type or '').strip() or None
    if not display_name:
        display_name = f'LINE-{destination_id[-6:]}'

    updates = {
        f'LINE_CHANNEL_{slot}_ID': channel_id,
        f'LINE_CHANNEL_{slot}_DESTINATION': destination_id,
        f'LINE_CHANNEL_{slot}_SECRET': channel_secret,
        f'LINE_CHANNEL_{slot}_ACCESS_TOKEN': access_token,
    }
    if payload.friend_add_url:
        updates[f'LINE_CHANNEL_{slot}_FRIEND_ADD_URL'] = payload.friend_add_url.strip()

    _update_env_file(updates)

    row = db.execute(select(models.LineChannel).where(models.LineChannel.channel_id == destination_id)).scalar_one_or_none()
    if not row:
        row = models.LineChannel(
            name=display_name,
            channel_id=destination_id,
            destination_id=destination_id,
            official_account_name=display_name,
            business_type=business_type,
            is_active=1,
        )
        db.add(row)
    else:
        row.name = display_name
        row.official_account_name = display_name
        row.destination_id = destination_id
        row.business_type = business_type
    db.commit()

    return {'ok': True, 'slot': slot, 'resolved_name': display_name, 'resolved_destination_id': destination_id, 'restart_required': True}


@app.post('/ops/restart-services')
def restart_services(admin: models.AdminUser = Depends(current_admin)):
    try:
        subprocess.Popen([
            'bash','-lc',
            '(sleep 1; systemctl restart line-template-api.service; systemctl restart line-template-ui.service) >/tmp/line-template-restart.log 2>&1 &'
        ])
        return {'ok': True, 'scheduled': True}
    except Exception as e:
        raise HTTPException(500, f'restart failed: {e}')


@app.post('/links/{link_id}/delete')
def delete_link(link_id: int, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = db.get(models.SavedLink, link_id)
    if not row:
        raise HTTPException(404, 'link not found')
    db.delete(row)
    db.commit()
    return {'ok': True}


@app.post('/conversations/{conversation_id}/pin')
def pin_conversation(conversation_id: int, value: int = 1, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    conv = db.get(models.Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, 'conversation not found')
    conv.is_pinned = 1 if int(value) == 1 else 0
    db.commit()
    return {'ok': True, 'conversation_id': conversation_id, 'is_pinned': bool(conv.is_pinned)}

@app.post('/templates/preview')
def preview_template(payload: schemas.TemplatePreviewIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    conv = db.get(models.Conversation, payload.conversation_id)
    if not conv:
        raise HTTPException(404, 'conversation not found')
    user = db.get(models.User, conv.user_id)
    if not user:
        raise HTTPException(404, 'user not found')
    profile = _get_channel_profile(db, user.id, conv.channel_id, create=False)
    ch = db.get(models.LineChannel, conv.channel_id) if conv.channel_id else None
    rendered = _render_template_text(payload.body or '', user, profile, (ch.official_account_name or ch.name) if ch else None)
    unresolved = sorted(set(re.findall(r'\{\{[A-Z0-9_]+\}\}', rendered or '')))
    return {'ok': True, 'rendered': rendered, 'unresolved': unresolved}


@app.post('/line/channels/{line_channel_id}/hide')
def hide_line_channel(line_channel_id: int, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = db.get(models.LineChannel, line_channel_id)
    if not row:
        raise HTTPException(404, 'channel not found')
    row.is_active = 0
    db.commit()
    return {'ok': True}


@app.post('/line/channels/{line_channel_id}/unhide')
def unhide_line_channel(line_channel_id: int, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = db.get(models.LineChannel, line_channel_id)
    if not row:
        raise HTTPException(404, 'channel not found')
    row.is_active = 1
    db.commit()
    return {'ok': True}


@app.post('/line/channels/merge')
def merge_line_channels(payload: schemas.ChannelMergeIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    src = db.get(models.LineChannel, payload.from_channel_id)
    dst = db.get(models.LineChannel, payload.to_channel_id)
    if not src or not dst:
        raise HTTPException(404, 'channel not found')
    if src.id == dst.id:
        raise HTTPException(400, 'from/to must be different')

    db.execute(text('UPDATE lp_conversations SET channel_id=:to_id WHERE channel_id=:from_id'), {'to_id': dst.id, 'from_id': src.id})
    db.execute(text('UPDATE lp_line_identities SET channel_id=:to_id WHERE channel_id=:from_id'), {'to_id': dst.id, 'from_id': src.id})

    src_profiles = db.execute(select(models.ChannelInterviewProfile).where(models.ChannelInterviewProfile.channel_id == src.id)).scalars().all()
    for sp in src_profiles:
        exists = db.execute(select(models.ChannelInterviewProfile).where(
            models.ChannelInterviewProfile.user_id == sp.user_id,
            models.ChannelInterviewProfile.channel_id == dst.id,
        )).scalar_one_or_none()
        if exists:
            exists.desired_work = exists.desired_work or sp.desired_work
            exists.available_time = exists.available_time or sp.available_time
            exists.desired_reward = exists.desired_reward or sp.desired_reward
            exists.experience_level = exists.experience_level or sp.experience_level
            exists.notes = exists.notes or sp.notes
            db.delete(sp)
        else:
            sp.channel_id = dst.id

    if payload.deactivate_from:
        src.is_active = 0
    db.commit()
    return {'ok': True, 'from_channel': src.id, 'to_channel': dst.id}


@app.get('/ops/thanks-config')
def get_thanks_config(admin: models.AdminUser = Depends(current_admin)):
    image_url = os.getenv('REFERRAL_THANKS_IMAGE_URL', '').strip()
    wait_sec = int(os.getenv('REFERRAL_THANKS_WAIT_SEC', '2') or '2')
    return {'ok': True, 'image_url': image_url, 'wait_sec': wait_sec}


@app.post('/ops/thanks-config')
def save_thanks_config(payload: schemas.ThanksConfigIn, admin: models.AdminUser = Depends(current_admin)):
    updates = {}
    if payload.image_url is not None:
        updates['REFERRAL_THANKS_IMAGE_URL'] = payload.image_url.strip()
    if payload.wait_sec is not None:
        if payload.wait_sec < 0 or payload.wait_sec > 60:
            raise HTTPException(400, 'wait_sec must be 0..60')
        updates['REFERRAL_THANKS_WAIT_SEC'] = str(payload.wait_sec)
    if not updates:
        raise HTTPException(400, 'no update fields')
    _update_env_file(updates)
    return {'ok': True, 'updated': updates, 'restart_required': True}


@app.get('/template-folders')
def list_template_folders(active_only: int = 1, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    q = select(models.TemplateFolder)
    if active_only == 1:
        q = q.where(models.TemplateFolder.is_active == 1)
    rows = db.execute(q.order_by(models.TemplateFolder.folder_name.asc())).scalars().all()
    return [
        {
            'id': r.id,
            'folder_name': r.folder_name,
            'folder_type': r.folder_type,
            'fixed_channel_name': r.fixed_channel_name,
            'is_active': r.is_active,
            'created_at': str(r.created_at),
        }
        for r in rows
    ]


@app.post('/template-folders')
def create_template_folder(payload: schemas.TemplateFolderCreateIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    raw_name = (payload.folder_name or '').strip()
    if not raw_name:
        raise HTTPException(400, 'folder_name is required')
    folder_type = (payload.folder_type or 'shared').strip().lower()
    if folder_type not in ('shared', 'fixed'):
        raise HTTPException(400, 'folder_type must be shared/fixed')

    fixed_channel_name = (payload.fixed_channel_name or '').strip() or None
    if folder_type == 'fixed' and not fixed_channel_name:
        raise HTTPException(400, 'fixed_channel_name is required for fixed folder')

    full_name = f"共有/{raw_name}" if folder_type == 'shared' else f"固定/{fixed_channel_name}/{raw_name}"
    exists = db.execute(select(models.TemplateFolder).where(models.TemplateFolder.folder_name == full_name)).scalar_one_or_none()
    if exists:
        return {'ok': True, 'id': exists.id, 'folder_name': exists.folder_name, 'already_exists': True}

    row = models.TemplateFolder(
        folder_name=full_name,
        folder_type=folder_type,
        fixed_channel_name=fixed_channel_name,
        is_active=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'ok': True, 'id': row.id, 'folder_name': row.folder_name, 'folder_type': row.folder_type, 'fixed_channel_name': row.fixed_channel_name}


@app.post('/templates/{template_id}/update')
def update_template(template_id: int, payload: schemas.TemplateUpdateIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = db.get(models.MessageTemplate, template_id)
    if not row:
        raise HTTPException(404, 'template not found')
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.body is not None:
        row.body = payload.body
    if payload.url is not None:
        row.url = payload.url.strip() or None
    if payload.transition_tag is not None:
        row.transition_tag = (payload.transition_tag or '').strip() or None
    if payload.transition_status_label is not None:
        row.transition_status_label = (payload.transition_status_label or '').strip() or None
    if payload.transition_support_mark is not None:
        row.transition_support_mark = (payload.transition_support_mark or '').strip() or None
    db.commit()
    return {'ok': True, 'id': row.id}


@app.post('/template-folders/{folder_id}/rename')
def rename_template_folder(folder_id: int, payload: schemas.TemplateFolderRenameIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = db.get(models.TemplateFolder, folder_id)
    if not row:
        raise HTTPException(404, 'folder not found')
    new_raw = (payload.new_folder_name or '').strip()
    if not new_raw:
        raise HTTPException(400, 'new_folder_name is required')

    folder_type = (payload.folder_type or row.folder_type or 'shared').strip().lower()
    fixed_channel = (payload.fixed_channel_name or row.fixed_channel_name or '').strip() or None
    if folder_type not in ('shared', 'fixed'):
        raise HTTPException(400, 'folder_type must be shared/fixed')
    if folder_type == 'fixed' and not fixed_channel:
        raise HTTPException(400, 'fixed_channel_name is required for fixed folder')

    new_full = f"共有/{new_raw}" if folder_type == 'shared' else f"固定/{fixed_channel}/{new_raw}"
    dup = db.execute(select(models.TemplateFolder).where(models.TemplateFolder.folder_name == new_full, models.TemplateFolder.id != row.id)).scalar_one_or_none()
    if dup:
        raise HTTPException(400, 'folder already exists')

    old_full = row.folder_name
    row.folder_name = new_full
    row.folder_type = folder_type
    row.fixed_channel_name = fixed_channel

    # move linked templates to new folder name
    db.execute(text('UPDATE lp_message_templates SET folder_name=:new_name WHERE folder_name=:old_name'), {'new_name': new_full, 'old_name': old_full})
    db.commit()
    return {'ok': True, 'id': row.id, 'folder_name': row.folder_name}


@app.post('/line/channels/{line_channel_id}/type')
def set_line_channel_type(line_channel_id: int, business_type: str, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = db.get(models.LineChannel, line_channel_id)
    if not row:
        raise HTTPException(404, 'channel not found')
    v=(business_type or '').strip()
    if v not in ('sidejob','material',''):
        raise HTTPException(400, 'business_type must be sidejob/material')
    row.business_type = (v or None)
    db.commit()
    return {'ok': True, 'id': row.id, 'business_type': row.business_type}


@app.get('/products')
def list_products(active_only: int = 1, business_type: str | None = None, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    q = select(models.ProductItem)
    if active_only == 1:
        q = q.where(models.ProductItem.is_active == 1)
    if business_type:
        q = q.where(models.ProductItem.business_type == business_type)
    rows = db.execute(q.order_by(models.ProductItem.id.desc())).scalars().all()
    return [{'id': r.id, 'business_type': r.business_type, 'name': r.name, 'price': r.price, 'description': r.description, 'purchase_url': r.purchase_url, 'is_active': r.is_active, 'created_at': str(r.created_at)} for r in rows]


@app.post('/products')
def create_product(payload: schemas.ProductCreateIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    name=(payload.name or '').strip()
    if not name:
        raise HTTPException(400, 'name is required')
    bt=(payload.business_type or 'material').strip()
    if bt not in ('sidejob','material'):
        raise HTTPException(400, 'business_type must be sidejob/material')
    row = models.ProductItem(business_type=bt, name=name, price=payload.price, description=(payload.description or '').strip() or None, purchase_url=(payload.purchase_url or '').strip() or None, is_active=1)
    db.add(row); db.commit(); db.refresh(row)
    return {'ok': True, 'id': row.id}


@app.post('/products/{product_id}/update')
def update_product(product_id: int, payload: schemas.ProductUpdateIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = db.get(models.ProductItem, product_id)
    if not row:
        raise HTTPException(404, 'product not found')
    if payload.business_type is not None:
        bt=(payload.business_type or '').strip()
        if bt not in ('sidejob','material'):
            raise HTTPException(400, 'business_type must be sidejob/material')
        row.business_type = bt
    if payload.name is not None: row.name = payload.name.strip()
    if payload.price is not None: row.price = payload.price
    if payload.description is not None: row.description = (payload.description or '').strip() or None
    if payload.purchase_url is not None: row.purchase_url = (payload.purchase_url or '').strip() or None
    if payload.is_active is not None: row.is_active = 1 if int(payload.is_active)==1 else 0
    db.commit()
    return {'ok': True, 'id': row.id}


@app.post('/products/{product_id}/delete')
def delete_product(product_id: int, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    row = db.get(models.ProductItem, product_id)
    if not row:
        raise HTTPException(404, 'product not found')
    db.delete(row); db.commit()
    return {'ok': True}


@app.post('/line/send-templated')
def send_templated_message(payload: schemas.TemplatedSendIn, db: Session = Depends(get_db), admin: models.AdminUser = Depends(current_admin)):
    conv = db.get(models.Conversation, payload.conversation_id)
    if not conv:
        raise HTTPException(404,'conversation not found')
    ident = db.execute(select(models.LineIdentity).where(models.LineIdentity.user_id == conv.user_id)).scalar_one_or_none()
    if not ident:
        raise HTTPException(400,'line identity not found')
    channel = db.get(models.LineChannel, conv.channel_id) if conv.channel_id else None
    channel_key = channel.channel_id if channel else None
    token = _line_channel_tokens().get(channel_key)
    if not token:
        raise HTTPException(500, f'line access token not configured for channel: {channel_key}')

    body = (payload.body or '').strip()
    if not body:
        raise HTTPException(400, 'body is required')

    r = httpx.post('https://api.line.me/v2/bot/message/push', headers={'Authorization': f'Bearer {token}','Content-Type':'application/json'}, json={'to': ident.line_user_id, 'messages':[{'type':'text','text':body}]}, timeout=20)
    if r.status_code >= 400:
        raise HTTPException(400, f'line send failed: {r.text}')

    db.add(models.Message(conversation_id=payload.conversation_id, direction='outbound', source='line', message_type='text', body=body))
    user = db.get(models.User, conv.user_id)
    if user:
        if payload.transition_tag is not None:
            user.tag = payload.transition_tag or None
        if payload.transition_status_label is not None:
            user.status_label = payload.transition_status_label or None
        if payload.transition_support_mark is not None:
            user.support_mark = payload.transition_support_mark or None
        if payload.transition_tag is None and payload.transition_status_label is None and payload.transition_support_mark is None:
            _apply_post_send_state(user, payload.template_title, body)
    db.commit()
    return {'ok':True}


@app.get('/entry/{source}', response_class=HTMLResponse)
def entry_source_redirect(source: str):
    src_map={'normal':'通常','sns':'SNS','ads':'広告','affiliate':'アフィリ','referral':'紹介'}
    if source not in src_map:
        source='normal'
    target = os.getenv('DEFAULT_FRIEND_ADD_URL','https://line-template.top')
    target = target + ('&' if '?' in target else '?') + f'src={source}'
    img_url = os.getenv('REFERRAL_THANKS_IMAGE_URL', 'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=900&q=60')
    wait_sec = int(os.getenv('REFERRAL_THANKS_WAIT_SEC', '2') or '2')
    html=f"""<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>ご案内中…</title>
<style>body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1020;color:#e5e7eb;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}.card{{width:min(92vw,520px);background:#111827;border:1px solid #1f2937;border-radius:14px;padding:20px;text-align:center}}img{{max-width:100%;border-radius:10px;margin:10px 0}}a.btn{{display:inline-block;margin-top:12px;padding:10px 14px;border-radius:10px;background:#14532d;color:#fff;text-decoration:none}}.small{{color:#94a3b8;font-size:12px;margin-top:8px}}</style>
</head><body><div class='card'><h3>ご登録ありがとうございます</h3><p>{src_map[source]}経由でLINEへご案内しています。少々お待ちください…</p><img src='{img_url}' alt='thanks' /><div><a class='btn' href='{target}'>すぐに進む</a></div><div class='small'>{wait_sec}秒後に自動で移動します</div></div><script>setTimeout(function(){{location.href={target!r};}}, {wait_sec}*1000);</script></body></html>"""
    return HTMLResponse(content=html)


@app.get('/acquisition-links')
def acquisition_links(admin: models.AdminUser = Depends(current_admin)):
    base='https://line-template.top/entry'
    return {'ok':True,'links':{'通常':f'{base}/normal','SNS':f'{base}/sns','広告':f'{base}/ads','アフィリ':f'{base}/affiliate','紹介':f'{base}/referral'}}

@app.get('/entry/{source}/{channel_key}', response_class=HTMLResponse)
def entry_source_redirect_v2(source: str, channel_key: str):
    src_map = {'normal':'通常','sns':'SNS','ads':'広告','affiliate':'アフィリ','referral':'紹介'}
    if source not in src_map:
        source = 'normal'

    ck = (channel_key or '').lower().strip()
    slot = {'ch1':1,'1':1,'ch2':2,'2':2,'ch3':3,'3':3}.get(ck)

    target = ''
    if slot in (1,2,3):
        target = os.getenv(f'LINE_CHANNEL_{slot}_FRIEND_ADD_URL', '').strip()
    if not target and slot in (1,2,3):
        # fallback to basicId-derived add-friend URL
        key = (os.getenv(f'LINE_CHANNEL_{slot}_DESTINATION','').strip() or os.getenv(f'LINE_CHANNEL_{slot}_ID','').strip())
        if key:
            ch = db.execute(select(models.LineChannel).where(models.LineChannel.channel_id == key)).scalar_one_or_none()
            if ch and ch.basic_id:
                target = f"https://line.me/R/ti/p/{ch.basic_id}"

    if not target:
        target = os.getenv('DEFAULT_FRIEND_ADD_URL', '').strip() or 'https://line-template.top'

    target = target + ('&' if '?' in target else '?') + f"src={source}&ch={slot or ''}"
    img_url = os.getenv('REFERRAL_THANKS_IMAGE_URL', 'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=900&q=60')
    wait_sec = int(os.getenv('REFERRAL_THANKS_WAIT_SEC', '2') or '2')

    html = f"""<!doctype html>
<html lang='ja'><head>
<meta charset='utf-8' />
<meta name='viewport' content='width=device-width, initial-scale=1' />
<title>redirect</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1020;color:#e5e7eb;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
.card{{width:min(92vw,520px);background:#111827;border:1px solid #1f2937;border-radius:14px;padding:20px;text-align:center}}
img{{max-width:100%;border-radius:10px;margin:10px 0}}
a.btn{{display:inline-block;margin-top:12px;padding:10px 14px;border-radius:10px;background:#14532d;color:#fff;text-decoration:none}}
.small{{color:#94a3b8;font-size:12px;margin-top:8px}}
</style>
</head><body>
  <div class='card'>
    <h3>LINE redirect</h3>
    <p>{src_map[source]} / {channel_key.upper()}</p>
    <img src='{img_url}' alt='thanks' />
    <div><a class='btn' href='{target}'>go</a></div>
    <div class='small'>{wait_sec}s auto redirect</div>
  </div>
<script>setTimeout(function(){{ location.href = {target!r}; }}, {wait_sec}*1000);</script>
</body></html>"""
    return HTMLResponse(content=html)

@app.get('/entry2/{source}/{channel_key}', response_class=HTMLResponse)
def entry_source_redirect_v3(source: str, channel_key: str, db: Session = Depends(get_db)):
    src_map = {'normal':'通常','sns':'SNS','ads':'広告','affiliate':'アフィリ','referral':'紹介'}
    if source not in src_map:
        source = 'normal'

    ck = (channel_key or '').lower().strip()
    slot = {'ch1':1,'1':1,'ch2':2,'2':2,'ch3':3,'3':3}.get(ck)

    target = ''
    if slot in (1,2,3):
        target = os.getenv(f'LINE_CHANNEL_{slot}_FRIEND_ADD_URL', '').strip()
    if not target and slot in (1,2,3):
        # fallback to basicId-derived add-friend URL
        key = (os.getenv(f'LINE_CHANNEL_{slot}_DESTINATION','').strip() or os.getenv(f'LINE_CHANNEL_{slot}_ID','').strip())
        if key:
            ch = db.execute(select(models.LineChannel).where(models.LineChannel.channel_id == key)).scalar_one_or_none()
            if ch and ch.basic_id:
                target = f"https://line.me/R/ti/p/{ch.basic_id}"

    if not target:
        target = os.getenv('DEFAULT_FRIEND_ADD_URL', '').strip() or 'https://line-template.top'

    sep = '&' if '?' in target else '?'
    suffix = f"src={source}"
    if slot:
        suffix += f"&ch={slot}"
    target = target + sep + suffix

    html = (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>redirect</title></head><body>"
        f"<p>{src_map[source]} / {channel_key.upper()}</p>"
        f"<p><a href='{target}'>go line</a></p>"
        f"<script>setTimeout(function(){{location.href={target!r};}},1500);</script>"
        "</body></html>"
    )
    return HTMLResponse(content=html)

@app.get('/entry3/{source}/{channel_key}', response_class=HTMLResponse)
def entry_source_redirect_v4(source: str, channel_key: str):
    src_map = {'normal':'通常','sns':'SNS','ads':'広告','affiliate':'アフィリ','referral':'紹介'}
    if source not in src_map:
        source = 'normal'
    # safe simple relay to LINE Login start (state carries src/ch)
    state = urllib.parse.quote_plus(f"src={source}&ch={channel_key}")
    login_target = f"/auth/line/login?state={state}"
    html = (
        "<!doctype html><html lang='ja'><head>"
        "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>LINEログイン中</title>"
        "<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1020;color:#e5e7eb;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}.card{width:min(92vw,560px);background:#111827;border:1px solid #1f2937;border-radius:14px;padding:22px;text-align:center}.spinner{width:36px;height:36px;border:4px solid #334155;border-top-color:#22c55e;border-radius:50%;margin:14px auto;animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}a.btn{display:inline-block;margin-top:12px;padding:10px 14px;border-radius:10px;background:#14532d;color:#fff;text-decoration:none}.small{color:#94a3b8;font-size:12px;margin-top:8px}</style>"
        "</head><body><div class='card'>"
        "<h3>ただいまLINEログイン中です</h3>"
        "<p>安全にご案内するため、本人確認を行っています（数秒で完了）。</p>"
        "<div class='spinner'></div>"
        f"<div><a class='btn' href='{login_target}'>進まない場合はこちら</a></div>"
        "<div class='small'>この画面を閉じずにお待ちください</div>"
        "</div>"
        f"<script>setTimeout(function(){{location.href={login_target!r};}},1200);</script>"
        "</body></html>"
    )
    return HTMLResponse(content=html)

def _norm_phone(v: str | None) -> str:
    return re.sub(r'[^0-9]', '', str(v or ''))


def _latest_survey_phone(db: Session, user_id: int) -> str:
    prof = db.execute(
        select(models.ChannelInterviewProfile)
        .where(models.ChannelInterviewProfile.user_id == user_id)
        .order_by(models.ChannelInterviewProfile.updated_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not prof or not isinstance(prof.survey_answers, dict):
        return ''
    return _norm_phone(prof.survey_answers.get('reg_phone'))


def _channel_key_to_slot(channel_key: str | None) -> int | None:
    ck = (channel_key or '').lower().strip()
    return {'ch1': 1, '1': 1, 'side': 1, 'ch2': 2, '2': 2, 'estate': 2, 'ch3': 3, '3': 3, 'ai': 3}.get(ck)


def _official_line_name(channel_key: str | None) -> str:
    slot = _channel_key_to_slot(channel_key)
    if slot == 1:
        return os.getenv('LINE_CHANNEL_1_NAME', 'CH1 副業 公式LINE')
    if slot == 2:
        return os.getenv('LINE_CHANNEL_2_NAME', 'CH2 不動産 公式LINE')
    if slot == 3:
        return os.getenv('LINE_CHANNEL_3_NAME', 'CH3 AI 公式LINE')
    return f"{(channel_key or 'CH?').upper()} 公式LINE"


@app.get('/official-lines/forms')
def official_line_forms():
    out = []
    for ck in ('ch1', 'ch2', 'ch3'):
        out.append({
            'channel_key': ck,
            'channel_name': _official_line_name(ck),
            'form_url': f'https://line-template.top/register?ch={ck}',
        })
    return {'ok': True, 'items': out}


@app.get('/official-lines/{channel_key}/register', response_class=HTMLResponse)
@app.get('/register/public/{channel_key}', response_class=HTMLResponse)
def official_line_register_form(channel_key: str):
    ch_name = _official_line_name(channel_key)
    form_url = f'https://line-template.top/register?ch={channel_key}'
    html = f"""<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{ch_name} 会員登録</title>
<style>body{{font-family:system-ui;background:#f7f7f8;margin:0}}.wrap{{max-width:620px;margin:30px auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px}}.badge{{display:inline-block;background:#e8f1ff;color:#1d4ed8;padding:5px 10px;border-radius:999px;font-size:12px;font-weight:700}}label{{display:block;margin-top:10px;font-weight:600}}input,textarea{{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px}}button{{margin-top:14px;padding:10px 14px;border:0;border-radius:8px;background:#16a34a;color:#fff;font-weight:700;cursor:pointer}}</style></head><body>
<div class='wrap'>
<span class='badge'>{channel_key.upper()}</span>
<h2>{ch_name} 会員登録フォーム</h2>
<p><b>公式LINE名:</b> {ch_name}<br><b>フォームURL:</b> {form_url}</p>
<form method='post' action='/register'>
<input type='hidden' name='ch' value='{channel_key}'>
<label>お名前 *</label><input name='name' required>
<label>電話番号（任意）</label><input name='phone_number' placeholder='09012345678'>
<label>メールアドレス（必須）</label><input name='email' type='email' required>
<label>LINEユーザーID（任意）</label><input name='line_user_id'>
<label>備考（任意）</label><textarea name='note' rows='4'></textarea>
<button type='submit'>登録する</button>
</form></div></body></html>"""
    return HTMLResponse(content=html)


@app.post('/official-lines/{channel_key}/register', response_class=HTMLResponse)
@app.post('/register/public/{channel_key}/submit', response_class=HTMLResponse)
async def official_line_register_submit(channel_key: str, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    name = (form.get('name') or '').strip()
    if not name:
        raise HTTPException(400, 'name is required')

    phone = _norm_phone(form.get('phone_number'))
    email_raw = (form.get('email') or '').strip()
    if not email_raw:
        raise HTTPException(400, 'email is required')
    email = email_raw
    line_user_id = (form.get('line_user_id') or '').strip() or None
    note = (form.get('note') or '').strip() or None
    ch_name = _official_line_name(channel_key)

    row = models.OfficialLineRegistration(
        channel_key=(channel_key or '').lower().strip(),
        channel_name=ch_name,
        form_url=f'https://line-template.top/official-lines/{channel_key}/register',
        name=name,
        phone_number=(phone or None),
        email=email,
        line_user_id=line_user_id,
        note=note,
    )
    db.add(row)
    db.commit()

    done = f"""<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>登録完了</title>
<style>body{{font-family:system-ui;background:#f7f7f8;margin:0}}.wrap{{max-width:560px;margin:40px auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;text-align:center}}</style></head><body>
<div class='wrap'><h2>登録を受け付けました</h2><p><b>{ch_name}</b> 向けの登録情報を保存しました。<br>※ログインページには遷移しません。</p></div>
</body></html>"""
    return HTMLResponse(content=done)


@app.get('/official-lines/{channel_key}/members/search')
def official_line_member_search(channel_key: str, keyword: str, db: Session = Depends(get_db)):
    kw = (keyword or '').strip()
    if not kw:
        raise HTTPException(422, 'keyword is required')
    q = db.execute(
        select(models.OfficialLineRegistration)
        .where(models.OfficialLineRegistration.channel_key == (channel_key or '').lower().strip())
        .where(
            (models.OfficialLineRegistration.name.like(f'%{kw}%')) |
            (models.OfficialLineRegistration.email.like(f'%{kw}%')) |
            (models.OfficialLineRegistration.phone_number.like(f'%{kw}%')) |
            (models.OfficialLineRegistration.line_user_id.like(f'%{kw}%'))
        )
        .order_by(models.OfficialLineRegistration.id.desc())
        .limit(20)
    ).scalars().all()

    items = []
    for r in q:
        reward_total = db.execute(
            select(func.coalesce(func.sum(models.RewardLedger.amount), 0))
            .where(models.RewardLedger.registration_id == r.id)
        ).scalar_one() or 0
        items.append({
            'registration_id': r.id,
            'channel_key': r.channel_key,
            'channel_name': r.channel_name,
            'name': r.name,
            'phone_number': r.phone_number,
            'email': r.email,
            'line_user_id': r.line_user_id,
            'reward_total': int(reward_total),
            'created_at': str(r.created_at),
        })

    return {'ok': True, 'count': len(items), 'items': items}


@app.get('/register', response_class=HTMLResponse)
def register_form(token: str | None = None, ch: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    # public mode: /register?ch=ch1 (ログイン不要)
    if not token and ch:
        return official_line_register_form(ch)

    reg = db.execute(select(models.MemberRegistration).where(models.MemberRegistration.session_token == token).order_by(models.MemberRegistration.id.desc()).limit(1)).scalar_one_or_none()
    if not reg:
        raise HTTPException(404, 'invalid token')

    name = reg.name or ''
    phone = reg.phone_number or ''
    email = reg.email or ''
    address = reg.address or ''
    err_html = f"<p style='color:#dc2626;font-weight:700'>{error}</p>" if error else ''
    html = f"""<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>会員登録</title>
<style>body{{font-family:system-ui;background:#f7f7f8;margin:0}}.wrap{{max-width:560px;margin:32px auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px}}label{{display:block;margin-top:10px;font-weight:600}}input,textarea{{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px}}.row{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}button{{margin-top:14px;padding:10px 14px;border:0;border-radius:8px;background:#16a34a;color:#fff;font-weight:700;cursor:pointer}}</style></head><body>
<div class='wrap'><h2>会員登録フォーム</h2>{err_html}
<form method='post' action='/register'>
<input type='hidden' name='token' value='{token}' />
<label>お名前</label><input name='name' required value='{name}' />
<label>電話番号</label><input name='phone_number' required value='{phone}' placeholder='09012345678' />
<label>メールアドレス</label><input type='email' name='email' required value='{email}' />
<label>郵便番号</label><input id='postal_code' name='postal_code' placeholder='1000001' />
<div class='row'>
  <div><label>都道府県</label><input id='prefecture' name='prefecture' /></div>
  <div><label>市区町村</label><input id='city' name='city' /></div>
</div>
<label>町名・番地</label><input id='addr1' name='addr1' />
<label>建物名・部屋番号（任意）</label><input id='addr2' name='addr2' />
<label>パスワード</label><input type='password' name='password' required minlength='6' />
<button type='submit'>登録して口座フォームへ進む</button>
</form></div>
<script>
const pc=document.getElementById('postal_code');
if(pc){{
  pc.addEventListener('change', async ()=>{{
    const z=(pc.value||'').replace(/[^0-9]/g,'');
    if(z.length!==7) return;
    try{{
      const r=await fetch('https://zipcloud.ibsnet.co.jp/api/search?zipcode='+z);
      const j=await r.json();
      const it=(j.results&&j.results[0])||null;
      if(!it) return;
      document.getElementById('prefecture').value=it.address1||'';
      document.getElementById('city').value=(it.address2||'')+(it.address3||'');
    }}catch(e){{}}
  }});
}}
</script>
</body></html>"""
    return HTMLResponse(content=html)


@app.post('/register', response_class=HTMLResponse)
async def register_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    token = (form.get('token') or '').strip()
    # public mode from /register?ch=ch1
    if not token and (form.get('ch') or '').strip():
        ch = (form.get('ch') or '').strip()
        return await official_line_register_submit(ch, request, db)

    name = (form.get('name') or '').strip()
    phone = _norm_phone(form.get('phone_number'))
    email = (form.get('email') or '').strip()
    postal_code = _norm_phone(form.get('postal_code'))[:7]
    prefecture = (form.get('prefecture') or '').strip()
    city = (form.get('city') or '').strip()
    addr1 = (form.get('addr1') or '').strip()
    addr2 = (form.get('addr2') or '').strip()
    password = (form.get('password') or '').strip()

    parts = []
    if postal_code:
        parts.append(f'〒{postal_code}')
    if prefecture:
        parts.append(prefecture)
    if city:
        parts.append(city)
    if addr1:
        parts.append(addr1)
    if addr2:
        parts.append(addr2)
    address = ' '.join([p for p in parts if p]).strip()

    reg = db.execute(select(models.MemberRegistration).where(models.MemberRegistration.session_token == token).order_by(models.MemberRegistration.id.desc()).limit(1)).scalar_one_or_none()
    if not reg:
        raise HTTPException(404, 'invalid token')
    user = db.get(models.User, reg.user_id)
    if not user:
        raise HTTPException(404, 'user not found')

    survey_phone = _latest_survey_phone(db, user.id) or _norm_phone(user.phone_number)
    if survey_phone and phone and survey_phone != phone:
        return RedirectResponse(url=f"/register?token={token}&error={urllib.parse.quote('登録の電話番号とLINEログイン時の電話番号が一致しません。ご確認ください。')}", status_code=303)

    reg.name = name
    reg.phone_number = phone
    reg.email = email
    reg.address = address
    reg.password_hash = pwd.hash(password)
    reg.status = 'registered'

    # Keep UI display name stable (LINE profile / manually edited value).
    # Registration form name is stored in MemberRegistration only.
    if not user.display_name:
        user.display_name = name or user.display_name
    user.phone_number = phone or user.phone_number
    user.email = email or user.email
    user.registered_at = user.registered_at or datetime.now()
    user.tag = '会員登録済'
    user.status_label = '会員登録済'

    db.commit()
    return RedirectResponse(url=f'/bank?token={token}', status_code=303)


@app.get('/bank', response_class=HTMLResponse)
def bank_form(token: str, error: str | None = None, db: Session = Depends(get_db)):
    reg = db.execute(select(models.MemberRegistration).where(models.MemberRegistration.session_token == token).order_by(models.MemberRegistration.id.desc()).limit(1)).scalar_one_or_none()
    if not reg:
        raise HTTPException(404, 'invalid token')

    err_html = f"<p style='color:#dc2626;font-weight:700'>{error}</p>" if error else ''
    html = f"""<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>口座登録</title>
<style>body{{font-family:system-ui;background:#f7f7f8;margin:0}}.wrap{{max-width:560px;margin:32px auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px}}label{{display:block;margin-top:10px;font-weight:600}}input,select{{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px}}button{{margin-top:14px;padding:10px 14px;border:0;border-radius:8px;background:#2563eb;color:#fff;font-weight:700;cursor:pointer}}</style></head><body>
<div class='wrap'><h2>口座登録フォーム</h2>{err_html}
<form method='post' action='/bank'>
<input type='hidden' name='token' value='{token}' />
<label>銀行名</label><input name='bank_name' required />
<label>支店名</label><input name='branch_name' required />
<label>口座種別</label><select name='account_type'><option value='普通'>普通</option><option value='当座'>当座</option></select>
<label>口座番号</label><input name='account_number' required />
<label>口座名義（カナ）</label><input name='account_holder' required />
<button type='submit'>口座を登録して完了</button>
</form></div></body></html>"""
    return HTMLResponse(content=html)


@app.post('/bank', response_class=HTMLResponse)
async def bank_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    token = (form.get('token') or '').strip()
    reg = db.execute(select(models.MemberRegistration).where(models.MemberRegistration.session_token == token).order_by(models.MemberRegistration.id.desc()).limit(1)).scalar_one_or_none()
    if not reg:
        raise HTTPException(404, 'invalid token')

    user = db.get(models.User, reg.user_id)
    if not user:
        raise HTTPException(404, 'user not found')

    row = models.MemberBankAccount(
        user_id=user.id,
        bank_name=(form.get('bank_name') or '').strip(),
        branch_name=(form.get('branch_name') or '').strip(),
        account_type=(form.get('account_type') or '').strip() or '普通',
        account_number=(form.get('account_number') or '').strip(),
        account_holder=(form.get('account_holder') or '').strip(),
    )
    db.add(row)
    reg.status = 'bank_registered'
    user.tag = '口座登録済'
    user.status_label = '口座登録完了'
    db.commit()

    done = """<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>登録完了</title>
<style>body{font-family:system-ui;background:#f7f7f8;margin:0}.wrap{max-width:560px;margin:40px auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;text-align:center}a{display:inline-block;margin-top:12px;color:#2563eb}</style></head><body>
<div class='wrap'><h2>登録が完了しました</h2><p>会員登録・口座登録が完了しました。担当からの案内をお待ちください。</p><a href='https://line-template.top'>TOPへ戻る</a></div>
</body></html>"""
    return HTMLResponse(content=done)
