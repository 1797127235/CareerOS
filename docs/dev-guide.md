# 软件工程实践指南 — 以 career-os 为例

> 不讲理论废话，只讲怎么把一个系统从"想法"变成"能用的东西"。

---

## 一、开发一个系统的本质：回答三个问题

```
1. 做什么？  → 需求
2. 怎么做？  → 设计
3. 做对了吗？→ 验证
```

大多数项目烂尾，不是因为技术不行，而是这三个问题没搞清楚就开写了。

---

## 二、需求：你到底要做什么？

### 2.1 区分"功能"和"场景"

新手常犯的错：一上来就列功能清单——"我要做简历解析、学习路径、模拟面试……"

这叫"功能视角"，它会帮你列出 20 个功能，然后每个都做一半。

正确的做法是用"场景视角"——用户会怎么用你的产品？

```
场景 1：大二学生小王，不知道选前端还是后端
  → 打开 App → 填写基本信息 → 和 AI 聊了一次职业方向
  → 得到了推荐方向和学习路径 → 每周回来看看进度

场景 2：大三学生小李，要秋招了
  → 上传简历 → AI 给出优化建议 → 修改后再上传
  → 选择目标岗位 → 生成差距分析 → 按路径学习
  → 面试前做模拟面试
```

### 2.2 MVP（最小可用版本）

一次做不完所有场景。选一个最核心的场景，把它做到"能用"：

```
career-os 的 MVP 场景应该是：
  用户注册 → 填写画像 → 和 AI 聊一次职业方向 → 得到学习路径

  不是：简历优化 + 模拟面试 + 技能评估 + 求职追踪……
```

### 2.3 怎么检验需求是否清晰？

试一个方法：把需求讲给一个不懂技术的朋友听，如果他能复述出"用户怎么用"，
说明需求清楚了。如果他说"所以到底能干什么？"，说明你还是在列功能而不是场景。

---

## 三、设计：怎么组织代码？

### 3.1 分层架构（你已经在用了）

```
请求 → 路由层(routers) → 服务层(services) → Agent层 → 数据层(models)
```

每一层的职责：

```
routers/    只管 HTTP 请求解析和返回，不做业务逻辑
services/   业务流程编排，串联各个模块
agent/      AI 相关：意图分类、LLM 调用、RAG、工具
models/     数据结构定义，和数据库交互
db/         数据库连接和基础配置
```

关键原则：**层与层之间不越级**。
  ✅ chat.py 调用 chat_service.py
  ✅ chat_service.py 调用 agent/orchestrator.py
  ❌ chat.py 直接调用 LLM（跳过了服务层）
  ❌ orchestrator.py 直接操作数据库（跳过了服务层）

### 3.2 模块划分（你做得不错）

```
career-os/
  app/backend/
    agent/          ← AI 相关的一切
    models/         ← 数据模型
    routers/        ← API 接口
    services/       ← 业务逻辑
    db/             ← 数据库
  docs/             ← 文档
  data/             ← 知识库数据
```

新增功能时，先想清楚"放哪"，再动手写。

### 3.3 API 设计原则

以你的 job_applications 为例，一个完整的 CRUD：

```
GET    /api/jobs                  → 列表（支持筛选）
POST   /api/jobs                  → 创建求职记录
GET    /api/jobs/{id}             → 详情
PUT    /api/jobs/{id}             → 更新
DELETE /api/jobs/{id}             → 删除
PATCH  /api/jobs/{id}/stage       → 更新面试阶段（特殊操作）
```

规律：
- 名词（jobs）而不是动词（getJobs）
- 用 HTTP 方法表示操作（GET/POST/PUT/DELETE）
- 特殊操作用 PATCH + 子路径

---

## 四、开发流程：怎么一步步写？

### 4.1 TDD（测试驱动开发）— 最适合你

流程：写测试 → 测试失败 → 写代码 → 测试通过 → 重构

以你的 generate_learning_path 工具为例：

```python
# 第一步：写测试（先不写实现）
# tests/test_tools.py

import pytest
from app.backend.agent.tools import generate_learning_path

@pytest.mark.asyncio
async def test_generate_learning_path_returns_nodes():
    """路径生成应该返回包含节点的字典"""
    result = await generate_learning_path({
        "target_role": "后端工程师",
        "current_level": "大二",
        "daily_time_hours": 2,
        "target_company": "字节跳动"
    })
    assert "nodes" in result  # 或者你定义的任何结构
    assert len(result["nodes"]) > 0

@pytest.mark.asyncio
async def test_generate_learning_path_handles_empty_input():
    """空输入不应该报错"""
    result = await generate_learning_path({})
    assert result is not None
```

```python
# 第二步：实现（让测试通过）
async def generate_learning_path(params: dict) -> dict:
    if not params.get("target_role"):
        return {"nodes": [], "error": "缺少目标岗位"}
    # ... LLM 调用逻辑
```

为什么先写测试？
1. 逼你想清楚"输入是什么、输出是什么"
2. 改代码后跑一遍就知道有没有搞坏
3. 给你安全感——敢重构、敢改代码

### 4.2 分支管理（Git）

```
main          ← 稳定版本，随时能跑
  └─ dev      ← 开发主分支，日常开发在这
       ├─ feat/resume-upload    ← 新功能
       ├─ feat/job-crud         ← 新功能
       └─ fix/rag-search-bug    ← 修 bug
```

流程：
```
1. git checkout dev
2. git checkout -b feat/learning-path-api
3. 写代码、写测试、跑通
4. git add . && git commit -m "feat: 添加学习路径 CRUD API"
5. git checkout dev && git merge feat/learning-path-api
6. 推到远程，确认 CI 通过
```

关键原则：main 分支永远是能跑的。出了问题就回滚，不影响别人。

### 4.3 Commit 规范

```
feat:     新功能      → feat: 添加简历上传解析接口
fix:      修 bug      → fix: 修复意图分类误判中文
refactor: 重构        → refactor: 把 orchestrator 拆分为独立模块
docs:     文档        → docs: 更新 API 文档
test:     测试        → test: 添加学习路径单元测试
chore:    杂务        → chore: 升级 fastapi 到 0.115
```

好的 commit message 让你三个月后看 git log 还能知道改了什么。

---

## 五、验证：怎么知道做对了？

### 5.1 三种测试

```
单元测试：测试单个函数/方法
  → test_classify_intent("我想学后端") == "consultation"
  → 最多、最快、最先写

集成测试：测试多个模块协作
  → 模拟一次完整对话流程：意图分类 → 路由 → LLM 调用 → 保存
  → 中等数量

端到端测试：从用户视角测试
  → 调用 /api/chat 接口，检查返回格式
  → 最少、最慢、最后写
```

### 5.2 实际验证清单

以"学习路径"功能为例：

```
□ 单元测试通过
□ 手动测试：在 Postman 或 Swagger UI 调一次接口
□ 异常测试：传空参数、传非法参数、传超长参数
□ 边界测试：路径有 0 个节点怎么办？100 个节点呢？
□ 历史测试：改完后，之前能用的功能还能用吗？
```

### 5.3 代码审查（自我审查）

写完代码后，隔几个小时再看一遍，问自己：

```
1. 有没有硬编码？（magic numbers、写死的字符串）
2. 错误处理够不够？（网络超时、数据库挂了、LLM 返回空）
3. 日志打了没有？（出了问题能排查）
4. 有没有重复代码？（能提取的提取出来）
5. 变量名够不够清晰？（别人看不看得懂）
```

---

## 六、实际操作：career-os 现在该做什么？

### 6.1 功能优先级排序

```
P0（必须有，没有就不能用）：
  □ 用户注册/登录（JWT 认证）
  □ 对话功能优化（你已有，需要完善）
  □ 知识库数据填充

P1（核心闭环）：
  □ 用户画像完善（首次使用引导填写）
  □ 学习路径生成 + 持久化
  □ 对话历史加载（跨会话记忆）

P2（增强体验）：
  □ 简历上传解析
  □ 能力评估
  □ 求职追踪

P3（锦上添花）：
  □ 模拟面试
  □ 进度提醒通知
  □ 数据可视化（雷达图、进度条）
```

### 6.2 建议的开发顺序

```
第 1 周：认证 + 画像
  - JWT 认证（注册/登录/鉴权）
  - 画像完善（引导用户填写基本信息）
  - 验证：能注册、能登录、能保存画像

第 2 周：路径闭环
  - 学习路径生成 API（对接 LLM）
  - 路径状态更新 API（开始/完成/跳过节点）
  - 验证：能生成路径、能标记进度

第 3 周：知识库
  - 准备职业领域知识数据
  - 用 ChromaDB 替换 SimpleRAG
  - 验证：RAG 检索能返回相关结果

第 4 周：简历
  - 简历上传 + PDF 解析
  - 简历优化建议
  - 验证：上传简历能解析、能给建议
```

### 6.3 每天的开发习惯

```
早上：
  1. 看昨天的 git log，回忆做到哪了
  2. 跑一遍测试，确认没挂
  3. 今天要做什么，列 2-3 个具体任务

写代码时：
  1. 先写测试，再写实现
  2. 写一个功能，提交一次（别攒一堆再提交）
  3. 遇到不确定的设计，先写在注释里或 TODO

收工前：
  1. 代码推到远程
  2. 跑一遍所有测试
  3. 在 commit message 或笔记里写"今天做了什么"
```

---

## 七、常见错误和避坑

```
错误 1：追求完美，一个功能写一周
  → 应该：先跑通一个简陋版本，再迭代优化

错误 2：不写测试，出了 bug 靠人肉排查
  → 应该：核心逻辑必须有测试，宁可功能少但可靠

错误 3：一次性写太多代码，最后跑不起来
  → 应该：每写 50 行就跑一下，确认能用

错误 4：数据库表结构反复改，前面的代码全废
  → 应该：先用 SQLite 跑通，稳定后再换 PostgreSQL

错误 5：所有功能同时开发
  → 应该：做完一个功能，测试通过，再做下一个

错误 6：不写文档，两个月后自己都看不懂
  → 应该：每个模块头部写清楚"这是干嘛的"
```

---

## 八、总结：开发好系统的核心心法

```
1. 先想清楚再动手
   → 场景 > 功能，MVP > 大而全

2. 小步快跑
   → 一个功能一个功能做，每次提交能跑

3. 测试是安全网
   → 没有测试的代码 = 定时炸弹

4. 代码是给人读的
   → 清晰 > 聪巧，能跑 > 高性能

5. 用 Git 保护自己
   → 随时能回滚，不怕搞坏

6. 文档不是形式
   → 给三个月后的自己写
```

---

*最后一条：不要想着一步到位。软件是迭代出来的，不是一次写完的。*
*你现在的 career-os 模型设计已经很好了，接下来就是把功能一个一个填进去。*
