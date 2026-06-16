# 英语刷题系统 (English CET-6 Practice System)

## 项目概述

基于 Python + PostgreSQL 的桌面刷题系统，专注大学英语六级（CET-6）题型练习。
采用**前后端分离**架构：后端 FastAPI 提供 REST API，前端 tkinter 通过 HTTP 调用。

### 技术栈

| 组件 | 技术 |
|------|------|
| GUI | tkinter + ttk |
| 后端框架 | FastAPI + uvicorn |
| 数据库 | PostgreSQL 18 + pgvector |
| 前后端通信 | HTTP (requests) |
| DB驱动 | psycopg2 |
| 图像处理 | Pillow (PIL) |
| 截图 | PIL.ImageGrab |
| 密码 | hashlib (SHA-256) |
| 虚拟环境 | Python 3.11 (venv) |

### 项目结构

```
final/
├── main.py                 # 启动入口（启动后端 + 前端）
├── requirements.txt        # Python 依赖
├── README.md               # 本文档
│
├── backend/                # 后端 API 服务
│   ├── __init__.py
│   ├── server.py           # FastAPI 路由 + 启动
│   ├── db.py               # 数据库访问层（CRUD）
│   └── config.py           # 数据库连接配置
│
├── frontend/               # 前端 GUI 客户端
│   ├── __init__.py
│   ├── gui.py              # tkinter 主程序（~2300 行）
│   ├── api_client.py       # API 客户端（与 db.py 接口兼容）
│   └── assets/
│       ├── __init__.py
│       └── notes_images/   # 绘图笔记图片（自动创建）
│
├── scripts/                # 工具脚本
│   ├── __init__.py
│   ├── init_db.py          # 数据库初始化 + CET-6 示例数据
│   └── create_ques.sql     # 原始建表 SQL（参考用）
│
├── docs/                   # 文档
│   ├── __init__.py
│   └── 数据库表结构文档.md  # 导入数据用表结构说明
│
├── venv/                   # Python 虚拟环境
├── 刷题系统.docx           # 需求文档
└── 分工报告.docx           # 分工报告
```

---

## 各文件详解

### main.py（70行）— 入口

**功能：** 先启动后端 FastAPI 服务（子进程），等待端口就绪后再启动前端 GUI。

**核心逻辑：**
```python
# 1. 启动 backend.server 作为子进程
_backend_process = subprocess.Popen(['python', '-m', 'backend.server'])
# 2. 轮询端口 8765 等待就绪
# 3. 启动 tkinter GUI
from frontend.gui import main as gui_main
gui_main()
```
退出时通过 `atexit` 自动关闭后端进程。

**启动方式：**
```bash
python main.py
```

---

### backend/ — 后端 API 服务

#### config.py（12行）— 配置

| 名称 | 值 | 说明 |
|------|-----|------|
| `DB_CONFIG` | `{'host':'127.0.0.1','database':'ENGLISH_1','user':'postgres','password':'ww123w456'}` | PostgreSQL 连接参数 |
| `CURRENT_SUBJECT` | `'英语'` | 当前科目 |

#### db.py（596行）— 数据库访问层

所有数据库 CRUD 操作的封装层。使用 `psycopg2` + `DictCursor`。

**模块划分：**

##### 用户模块
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `register_user` | username, password, nickname | `(bool, user_id, msg)` | 注册，捕获 UniqueViolation |
| `login_user` | username, password | `(bool, user_dict, msg)` | 验证密码，更新 last_login |

##### 题目模块
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_subject_id` | - | int/None | 查当前科目 ID |
| `get_random_questions` | count, question_type | `list[dict]` | 核心查题函数。`question_type` 支持 `None`(全部), `'writing'`, `'careful_reading'`, `'banked_cloze'`, `'long_reading'`, `'translation'` |
| `get_question_by_id` | question_id | dict/None | 单题查询 |
| `get_child_questions` | parent_id | `list[dict]` | 取子题（按 order_index 排序） |

##### 答题记录模块
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `save_answer_record` | user_id, q_id, answer, correct, score, practice_id | bool | 插入答题记录 |
| `create_practice_record` | user_id | int/None | 创建练习会话 |
| `finish_practice_record` | practice_id, total, correct, score | None | 完成会话 |
| `get_wrong_answers` | user_id, limit | `list[dict]` | 错题列表 |

##### 笔记模块
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `save_note` | user_id, q_id, content, note_type, image_path | `(bool, msg)` | 按题目 upsert 笔记 |
| `get_notes` | user_id, limit | `list[dict]` | 获取所有笔记 |
| `add_notebook_page` | user_id, content, type, image_path, question_id | `(bool, order, msg)` | 笔记本添加新页 |
| `get_notebook_pages` | user_id | `list[dict]` | 获取全部笔记本页 |
| `update_notebook_page` | page_id, user_id, content, type, image_path | bool | 更新笔记本页 |
| `delete_notebook_page` | user_id, page_id | bool | 删除页并清理图片 |

##### 统计模块
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_user_stats` | user_id | dict | 总练习次数/题数/正确率、分题型统计、知识点掌握度、近期趋势 |
| `update_knowledge_progress` | user_id, q_id, is_correct | None | 更新知识点掌握度 |

#### server.py — FastAPI 路由

所有路由均匹配 `api_client.py` 的函数调用。关键接口：

| 方法 | 路径 | 用途 |
|:---|:---|:---|
| POST | `/api/login` | 登录，返回 token |
| POST | `/api/register` | 注册 |
| GET | `/api/questions/random` | 随机取题 |
| GET | `/api/questions/{id}` | 取单个题目 |
| POST | `/api/practice` | 创建练习记录 |
| PUT | `/api/practice/{id}/finish` | 完成练习 |
| POST | `/api/answers` | 保存答题 |
| PUT | `/api/answers/score` | 更新自评分数 |
| GET | `/api/wrong-answers` | 错题列表 |
| GET | `/api/stats` | 统计数据 |
| POST | `/api/knowledge-progress` | 更新知识点进度 |
| GET | `/api/notebook-pages` | 笔记本页面列表 |
| POST/PUT/DELETE | `/api/notebook-pages` | 笔记本页面 CRUD |

---

### frontend/ — 前端 GUI

#### gui.py（~2300行）— GUI 主程序

完整的 tkinter GUI 应用程序，包含登录、刷题、错题本、笔记本、数据分析。

**全局常量：** `FONT_TITLE`, `FONT_NORMAL`, `FONT_SMALL`, `COLOR_PRIMARY`, `COLOR_ACCENT`, `COLOR_SUCCESS`, `COLOR_DANGER`, `COLOR_WARNING`, `COLOR_BG`, `COLOR_WHITE`

##### 类结构

```
LoginWindow                  # 登录/注册
PracticePanel                # 刷题面板（核心）
    ├── _build_question_list # 子题分组→复合题
    ├── _show_current_question  # 渲染题目（复合/独立）
    ├── _submit_answer      # 批改 + 反馈
    └── _next_question      # 子题翻页 / 下一题
WrongAnswerPanel             # 错题本
NotesPanel                   # 笔记本入口面板
StatsPanel                   # 数据分析仪表盘
PracticeDialog               # 单题重练弹窗
ScreenshotSelector           # 全屏选区工具
DrawingCanvas                # 画笔标注（自由缩放，支持撤销/重做）
NotebookWindow               # 共享笔记本（翻页，画笔标注）
MainApplication              # 主窗口（Tab 容器）
```

##### 刷题流程

```
[选择题型→开始刷题]
    │
    ▼
get_random_questions() → 获取原始题目列表
    │
    ▼
_build_question_list() → 子题按 parent_id 合并为复合题
    │
    ▼
_show_current_question()
    ├── 复合题(is_composite=True):
    │    ├── 标题: "第 X 大题 [文章标题]"
    │    ├── 文章框（浅蓝底）
    │    ├── "▸ 子题 X/Y"
    │    └── 子题内容 + A/B/C/D 选项（灰色边框卡片）
    │
    └── 独立题(is_composite=False):
         ├── 标题: "第 X 题 [题型名]"
         ├── 题目内容
         └── 答案输入（文本框/作文区）
    │
    ▼
_submit_answer()
    ├── 客观题→自动对错批改
    ├── 主观题→显示参考范文 + 自评滑块(0~满分)
    └── 保存 answer_record + 更新 knowledge_progress
```

##### DrawingCanvas 笔画流程

```
原始图片坐标 ← → 画布坐标 通过 display_scale 转换

_start_stroke / _add_point / _finish_stroke
    → 记录笔画到 strokes[]
    → 新笔画清空重做栈

_undo: strokes.pop() → push 到 redo_stack → 重绘
_redo: redo_stack.pop() → append 到 strokes → 重绘

橡皮擦模式：
    → 绘制红色十字❌指示器
    → 完成时检测相交笔迹并移除
    → 被擦除笔迹存入重做栈（可恢复）

_save:
    strokes[] 在原始全分辨率图片上 ImageDraw → 保存 PNG
```

#### api_client.py — 前后端通信模块

与 `backend/db.py` 保持**完全相同的函数名和签名**，供 `gui.py` 无缝替换导入。

所有函数将参数转为 HTTP 请求发往 `http://127.0.0.1:8765`，返回值格式与原 `db.py` 一致。

---

### scripts/ — 工具脚本

#### init_db.py（541行）— 数据库初始化

建表 + 索引 + 触发器 + CET-6 示例数据。`--force` 参数可先删表重建。

**11 张表：** `dict_question_types`, `subjects`, `knowledge_points`, `users`, `questions`, `question_knowledge`, `practice_records`, `answer_records`, `user_notes`, `user_knowledge_progress`

**示例数据：** 2 篇写作、1 篇仔细阅读（4 选择）、1 篇选词填空（10 空）、1 篇长篇阅读（5 匹配）、2 道翻译

---

## 数据库关系图

```
subjects ──┬── knowledge_points
           │
           └── questions ──┬── question_knowledge
                           │   └── knowledge_points
                           │
                           └── answer_records ──┬── practice_records
                                                │       └── users
                                                └── users

users ──┬── user_notes
        ├── practice_records
        ├── answer_records
        └── user_knowledge_progress ──┬── knowledge_points
```

---

## 运行方式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化/重置数据库
cd f:/a_study/software_tec/final
python scripts/init_db.py --force

# 3. 启动系统（自动启动后端+前端）
python main.py
```

> `main.py` 会自动在子进程中启动 `backend.server`（FastAPI），
> 等待端口 `8765` 就绪后再弹出 GUI 窗口。
> 关闭 GUI 时自动终止后端进程。

---

## AI 查询指引

### 常见问题定位

| 问题 | 应查看的文件/位置 |
|------|------------------|
| 题目显示/批改逻辑 | `frontend/gui.py` → `PracticePanel._show_current_question`, `_submit_answer` |
| 复合题子题分组 | `frontend/gui.py` → `PracticePanel._build_question_list` |
| 子题翻页 | `frontend/gui.py` → `PracticePanel._next_question` |
| 截图选区 | `frontend/gui.py` → `ScreenshotSelector` |
| 画笔标注 | `frontend/gui.py` → `DrawingCanvas`（含撤销/重做/橡皮擦） |
| 笔记本翻页+画笔 | `frontend/gui.py` → `NotebookWindow` |
| 题型筛选 | `frontend/gui.py` → `PracticePanel._start_practice` 中的 `type_map` |
| 数据库查询 | `backend/db.py` → 对应函数 |
| 数据库建表 | `scripts/init_db.py` → `init_database()` |
| 示例数据 | `scripts/init_db.py` → `insert_sample_data()` |
| API 路由定义 | `backend/server.py` |
| 前后端通信 | `frontend/api_client.py` |
| 全局样式/颜色 | `frontend/gui.py` → 顶部 `COLOR_*` 常量 |
| CET-6 题型定义 | `scripts/init_db.py` → `types_data`; `backend/db.py` → `get_random_questions()` |
| 启动流程 | `main.py` |
| 数据导入指南 | `docs/数据库表结构文档.md` |
