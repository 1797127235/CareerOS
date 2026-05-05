# CareerOS 数据模型

**项目**: CareerOS（码路领航）
**数据库**: SQLite (aiosqlite)
**ORM**: SQLAlchemy 2.0 (async)
**最后更新**: 2026-05-06

---

## 概述

CareerOS 使用 SQLite 作为主数据库，通过 SQLAlchemy 2.0 async 风格定义模型。所有表在应用启动时自动创建（`Base.metadata.create_all`）。

---

## 1. users 表

用户基本信息。

```python
class User(Base):
    __tablename__ = "users"
    
    user_id: str          # PK, UUID
    phone: str            # UNIQUE
    email: str            # UNIQUE
    nickname: str         # 显示名称
    avatar_url: str       # 头像 URL
    status: str           # active/suspended/deleted
    user_type: str        # student/transfer_student/graduate
    privacy_level: str    # standard/high
    created_at: datetime
    last_login_at: datetime
    
    # relationship
    profile: UserProfile  # 一对一
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| user_id | String(36) | PK | UUID 主键 |
| phone | String(20) | UNIQUE | 手机号 |
| email | String(100) | UNIQUE | 邮箱 |
| nickname | String(50) | — | 显示名称 |
| avatar_url | String(500) | — | 头像 URL |
| status | String(20) | — | 用户状态 |
| user_type | String(30) | — | 用户类型 |
| privacy_level | String(10) | — | 隐私等级 |
| created_at | DateTime | — | 创建时间 |
| last_login_at | DateTime | — | 最后登录 |

---

## 2. user_profiles 表

用户画像（扩展信息）。

```python
class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    profile_id: str       # PK, UUID
    user_id: str          # FK → users, UNIQUE
    school_name: str
    school_level: str     # 985/211/double_first_class/normal
    major: str
    grade: str            # freshman/sophomore/junior/senior/graduate1-3
    graduation_year: int
    target_direction: str
    target_company_level: str  # top/major/medium/state_owned
    current_skills: JSON
    profile_data: JSON    # 扩展数据
    available_time_daily: int
    personality_tags: JSON
    learning_style: str
    anxiety_level: int
    preferred_interaction: str
    created_at: datetime
    updated_at: datetime
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| profile_id | String(36) | PK | UUID 主键 |
| user_id | String(36) | FK, UNIQUE | 外键 → users |
| school_name | String(100) | — | 学校名称 |
| school_level | String(30) | — | 学校层次 |
| major | String(50) | — | 专业 |
| grade | String(20) | — | 年级 |
| graduation_year | Integer | — | 毕业年份 |
| target_direction | String(50) | — | 目标方向 |
| target_company_level | String(20) | — | 目标公司类型 |
| current_skills | JSON | — | 当前技能列表 |
| profile_data | JSON | — | 扩展画像数据 |
| available_time_daily | Integer | — | 每日可用时间 |
| personality_tags | JSON | — | 性格标签 |
| learning_style | String(20) | — | 学习风格 |
| anxiety_level | Integer | — | 焦虑程度 1-10 |
| preferred_interaction | String(10) | — | 交互偏好 |
| created_at | DateTime | — | 创建时间 |
| updated_at | DateTime | — | 更新时间 |

---

## 3. conversations 表

对话记录。

```python
class Conversation(Base):
    __tablename__ = "conversations"
    
    conversation_id: str  # PK, UUID
    user_id: str          # INDEX
    title: str
    topic_type: str       # career_consult/learning/resume/emotional/technical_qa
    status: str           # active/closed/archived
    context_snapshot: JSON
    message_count: int
    is_pinned: bool
    summary: Text         # 滚动摘要
    created_at: datetime
    last_message_at: datetime
    
    # relationship
    messages: list[Message]  # 一对多
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| conversation_id | String(36) | PK | UUID 主键 |
| user_id | String(36) | INDEX | 用户 ID |
| title | String(200) | — | 对话标题 |
| topic_type | String(30) | — | 主题类型 |
| status | String(20) | — | 对话状态 |
| context_snapshot | JSON | — | 上下文快照 |
| message_count | Integer | — | 消息计数 |
| is_pinned | Boolean | — | 置顶标志 |
| summary | Text | — | 滚动摘要 |
| created_at | DateTime | — | 创建时间 |
| last_message_at | DateTime | — | 最后消息时间 |

---

## 4. messages 表

消息记录。

```python
class Message(Base):
    __tablename__ = "messages"
    
    message_id: str       # PK, UUID
    conversation_id: str  # FK → conversations, INDEX
    role: str             # user/assistant/system/tool
    content: Text
    content_type: str     # text/code/image/card/file
    card_type: str
    card_payload: JSON
    intent: str
    sentiment: float
    tokens_used: int
    model_version: str
    feedback_rating: int
    feedback_comment: Text
    created_at: datetime
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| message_id | String(36) | PK | UUID 主键 |
| conversation_id | String(36) | FK, INDEX | 外键 → conversations |
| role | String(20) | — | 消息角色 |
| content | Text | — | 消息内容 |
| content_type | String(20) | — | 内容类型 |
| card_type | String(50) | — | 卡片类型 |
| card_payload | JSON | — | 卡片数据 |
| intent | String(50) | — | 意图识别 |
| sentiment | Float | — | 情感分数 |
| tokens_used | Integer | — | Token 消耗 |
| model_version | String(50) | — | 模型版本 |
| feedback_rating | Integer | — | 用户评分 1-5 |
| feedback_comment | Text | — | 用户反馈 |
| created_at | DateTime | — | 创建时间 |

---

## 5. growth_events 表

成长事件（**真相源**）。

```python
class GrowthEvent(Base):
    __tablename__ = "growth_events"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_growth_events_user_dedupe"),
    )
    
    id: str               # PK, UUID
    user_id: str          # INDEX
    event_type: str       # INDEX
    entity_type: str
    entity_id: str
    payload_json: Text
    source: str
    created_at: datetime
    dedupe_key: str       # UNIQUE with user_id
    payload_hash: str
    projected_md_at: datetime
    projected_cognee_at: datetime
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK | UUID 主键 |
| user_id | String(64) | INDEX | 用户 ID |
| event_type | String(32) | INDEX | 事件类型 |
| entity_type | String(32) | — | 实体类型 |
| entity_id | String(64) | — | 实体 ID |
| payload_json | Text | — | 事件详情 JSON |
| source | String(16) | — | 事件来源 |
| created_at | DateTime | — | 创建时间 |
| dedupe_key | String(128) | UNIQUE | 去重键 |
| payload_hash | String(64) | — | 内容哈希 |
| projected_md_at | DateTime | — | .md 投影时间 |
| projected_cognee_at | DateTime | — | Cognee 投影时间 |

**索引**:
- `ix_growth_events_user_event` (user_id, event_type)
- `ix_growth_events_user_entity` (user_id, entity_type, entity_id)
- `ix_growth_events_dedupe` (user_id, dedupe_key) UNIQUE
- `ix_growth_events_unprojected_md` (user_id, projected_md_at)
- `ix_growth_events_unprojected_cognee` (user_id, projected_cognee_at)

**事件类型**:
- `profile_updated` — 画像更新
- `skill_added` — 技能新增
- `skill_level_changed` — 技能等级变化
- `experience_added` — 经历新增
- `preference_learned` — 偏好学习
- `decision_made` — 决策记录
- `status_changed` — 状态变化
- `goal_updated` — 目标更新
- `resume_uploaded` — 简历上传

**去重键格式**: `{event_type}:{entity_type}:{entity_id}`

---

## 6. agent_traces 表

Agent 可观测性。

```python
class AgentTrace(Base):
    __tablename__ = "agent_traces"
    
    id: str               # PK, UUID
    conversation_id: str  # INDEX
    user_id: str          # INDEX
    step_number: int
    step_type: str        # llm_call/tool_call/tool_result
    tool_name: str
    tool_args: JSON
    tool_result: str
    content: str
    duration_ms: int
    success: bool
    error_message: str
    created_at: datetime
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK | UUID 主键 |
| conversation_id | String(36) | INDEX | 对话 ID |
| user_id | String(36) | INDEX | 用户 ID |
| step_number | Integer | — | 步骤编号 |
| step_type | String(20) | — | 步骤类型 |
| tool_name | String(50) | — | 工具名称 |
| tool_args | JSON | — | 工具参数 |
| tool_result | String(5000) | — | 工具结果 |
| content | String(5000) | — | 步骤内容 |
| duration_ms | Integer | — | 耗时毫秒 |
| success | Boolean | — | 成功标志 |
| error_message | String(1000) | — | 错误信息 |
| created_at | DateTime | — | 创建时间 |

---

## 7. skill_records 表

技能成长记录。

```python
class SkillRecord(Base):
    __tablename__ = "skill_records"
    
    id: str               # PK, UUID
    user_id: str          # INDEX
    skill_name: str
    skill_level: str
    context: str
    created_at: datetime
    updated_at: datetime
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK | UUID 主键 |
| user_id | String(36) | INDEX | 用户 ID |
| skill_name | String(100) | — | 技能名称 |
| skill_level | String(20) | — | 技能等级 |
| context | String(500) | — | 备注 |
| created_at | DateTime | — | 创建时间 |
| updated_at | DateTime | — | 更新时间 |

---

## ER 图

```
users 1──1 user_profiles
  │
  ├──1──∞ conversations 1──∞ messages
  │
  ├──1──∞ growth_events
  │
  ├──1──∞ skill_records
  │
  └──1──∞ agent_traces
```

---

## 迁移策略

当前使用 `Base.metadata.create_all()` 自动建表，无版本化迁移。

**生产环境建议**: 使用 Alembic 管理 schema 变更。
