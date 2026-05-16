# Story: 路线 B — 体验升级（2-3 天）

**目标**：让 Lumen 从"能记录"进化到"能理解、能建议、能互动"。

**前置条件**：Workstream A/B/C 已完成（记忆维度重塑、语义去重、简历模块删除）。

---

## B1: 清理画像字段（消除求职基因）

**问题**：`ProfilePayload` 和 `UpdateProfileArgs` 仍含求职字段（`school_name`、`gpa`、`target_direction`），Agent 可能问用户"你学校是什么"。

**方案**：收窄 `update_profile` 的定位为"只收集最基础身份名片"，其他深度画像全部走 `memory_save`。

### 修改文件

#### `backend/modules/profile/schemas.py`

```python
class ProfilePayload(BaseModel):
    nickname: str | None = None
    bio: str | None = None
```

#### `backend/modules/agent/tools/builtin/schemas.py`

```python
class UpdateProfileArgs(TypedDict):
    nickname: NotRequired[str]
    bio: NotRequired[str]
```

#### `backend/modules/agent/tools/builtin/profile.py`

字段遍历列表从 13 个字段缩减为 2 个：
```python
for name in ["nickname", "bio"]:
```

#### `backend/modules/agent/pydantic_agent.py`

第 139 行提示词微调：
```python
return "【用户画像为空】用户尚未提供个人信息。当用户提供信息时，调用 memory_save 或 update_profile 保存。"
```

**验证**：py_compile 通过 + grep 确认旧字段名不再出现在 schemas 和 profile.py 中。

---

## B2: 模式洞察实现（patterns）

**问题**：`understanding.py` 第 209 行 `patterns: []` 永远为空，Profile 页面"AI 注意到的"区块空白。

**方案**：在 `update_ai_understanding()` 的 LLM 调用中，让 AI 同时生成 3-5 条模式洞察，持久化到 `UserProfile.profile_data["patterns"]`。

### 修改文件

#### `backend/modules/memory/understanding.py`

1. 修改 `_generate_understanding()` 的 prompt，要求 AI 同时输出 `patterns` JSON 数组
2. 修改 `_update_profile_data()` 将 `patterns` 存入 `profile_data`
3. 修改 `get_about_you_data()` 从 `profile_data` 读取 `patterns`

#### `backend/modules/profile/models.py`

无需修改，`profile_data` JSON 列已支持任意字段。

**验证**：运行后检查 `UserProfile.profile_data["patterns"]` 是否包含非空数组。

---

## B3: Profile 页面主动塑造画像入口

**问题**：Workstream C 删除简历编辑后，Profile 变成纯只读。用户无法主动告诉 AI"我是谁"。

**方案**：在 Profile 页面增加轻量化的"告诉 AI"输入框，用户输入后直接写入对应 event type。

### 修改文件

#### `src/pages/Profile.tsx`

在"关于你"卡片下方增加 3 个输入框：
- **兴趣**：写入 `interest_observed`
- **价值观**：写入 `value_surfaced`
- **重要的人**：写入 `relationship_noted`

#### `src/lib/api/memory.ts`

新增 `tellAI(event_type, content)` 函数，调用后端通用写入端点。

#### `backend/modules/memory/router.py`

新增 `POST /tell` 端点：
```python
@router.post("/tell")
async def tell_ai(
    body: dict[str, str],
    user_id: str = Query("demo_user"),
) -> dict:
    # body: {event_type, content}
    # 写入对应 event type
```

**验证**：前端输入 → 后端写入 → 数据库查询确认 event 存在。

---

## B4: 意图/目标追踪（Intent Tracking）

**问题**：用户说"我想学日语"，Lumen 没有机制记住这个意图并追踪进展。

**方案**：复用 `value_surfaced` 事件类型（"在意什么"天然包含"想做什么"），在 `understanding.py` 中增加意图提取逻辑，定期在对话中温和提醒。

### 修改文件

#### `backend/modules/memory/understanding.py`

1. 新增 `_extract_intents()` 函数：从 `value_surfaced` 事件中提取以"我想"、"我希望"、"我打算"开头的内容
2. 新增 `_should_remind_intent()` 函数：判断某个意图是否超过 N 天未被提及
3. 在 `build_context()` 中注入"待追踪意图"提示

**验证**：用户说"我想学日语" → 3 天后对话中 Lumen 主动问"日语学得怎么样了？"

---

## B5: 情绪时间线可视化

**问题**：`emotional_pattern` 事件已完整记录，但前端没有任何可视化展示。

**方案**：Profile 页面新增"情绪"标签页，展示近期情绪起伏折线图。

### 修改文件

#### `src/pages/Profile.tsx`

新增情绪 Tab：
- 调用 `getMemoryList()` 获取 `emotional_pattern` 类型事件
- 提取时间 + 情绪关键词
- 用简单 CSS/Chart 展示时间线

#### `backend/modules/memory/router.py` 或 `searcher.py`

确保 `list_events` 或 `recall` 支持按 `event_type` 过滤（已支持，无需修改）。

**验证**：前端能看到情绪事件的时间分布。

---

## 实施顺序

| 顺序 | 任务 | 工作量 | 依赖 |
|------|------|--------|------|
| 1 | B1 清理画像字段 | 30 分钟 | 无 |
| 2 | B2 模式洞察 | 半天 | B1 |
| 3 | B3 主动塑造入口 | 半天 | 无 |
| 4 | B4 意图追踪 | 1 天 | B2（共用 understanding 逻辑）|
| 5 | B5 情绪可视化 | 半天 | 无 |

---

## 验收标准

1. Agent 不再询问 GPA/学校/薪资
2. Profile 页面"AI 注意到的"展示 3-5 条模式洞察
3. 用户可以在 Profile 页面主动输入兴趣/价值观/重要的人
4. Lumen 能记住用户的"我想..."并在合适时机提醒
5. Profile 页面能看到情绪时间线
