# 画像系统改进方案

> 状态：待审核。批准后开始实施。

---

## 1. 现状分析

### 当前画像字段

```python
class UserProfile(Base):
    nickname: str | None
    school_name: str | None        # 学校
    school_level: str | None       # 985/211/双一流/普通本科
    major: str | None              # 专业
    grade: str | None              # 年级
    graduation_year: int | None    # 毕业年份
    target_direction: str | None   # 目标方向
    target_company_level: str | None  # 目标公司层级
    current_skills: list[SkillItem]   # 技能列表 [{name, level}]
```

### 问题诊断

| 问题 | 影响 |
|------|------|
| 字段太少 | JD 诊断只能做粗粒度匹配 |
| 没有实习经历 | 无法评估实战经验 |
| 没有项目经历 | 无法判断动手能力 |
| 没有教育详情 | 缺少 GPA/课程/获奖信息 |
| 没有求职偏好 | 无法考虑地域/薪资匹配 |
| UI 太单薄 | 用户不知道还能填什么 |

---

## 2. 目标画像结构

### 2.1 基础信息

| 字段 | 类型 | 必填 | 来源 |
|------|------|------|------|
| nickname | str | 否 | 手动 |
| city | str | 否 | 手动 |
| self_intro | str | 否 | 手动（一句话自我介绍） |

### 2.2 教育背景

| 字段 | 类型 | 必填 | 来源 |
|------|------|------|------|
| school_name | str | 是 | 简历解析 |
| major | str | 是 | 简历解析 |
| school_level | enum | 否 | 简历解析 |
| grade | enum | 否 | 简历解析 |
| graduation_year | int | 否 | 简历解析 |
| gpa | str | 否 | 手动（如 "3.8/4.0"） |
| ranking | str | 否 | 手动（如 "前10%"） |
| awards | list[str] | 否 | 手动（获奖列表） |

### 2.3 实习经历（可多条）

| 字段 | 类型 | 必填 | 来源 |
|------|------|------|------|
| company | str | 是 | 简历解析 |
| position | str | 是 | 简历解析 |
| duration | str | 否 | 简历解析（如 "3个月"） |
| start_date | str | 否 | 手动 |
| end_date | str | 否 | 手动 |
| description | str | 否 | 简历解析（工作内容） |
| tech_stack | list[str] | 否 | 手动（技术栈） |
| highlights | list[str] | 否 | 手动（亮点成果） |

### 2.4 项目经历（可多条）

| 字段 | 类型 | 必填 | 来源 |
|------|------|------|------|
| name | str | 是 | 简历解析 |
| description | str | 否 | 简历解析 |
| tech_stack | list[str] | 否 | 简历解析 |
| role | str | 否 | 手动（担任角色） |
| duration | str | 否 | 手动 |
| highlights | list[str] | 否 | 手动（亮点成果） |
| github_url | str | 否 | 手动 |

### 2.5 技能清单

| 字段 | 类型 | 必填 | 来源 |
|------|------|------|------|
| name | str | 是 | 简历解析 |
| level | enum | 是 | 简历解析（入门/一般/熟练/精通） |
| years | int | 否 | 手动（使用年限） |
| category | str | 否 | 手动（语言/框架/工具/其他） |

### 2.6 求职偏好

| 字段 | 类型 | 必填 | 来源 |
|------|------|------|------|
| target_direction | str | 是 | 手动 |
| target_company_level | enum | 否 | 手动 |
| target_cities | list[str] | 否 | 手动 |
| expected_salary | str | 否 | 手动（如 "15-20k"） |
| available_date | str | 否 | 手动（到岗时间） |

### 2.7 证书/资质

| 字段 | 类型 | 必填 | 来源 |
|------|------|------|------|
| name | str | 是 | 手动 |
| issuer | str | 否 | 手动（颁发机构） |
| date | str | 否 | 手动 |

---

## 3. 数据模型变更

### 3.1 新增 JSON 字段（推荐）

保持现有字段不变，新增一个 `profile_data` JSON 字段存储扩展信息：

```python
class UserProfile(Base):
    # 现有字段保持不变...
    
    # 新增：扩展画像数据（JSON）
    profile_data: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )
    # 存储结构：
    # {
    #   "city": "北京",
    #   "self_intro": "大三后端方向，有两段实习",
    #   "education": {
    #     "gpa": "3.8/4.0",
    #     "ranking": "前10%",
    #     "awards": ["ACM银牌", "国家奖学金"]
    #   },
    #   "internships": [
    #     {
    #       "company": "字节跳动",
    #       "position": "后端开发实习生",
    #       "duration": "3个月",
    #       "description": "负责...",
    #       "tech_stack": ["Go", "MySQL", "Redis"],
    #       "highlights": ["优化查询性能提升50%"]
    #     }
    #   ],
    #   "projects": [
    #     {
    #       "name": "分布式KV存储",
    #       "description": "基于Raft协议...",
    #       "tech_stack": ["C++", "gRPC"],
    #       "highlights": ["支持10万QPS"]
    #     }
    #   ],
    #   "certificates": [
    #     {"name": "AWS SAA", "issuer": "AWS", "date": "2024-06"}
    #   ],
    #   "preferences": {
    #     "target_cities": ["北京", "上海"],
    #     "expected_salary": "15-20k",
    #     "available_date": "2025-07"
    #   },
    #   "skills_detail": [
    #     {"name": "Python", "level": "精通", "years": 3, "category": "语言"},
    #     {"name": "Django", "level": "熟练", "years": 2, "category": "框架"}
    #   ]
    # }
```

**优点**：
- 不破坏现有数据
- 灵活扩展，后续加字段不用改表结构
- JSON 字段可以直接被 LLM 读取

### 3.2 备选：独立表

如果后续需要更复杂的查询（如按技能筛选用户），可以拆分独立表：

```python
class Internship(Base):
    __tablename__ = "internships"
    id: int
    user_id: int
    company: str
    position: str
    duration: str
    description: str
    ...

class Project(Base):
    __tablename__ = "projects"
    id: int
    user_id: int
    name: str
    description: str
    tech_stack: list[str]
    ...
```

**MVP 阶段建议用 JSON，后续按需拆表。**

---

## 4. LLM 解析 Prompt 改进

### 4.1 当前 Prompt 问题

```
你是一个简历解析助手。请从以下简历文本中提取用户画像，输出JSON格式...
```

**问题**：只提取基础字段，没有提取实习/项目/证书等详细信息。

### 4.2 改进后的 Prompt

```
你是一个简历解析助手。请从以下简历文本中提取完整的用户画像，输出JSON格式：

{
  "nickname": "姓名",
  "school_name": "学校全称",
  "major": "专业",
  "school_level": "985/211/double_first_class/normal",
  "grade": "freshman/sophomore/junior/senior/graduate1/graduate2/graduate3",
  "graduation_year": 2026,
  "city": "所在城市",
  "education": {
    "gpa": "如 3.8/4.0，没有则null",
    "ranking": "如 前10%，没有则null",
    "awards": ["获奖1", "获奖2"]
  },
  "internships": [
    {
      "company": "公司名",
      "position": "职位",
      "duration": "时长",
      "description": "工作内容摘要",
      "tech_stack": ["技术1", "技术2"],
      "highlights": ["亮点1", "亮点2"]
    }
  ],
  "projects": [
    {
      "name": "项目名",
      "description": "项目描述",
      "tech_stack": ["技术1", "技术2"],
      "highlights": ["亮点1"]
    }
  ],
  "skills": [
    {"name": "技能名", "level": "beginner/familiar/intermediate/advanced"}
  ],
  "certificates": [
    {"name": "证书名", "issuer": "颁发机构", "date": "获得时间"}
  ],
  "target_direction": "后端/前端/算法/AI/...",
  "target_company_level": "top/major/medium/state_owned"
}

注意：
1. 从简历内容推断，不确定的字段填 null
2. 技能等级根据简历描述判断：提到"精通"用advanced，"熟练"用familiar，"了解"用beginner
3. 实习和项目尽量提取完整信息
4. 如果简历格式混乱，尽力解析，不要遗漏关键信息
```

---

## 5. UI 改进方案

### 5.1 布局：双栏（参考 CareerPlanningAgent）

```
┌─────────────┬──────────────────────────────────┐
│ 左栏 280px   │ 右栏                              │
│             │                                  │
│ 头像+姓名    │ 区块1: 教育背景                    │
│ 城市         │ 区块2: 实习经历（时间线）            │
│ 自我介绍     │ 区块3: 项目经历                    │
│             │ 区块4: 技能清单                    │
│ 操作按钮:    │ 区块5: 证书/获奖                   │
│ - 编辑画像   │ 区块6: 求职偏好                    │
│ - 重新上传   │                                  │
└─────────────┴──────────────────────────────────┘
```

### 5.2 各区块设计

**教育背景**：
```
教育背景
─────────────
南华大学 · 软件工程
普通本科 · 大三 · 2027毕业
GPA: 3.8/4.0 · 前10%
获奖: 国家奖学金, ACM银牌
```

**实习经历**（时间线样式）：
```
实习经历 (2段)
─────────────
  ● 字节跳动 · 后端开发实习生          2024.07-2024.10
    负责用户服务重构，优化查询性能...
    技术栈: Go, MySQL, Redis
    亮点: 查询性能提升50%
    
  ● 美团 · 后端开发实习生              2024.01-2024.04
    参与订单系统开发...
    技术栈: Java, Spring Boot
```

**项目经历**（卡片式）：
```
项目经历 (3个)
─────────────
┌─────────────────────────────────────┐
│ 分布式KV存储                         │
│ 基于Raft协议的分布式键值存储系统        │
│ 技术栈: C++, gRPC, Protobuf         │
│ 亮点: 支持10万QPS, 3节点容错          │
│ GitHub: github.com/xxx/kv-store     │
└─────────────────────────────────────┘
```

**技能清单**（分组展示）：
```
技能清单
─────────────
语言: Python(精通) · C++(熟练) · Java(一般)
框架: Django(熟练) · Spring Boot(一般)
工具: Git(精通) · Docker(熟练) · K8s(一般)
```

**求职偏好**：
```
求职偏好
─────────────
目标方向: 后端开发
目标公司: 大厂
期望城市: 北京, 上海
期望薪资: 15-20k
到岗时间: 2025年7月
```

### 5.3 编辑模式

点击「编辑画像」进入编辑模式：
- 所有区块变成可编辑表单
- 实习/项目支持「添加」「删除」「排序」
- 底部显示「保存」和「取消」按钮
- 保存后显示「✓ 已保存」反馈

---

## 6. 简历解析改进

### 6.1 解析流程

```
用户上传简历
    ↓
提取文本（pdfplumber/docx）
    ↓
发送给 LLM（改进后的 Prompt）
    ↓
解析 JSON 响应
    ↓
存入数据库（现有字段 + profile_data JSON）
    ↓
返回完整画像给前端
```

### 6.2 向后兼容

- 现有字段保持不变，不影响已有用户
- 新字段存储在 `profile_data` JSON 中
- 前端根据字段是否存在决定显示哪些区块

---

## 7. 实施计划

### Phase 1：数据模型（1天）
- [ ] UserProfile 新增 `profile_data` JSON 字段
- [ ] 创建 Alembic 迁移脚本
- [ ] 更新 ProfileResponse schema
- [ ] 更新 ProfileUpdate schema

### Phase 2：后端逻辑（2天）
- [ ] 改进简历解析 Prompt
- [ ] 更新 profile_service.py 解析逻辑
- [ ] 更新 profile_service.py 写入逻辑
- [ ] 更新 profile.py 路由（支持 JSON 字段更新）

### Phase 3：前端 UI（3天）
- [ ] 重新设计 Profile.tsx 布局（双栏）
- [ ] 实现教育背景区块
- [ ] 实现实习经历区块（时间线）
- [ ] 实现项目经历区块（卡片）
- [ ] 实现技能清单区块（分组）
- [ ] 实现证书/获奖区块
- [ ] 实现求职偏好区块
- [ ] 实现编辑模式（表单）

### Phase 4：测试优化（1天）
- [ ] 上传简历测试解析准确性
- [ ] 测试编辑保存流程
- [ ] 测试 JD 诊断准确性
- [ ] 修复 bug

**总计：7 天**

---

## 8. 验收标准

- [ ] 上传简历后，解析出完整的教育/实习/项目/技能信息
- [ ] 画像页显示所有区块，数据完整
- [ ] 每个字段都可以手动编辑并保存
- [ ] JD 诊断结果更准确（因为有更多画像数据）
- [ ] 现有用户数据不丢失（向后兼容）
