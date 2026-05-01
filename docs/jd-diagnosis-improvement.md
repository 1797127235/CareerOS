# JD 诊断改进设计文档

> 第一期：诊断报告页 + 历史管理
> 第二期：简历定制 + PDF 导出（规划中）

## 1. 背景与目标

### 现状问题
- 诊断结果内嵌显示，无独立报告页
- 诊断后按钮状态不变（"让学长看看" 应变为 "重新诊断"）
- 无历史记录，每次诊断都是临时的

### 目标
- 独立报告页 `/jd/:id`，展示完整诊断结果
- JD 页底部显示历史列表（标题 + 评分 + 日期）
- 诊断完自动跳转报告页
- 支持删除、重诊断

### 现状已走一半
`JDDiagnoseResponse` 已包含 9 个字段，LLM prompt 已在产出这些数据。第一期只需：加表 + 加 3 个路由 + 报告页组件 + 改 JD 页跳转。

## 2. 关键决策

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | 自动存 vs 手动存 | 自动存 | 学生场景不频繁，垃圾靠删 |
| 2 | 6 JSON 字段 vs 1 result_data | 合并为 result_data | 不被 WHERE 查询，合并更灵活，加字段不动表 |
| 3 | 分页 | LIMIT 50 不做 UI | N < 30，先不做 |
| 4 | jd_text 留不留 | 留 | 支持重诊断功能 |
| 5 | 删除策略 | 硬删 | MVP 简化 |
| 6 | loading 位置 | 停在 /jd 显示进度 | 避免 pending 记录复杂度 |
| 7 | jd_title 兜底 | "未命名 JD" + 日期 | LLM 提取失败时的 fallback |
| 8 | 重新诊断按钮 | 要 | 需保留 jd_text |

## 3. 数据模型

### jd_diagnoses 表

```sql
CREATE TABLE jd_diagnoses (
    diagnosis_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    jd_text TEXT NOT NULL,              -- 保留，支持重诊断
    jd_title VARCHAR(200),              -- 兜底 "未命名 JD"
    overall_score INTEGER,
    summary TEXT,
    result_data JSON NOT NULL,          -- 合并：skill_gaps/matched_skills/strengths/risks/resume_tips/action_plan
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

### result_data 结构

```json
{
  "skill_gaps": [{"skill": "Redis", "priority": "high", "suggested_hours": 40}],
  "matched_skills": ["Python", "FastAPI"],
  "strengths": ["有相关实习经验"],
  "risks": ["非科班可能被筛"],
  "resume_tips": ["简历加上量化指标"],
  "action_plan": ["刷 LeetCode Hot 100"]
}
```

## 4. API 设计

### POST /api/jd/diagnose

**改动**：诊断结果自动存库，返回 `diagnosis_id`

**Request**：
```json
{
  "jd_text": "岗位描述文本..."
}
```

**Response**（新增 `diagnosis_id`）：
```json
{
  "diagnosis_id": "uuid-xxx",
  "jd_title": "字节跳动-后端开发工程师",
  "overall_score": 72,
  "summary": "基本匹配，但缺 Redis 和分布式经验",
  "skill_gaps": [...],
  "matched_skills": [...],
  "strengths": [...],
  "risks": [...],
  "resume_tips": [...],
  "action_plan": [...]
}
```

### GET /api/jd/history

**新增**：查询诊断历史（LIMIT 50，不做分页）

**Query Params**：
- `user_id` (默认 "demo_user")

**Response**：
```json
{
  "items": [
    {
      "diagnosis_id": "uuid-xxx",
      "jd_title": "字节跳动-后端开发工程师",
      "overall_score": 72,
      "created_at": "2026-05-02T10:30:00Z"
    }
  ]
}
```

### GET /api/jd/{diagnosis_id}

**新增**：获取单条诊断详情

**Response**：完整诊断结果（同 POST 响应）

### DELETE /api/jd/{diagnosis_id}

**新增**：硬删除单条诊断

**Response**：
```json
{
  "deleted": true
}
```

## 5. 前端设计

### 路由结构

```
/jd          → JD 诊断页（输入 + 历史列表）
/jd/:id      → 诊断报告页（独立展示）
```

### /jd 页面改动

```
┌─────────────────────────────────────┐
│  把你看上的 JD 贴进来,               │
│  我帮你看看够不够格.                  │
│                                      │
│  ┌─────────────────────────────────┐ │
│  │ JD 文本输入区                    │ │
│  └─────────────────────────────────┘ │
│           [ 让学长看看 ]              │
│                                      │
│ ─────────────────────────────────── │
│  诊断历史                            │
│  ┌─────────────────────────────────┐ │
│  │ 字节-后端开发   72分   05-02  ✕ │ │
│  │ 阿里-算法岗     45分   05-01  ✕ │ │
│  └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

**交互**：
- 诊断中：按钮变为 "..."，显示进度条
- 诊断完成：navigate(`/jd/${res.diagnosis_id}`)
- 历史条目：点击跳转报告页
- 删除：hover 显示 ✕，点击后直接删除（硬删，不二次确认）

### /jd/:id 报告页

```
┌─────────────────────────────────────┐
│  ← 返回 JD 诊断  [ 重新诊断 ]       │
│                                      │
│  字节跳动-后端开发工程师              │
│                                      │
│  ┌────┐                              │
│  │ 72 │ / 100 · 基本匹配，但缺 Redis │
│  └────┘                              │
│                                      │
│  你已经具备的                        │
│  · Python · FastAPI · MySQL          │
│                                      │
│  你还缺的                            │
│  · Redis               约 40 小时    │
│                                      │
│  提个醒                              │
│  · 非科班可能被筛                    │
│                                      │
│  下一步建议                          │
│  1. 刷 LeetCode Hot 100             │
│  2. 做一个 Redis 缓存项目            │
│                                      │
│  改简历的话                          │
│  · 简历加上量化指标                  │
└─────────────────────────────────────┘
```

**交互**：
- 左上角返回链接
- 右上角"重新诊断"按钮：将 jd_text 带回 /jd 页输入区
- 评分大数字展示
- 各区块复用现有 Result 组件

## 6. 实现步骤

### 后端

1. 新增 `JDDiagnosis` ORM 模型（`models/jd.py`）
2. 改 `jd_service.py`：诊断后存库
3. 新增路由：`GET /api/jd/history`、`GET /api/jd/{id}`、`DELETE /api/jd/{id}`
4. 更新 `JDDiagnoseResponse` 加 `diagnosis_id` 字段

### 前端

1. 新增路由 `/jd/:id`（`App.tsx`）
2. 改 JD 页：诊断后跳转 + 底部历史列表
3. 新增报告页组件（复用 Result）
4. 更新 `api.ts`：新增 `getJDHistory`、`getJDDiagnosis`、`deleteJDDiagnosis`

## 7. 未来规划（第二期）

### 简历定制

参考 Resume-Matcher，实现：
1. 主简历存储（`profile_data.master_resume`）
2. JD 关键词提取
3. Diff-based 简历改写（只改 summary/descriptions/technicalSkills）
4. 安全机制：个人信息/教育/日期锁定
5. 对比预览：原始 vs 定制

### 数据流

```
上传简历 → 解析为 master_resume
    ↓
诊断 JD → 提取 skill_gaps + matched_skills
    ↓
生成定制简历 (diff-based)
    ↓
展示：原始 vs 定制对比 + 改动说明
    ↓
导出 PDF
```
