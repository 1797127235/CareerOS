"""Memory Service — .md 文件记忆层

负责读写 ~/.careeros/memory/ 目录下的 .md 文件。
"""

from __future__ import annotations

import re
from datetime import datetime

from app.backend.config import USER_DATA_DIR

# ── 目录常量 ────────────────────────────────────────

MEMORY_DIR = USER_DATA_DIR / "memory"
ENTITIES_DIR = MEMORY_DIR / "entities"

# ── 初始化 ──────────────────────────────────────────


def ensure_memory_dirs() -> None:
    """确保记忆目录存在"""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    ENTITIES_DIR.mkdir(parents=True, exist_ok=True)


# ── 核心记忆读写 ────────────────────────────────────


def read_memory() -> str:
    """读取核心记忆文件 memory.md"""
    memory_file = MEMORY_DIR / "memory.md"
    if not memory_file.exists():
        return ""
    return memory_file.read_text(encoding="utf-8")


def write_memory(content: str) -> None:
    """写入核心记忆文件 memory.md"""
    ensure_memory_dirs()
    memory_file = MEMORY_DIR / "memory.md"
    memory_file.write_text(content, encoding="utf-8")


def update_memory_section(section: str, content: str) -> None:
    """更新核心记忆的特定章节

    Args:
        section: 章节标题，如 "基础信息"、"目标方向"
        content: 章节内容
    """
    current = read_memory()
    if not current:
        # 如果文件不存在，创建默认结构
        current = _default_memory_template()

    # 匹配章节标题
    pattern = rf"(## {re.escape(section)}\n)(.*?)(?=\n## |\Z)"
    match = re.search(pattern, current, re.DOTALL)

    if match:
        # 替换章节内容
        new_content = current[: match.start(2)] + content + "\n" + current[match.end(2) :]
    else:
        # 追加新章节
        new_content = current.rstrip() + f"\n\n## {section}\n{content}\n"

    write_memory(new_content)


def _default_memory_template() -> str:
    """默认核心记忆模板"""
    return f"""# 用户核心记忆

> 这个文件由 AI 自动管理，记录用户的核心信息。
> 每次对话开始时会自动注入到 system prompt。

## 基础信息
<!-- 从简历或对话中提取的基本信息 -->
- 学校：（待填写）
- 专业：（待填写）
- 年级：（待填写）
- 毕业年份：（待填写）

## 目标方向
<!-- 用户的职业目标 -->
- 目标岗位：（待填写）
- 目标公司类型：（待填写）
- 意向城市：（待填写）

## 当前状态
<!-- 用户当前的学习/求职状态 -->
- 正在学习：（待填写）
- 正在准备：（待填写）
- 焦虑程度：（待填写）

## 关键偏好
<!-- 用户的偏好和习惯 -->
- 学习风格：（待填写）
- 交互偏好：（待填写）
- 每日可用时间：（待填写）

## 最近决定
<!-- 用户最近做出的重要决定 -->
<!-- 格式：- [日期] 决定内容 -->

---
*最后更新：{datetime.now().strftime("%Y-%m-%d")}*
"""


# ── 实体记忆读写 ────────────────────────────────────


def read_entity(entity_type: str) -> str:
    """读取实体记忆文件

    Args:
        entity_type: 实体类型，如 "skills"、"experiences"、"preferences"

    Returns:
        文件内容，如果文件不存在返回空字符串
    """
    entity_file = ENTITIES_DIR / f"{entity_type}.md"
    if not entity_file.exists():
        return ""
    return entity_file.read_text(encoding="utf-8")


def write_entity(entity_type: str, content: str) -> None:
    """写入实体记忆文件

    Args:
        entity_type: 实体类型，如 "skills"、"experiences"、"preferences"
        content: 文件内容
    """
    ensure_memory_dirs()
    entity_file = ENTITIES_DIR / f"{entity_type}.md"
    entity_file.write_text(content, encoding="utf-8")


def append_to_entity(entity_type: str, section: str, content: str) -> None:
    """向实体记忆追加内容

    Args:
        entity_type: 实体类型
        section: 章节标题
        content: 追加的内容
    """
    current = read_entity(entity_type)
    if not current:
        # 如果文件不存在，创建默认结构
        current = _default_entity_template(entity_type)

    # 匹配章节标题
    pattern = rf"(## {re.escape(section)}\n)(.*?)(?=\n## |\Z)"
    match = re.search(pattern, current, re.DOTALL)

    if match:
        # 在章节末尾追加
        new_content = current[: match.end(2)].rstrip() + "\n" + content + "\n" + current[match.end(2) :]
    else:
        # 追加新章节
        new_content = current.rstrip() + f"\n\n## {section}\n{content}\n"

    write_entity(entity_type, new_content)


def _default_entity_template(entity_type: str) -> str:
    """默认实体记忆模板"""
    templates = {
        "skills": """# 技能列表

> 记录用户的技能状态，用于能力评估和学习建议。

## 编程语言
<!-- 格式：
### 语言名称
- 状态：了解/熟悉/精通
- 学习时间：xxx
- 项目经验：xxx
- 置信度：0.0-1.0
-->

## 框架/工具
<!-- 格式：
### 框架名称
- 状态：了解/熟悉/精通
- 学习时间：xxx
- 项目经验：xxx
- 置信度：0.0-1.0
-->

## 其他技能
<!-- 格式：
### 技能名称
- 状态：了解/熟悉/精通
- 学习时间：xxx
- 项目经验：xxx
- 置信度：0.0-1.0
-->

---
*最后更新：{date}*
""",
        "experiences": """# 经历列表

> 记录用户的项目经历、实习经历、获奖经历等。

## 项目经历
<!-- 格式：
### 项目名称
- 时间：YYYY-MM
- 技术栈：xxx
- 角色：xxx
- 描述：xxx
- 收获：xxx
-->

## 实习经历
<!-- 格式：
### 公司名称 - 岗位
- 时间：YYYY-MM - YYYY-MM
- 描述：xxx
- 收获：xxx
-->

## 获奖经历
<!-- 格式：
### 奖项名称
- 时间：YYYY-MM
- 级别：xxx
- 描述：xxx
-->

## 课程项目
<!-- 格式：
### 课程名称 - 项目名称
- 时间：YYYY-MM
- 描述：xxx
- 收获：xxx
-->

---
*最后更新：{date}*
""",
        "preferences": """# 偏好列表

> 记录用户的偏好和习惯，用于个性化建议。

## 学习风格
<!-- 用户偏好的学习方式 -->
- 主要方式：（待填写）
- 辅助方式：（待填写）

## 交互偏好
<!-- 用户偏好的交互方式 -->
- 详细程度：（待填写）
- 是否喜欢代码示例：（待填写）
- 是否喜欢类比解释：（待填写）

## 工具偏好
<!-- 用户偏好的开发工具 -->
- 编辑器：（待填写）
- 终端：（待填写）
- 版本控制：（待填写）

## 内容偏好
<!-- 用户偏好的学习内容类型 -->
- 视频/文章/文档：（待填写）
- 中文/英文：（待填写）
- 理论/实践：（待填写）

---
*最后更新：{date}*
""",
        "goals": """# 目标列表

> 记录用户的短期和长期目标，用于规划和追踪。

## 长期目标
<!-- 格式：
### 目标名称
- 时间范围：xxx
- 状态：规划中/进行中/已完成
- 进度：xx%
- 关键里程碑：xxx
-->

## 短期目标
<!-- 格式：
### 目标名称
- 截止时间：YYYY-MM-DD
- 状态：规划中/进行中/已完成
- 进度：xx%
- 下一步行动：xxx
-->

## 学习目标
<!-- 格式：
### 目标名称
- 截止时间：YYYY-MM-DD
- 状态：规划中/进行中/已完成
- 进度：xx%
- 学习资源：xxx
-->

---
*最后更新：{date}*
""",
        "decisions": """# 决策记录

> 记录用户做出的重要决策，用于追踪决策过程和复盘。

## 职业决策
<!-- 格式：
### 决策标题
- 时间：YYYY-MM-DD
- 背景：xxx
- 决策：xxx
- 理由：xxx
- 结果：xxx
-->

## 学习决策
<!-- 格式：
### 决策标题
- 时间：YYYY-MM-DD
- 背景：xxx
- 决策：xxx
- 理由：xxx
- 结果：xxx
-->

## 项目决策
<!-- 格式：
### 决策标题
- 时间：YYYY-MM-DD
- 背景：xxx
- 决策：xxx
- 理由：xxx
- 结果：xxx
-->

---
*最后更新：{date}*
""",
        "relationships": """# 关系网络

> 记录用户的人际关系，用于人脉管理和机会发现。

## 导师/老师
<!-- 格式：
### 人名
- 关系：xxx
- 单位：xxx
- 联系方式：xxx
- 备注：xxx
-->

## 同学/朋友
<!-- 格式：
### 人名
- 关系：xxx
- 单位/学校：xxx
- 联系方式：xxx
- 备注：xxx
-->

## 行业人士
<!-- 格式：
### 人名
- 关系：xxx
- 单位：xxx
- 职位：xxx
- 联系方式：xxx
- 备注：xxx
-->

---
*最后更新：{date}*
""",
        "status": """# 当前状态

> 记录用户当前的实时状态，用于个性化建议。

## 求职状态
- 阶段：（待填写）<!-- 准备中/投递中/面试中/已签约 -->
- 投递数量：（待填写）
- 面试数量：（待填写）
- Offer 数量：（待填写）

## 学习状态
- 正在学习：（待填写）
- 学习进度：（待填写）
- 遇到困难：（待填写）

## 心理状态
- 焦虑程度：（待填写）<!-- 1-10 -->
- 信心程度：（待填写）<!-- 1-10 -->
- 主要压力源：（待填写）

## 时间状态
- 每日可用时间：（待填写）
- 主要时间段：（待填写）
- 碎片时间：（待填写）

---
*最后更新：{date}*
""",
    }

    date = datetime.now().strftime("%Y-%m-%d")
    return templates.get(entity_type, f"# {entity_type}\n\n*最后更新：{date}*\n").format(date=date)


# ── 搜索功能 ────────────────────────────────────────


def search_memory(query: str) -> list[dict]:
    """搜索记忆内容

    Args:
        query: 搜索关键词

    Returns:
        匹配的结果列表，每个结果包含 {file, section, content}
    """
    results = []

    # 搜索核心记忆
    memory_content = read_memory()
    if query.lower() in memory_content.lower():
        results.append(
            {
                "file": "memory.md",
                "section": "核心记忆",
                "content": _extract_relevant_content(memory_content, query),
            }
        )

    # 搜索实体记忆
    for entity_file in ENTITIES_DIR.glob("*.md"):
        entity_content = entity_file.read_text(encoding="utf-8")
        if query.lower() in entity_content.lower():
            results.append(
                {
                    "file": f"entities/{entity_file.name}",
                    "section": entity_file.stem,
                    "content": _extract_relevant_content(entity_content, query),
                }
            )

    return results


def _extract_relevant_content(content: str, query: str, context_lines: int = 3) -> str:
    """提取包含查询词的相关内容

    Args:
        content: 完整内容
        query: 搜索关键词
        context_lines: 上下文行数

    Returns:
        相关内容片段
    """
    lines = content.split("\n")
    relevant_lines = []

    for i, line in enumerate(lines):
        if query.lower() in line.lower():
            # 提取上下文
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            relevant_lines.extend(lines[start:end])
            relevant_lines.append("---")

    # 去重
    seen = set()
    unique_lines = []
    for line in relevant_lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    return "\n".join(unique_lines[:50])  # 限制长度


# ── 简历数据转 Markdown ─────────────────────────────


def resume_to_markdown(data: dict) -> dict[str, str]:
    """将 LLM 解析的简历 JSON 转为 Markdown 格式

    Args:
        data: LLM 解析的简历数据

    Returns:
        dict: 包含 memory.md 和 entities/*.md 的内容
    """
    date = datetime.now().strftime("%Y-%m-%d")

    # ── 构建 memory.md ──
    memory_parts = ["# 用户核心记忆", ""]
    memory_parts.append("> 这个文件由 AI 自动管理，记录用户的核心信息。")
    memory_parts.append("> 每次对话开始时会自动注入到 system prompt。")
    memory_parts.append("")

    # 基础信息
    memory_parts.append("## 基础信息")
    memory_parts.append(f"- 学校：{data.get('school_name', '（待填写）')}")
    memory_parts.append(f"- 专业：{data.get('major', '（待填写）')}")
    memory_parts.append(f"- 年级：{_format_grade(data.get('grade'))}")
    memory_parts.append(f"- 毕业年份：{data.get('graduation_year', '（待填写）')}")
    memory_parts.append(f"- 学校层次：{_format_school_level(data.get('school_level'))}")
    memory_parts.append("")

    # 目标方向
    memory_parts.append("## 目标方向")
    memory_parts.append(f"- 目标岗位：{data.get('target_direction', '（待填写）')}")
    memory_parts.append(f"- 目标公司类型：{_format_company_level(data.get('target_company_level'))}")
    memory_parts.append(f"- 意向城市：{data.get('city', '（待填写）')}")
    memory_parts.append("")

    # 教育背景
    education = data.get("education", {})
    if education:
        memory_parts.append("## 教育背景")
        if education.get("gpa"):
            memory_parts.append(f"- GPA：{education['gpa']}")
        if education.get("ranking"):
            memory_parts.append(f"- 排名：{education['ranking']}")
        if education.get("awards"):
            memory_parts.append("- 获奖：")
            for award in education["awards"]:
                memory_parts.append(f"  - {award}")
        memory_parts.append("")

    # 当前状态
    memory_parts.append("## 当前状态")
    memory_parts.append("- 正在学习：（待填写）")
    memory_parts.append("- 正在准备：（待填写）")
    memory_parts.append("- 焦虑程度：（待填写）")
    memory_parts.append("")

    # 其他信息
    if data.get("bio"):
        memory_parts.append("## 个人简介")
        memory_parts.append(data["bio"])
        memory_parts.append("")

    if data.get("english_level"):
        memory_parts.append("## 英语水平")
        memory_parts.append(f"- {data['english_level']}")
        memory_parts.append("")

    if data.get("expected_salary"):
        memory_parts.append("## 期望薪资")
        memory_parts.append(f"- {data['expected_salary']}")
        memory_parts.append("")

    memory_parts.append(f"---\n*最后更新：{date}*")

    # ── 构建 entities/experiences.md ──
    experiences_parts = ["# 经历列表", ""]
    experiences_parts.append("> 记录用户的项目经历、实习经历、获奖经历等。")
    experiences_parts.append("")

    # 项目经历
    projects = data.get("projects", [])
    if projects:
        experiences_parts.append("## 项目经历")
        for proj in projects:
            experiences_parts.append(f"### {proj.get('title', '未命名项目')}")
            if proj.get("period"):
                experiences_parts.append(f"- 时间：{proj['period']}")
            if proj.get("tech_stack"):
                experiences_parts.append(f"- 技术栈：{proj['tech_stack']}")
            if proj.get("role"):
                experiences_parts.append(f"- 角色：{proj['role']}")
            if proj.get("description"):
                experiences_parts.append(f"- 描述：{proj['description']}")
            experiences_parts.append("")

    # 工作经历
    work_experience = data.get("work_experience", [])
    if work_experience:
        experiences_parts.append("## 实习经历")
        for work in work_experience:
            experiences_parts.append(f"### {work.get('company', '未命名公司')} - {work.get('role', '未知岗位')}")
            if work.get("period"):
                experiences_parts.append(f"- 时间：{work['period']}")
            if work.get("description"):
                experiences_parts.append(f"- 描述：{work['description']}")
            experiences_parts.append("")

    # 获奖经历
    awards = education.get("awards", [])
    if awards:
        experiences_parts.append("## 获奖经历")
        for award in awards:
            experiences_parts.append(f"### {award}")
            experiences_parts.append("")

    experiences_parts.append(f"---\n*最后更新：{date}*")

    # ── 构建 entities/skills.md ──
    skills_parts = ["# 技能列表", ""]
    skills_parts.append("> 记录用户的技能状态，用于能力评估和学习建议。")
    skills_parts.append("")

    current_skills = data.get("current_skills", [])
    if current_skills:
        skills_parts.append("## 已掌握技能")
        for skill in current_skills:
            name = skill.get("name") or skill.get("skill") or ""
            level = skill.get("level", "familiar")
            context = skill.get("context", "")
            skills_parts.append(f"### {name}")
            skills_parts.append(f"- 状态：{_format_skill_level(level)}")
            if context:
                skills_parts.append(f"- 备注：{context}")
            skills_parts.append("")

    skills_parts.append(f"---\n*最后更新：{date}*")

    # ── 构建 entities/preferences.md ──
    preferences_parts = ["# 偏好列表", ""]
    preferences_parts.append("> 记录用户的偏好和习惯，用于个性化建议。")
    preferences_parts.append("")
    preferences_parts.append("## 学习风格")
    preferences_parts.append("- 主要方式：（待填写）")
    preferences_parts.append("- 辅助方式：（待填写）")
    preferences_parts.append("")
    preferences_parts.append("## 交互偏好")
    preferences_parts.append("- 详细程度：（待填写）")
    preferences_parts.append("- 是否喜欢代码示例：（待填写）")
    preferences_parts.append("- 是否喜欢类比解释：（待填写）")
    preferences_parts.append("")
    preferences_parts.append(f"---\n*最后更新：{date}*")

    # ── 构建 entities/goals.md ──
    goals_parts = ["# 目标列表", ""]
    goals_parts.append("> 记录用户的短期和长期目标，用于规划和追踪。")
    goals_parts.append("")
    goals_parts.append("## 长期目标")
    goals_parts.append("### 找到理想工作")
    goals_parts.append(f"- 时间范围：{data.get('graduation_year', '毕业前')}")
    goals_parts.append("- 状态：进行中")
    goals_parts.append("- 进度：10%")
    goals_parts.append("- 关键里程碑：完善简历、准备面试、投递实习")
    goals_parts.append("")
    goals_parts.append(f"---\n*最后更新：{date}*")

    return {
        "memory.md": "\n".join(memory_parts),
        "entities/experiences.md": "\n".join(experiences_parts),
        "entities/skills.md": "\n".join(skills_parts),
        "entities/preferences.md": "\n".join(preferences_parts),
        "entities/goals.md": "\n".join(goals_parts),
    }


def _format_grade(grade: str | None) -> str:
    """格式化年级"""
    grade_map = {
        "freshman": "大一",
        "sophomore": "大二",
        "junior": "大三",
        "senior": "大四",
        "graduate1": "研一",
        "graduate2": "研二",
        "graduate3": "研三",
    }
    return grade_map.get(grade, grade or "（待填写）")


def _format_school_level(level: str | None) -> str:
    """格式化学校层次"""
    level_map = {
        "985": "985",
        "211": "211",
        "double_first_class": "双一流",
        "normal": "普通本科",
    }
    return level_map.get(level, level or "（待填写）")


def _format_company_level(level: str | None) -> str:
    """格式化公司类型"""
    level_map = {
        "top": "头部大厂",
        "major": "一线大厂",
        "medium": "中型企业",
        "state_owned": "国企/央企",
    }
    return level_map.get(level, level or "（待填写）")


def _format_skill_level(level: str) -> str:
    """格式化技能水平"""
    level_map = {
        "beginner": "了解",
        "familiar": "熟悉",
        "intermediate": "熟练",
        "advanced": "精通",
    }
    return level_map.get(level, level)


def write_resume_to_memory(data: dict) -> None:
    """将简历解析结果写入 .md 文件

    Args:
        data: LLM 解析的简历数据
    """
    md_contents = resume_to_markdown(data)

    # 写入 memory.md
    write_memory(md_contents["memory.md"])

    # 写入实体文件
    for entity_path, content in md_contents.items():
        if entity_path.startswith("entities/"):
            entity_type = entity_path.replace("entities/", "").replace(".md", "")
            write_entity(entity_type, content)


# ── 初始化函数 ──────────────────────────────────────


def initialize_memory() -> None:
    """初始化记忆系统

    确保目录存在，并创建默认文件（如果不存在）。
    """
    ensure_memory_dirs()

    # 创建核心记忆文件（如果不存在）
    memory_file = MEMORY_DIR / "memory.md"
    if not memory_file.exists():
        write_memory(_default_memory_template())

    # 创建实体记忆文件（如果不存在）
    for entity_type in ["skills", "experiences", "preferences", "goals", "decisions", "relationships", "status"]:
        entity_file = ENTITIES_DIR / f"{entity_type}.md"
        if not entity_file.exists():
            write_entity(entity_type, _default_entity_template(entity_type))
