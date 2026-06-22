"""
英语刷题系统 - 后端 API 服务 (FastAPI)
前后端分离后，前端通过 HTTP 调用本服务操作数据库
"""
import uuid
import json
import requests as http_requests
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db as db_module
from .config import set_current_subject, DEEPSEEK_API_KEY, DEEPSEEK_API_URL

app = FastAPI(title='英语刷题系统 API', version='1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ========== 简单 Token 鉴权（本地应用） ==========
_tokens: dict[str, int] = {}  # token -> user_id

def _gen_token() -> str:
    return uuid.uuid4().hex[:32]

# ========== Pydantic 请求模型 ==========

class LoginReq(BaseModel):
    username: str
    password: str

class RegisterReq(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None

class AnswerReq(BaseModel):
    user_id: int
    question_id: int
    user_answer: str
    is_correct: bool
    score: float
    practice_id: Optional[int] = None

class ScoreReq(BaseModel):
    user_id: int
    question_id: int
    score: float
    practice_id: Optional[int] = None

class KnowledgeReq(BaseModel):
    user_id: int
    question_id: int
    is_correct: bool

class NoteReq(BaseModel):
    user_id: int
    content: str = ''
    note_type: str = 'text'
    image_path: Optional[str] = None
    question_id: Optional[int] = None

class SubjectSwitchReq(BaseModel):
    name: str

class AIGenerateReq(BaseModel):
    question_type: str
    content: str
    options: Optional[str] = None
    answer: str
    explanation: Optional[str] = None
    subject: str = ''

class AIGradeReq(BaseModel):
    question_type: str
    content: str
    user_answer: str
    answer: str
    explanation: Optional[str] = None
    max_score: float = 15

class AIDiagnoseReq(BaseModel):
    user_id: int
    question_id: int
    user_answer: str
    subject: str = ''

class AIMaterialGenerateReq(BaseModel):
    user_id: int
    filename: str
    file_type: str
    content: str
    subject: str = ''
    question_type: str = 'mixed'
    question_count: int = 5
    difficulty: int = 3

class NoteUpdateReq(BaseModel):
    user_id: int
    content: Optional[str] = None
    note_type: Optional[str] = None
    image_path: Optional[str] = None

# ========== 用户 ==========

@app.post('/api/login')
def login(req: LoginReq):
    success, user, msg = db_module.login_user(req.username, req.password)
    if not success:
        raise HTTPException(400, msg)
    token = _gen_token()
    _tokens[token] = user['id']
    return {'success': True, 'token': token, 'user': user, 'msg': msg}

@app.post('/api/register')
def register(req: RegisterReq):
    success, uid, msg = db_module.register_user(req.username, req.password, req.nickname)
    if not success:
        raise HTTPException(400, msg)
    return {'success': True, 'user_id': uid, 'msg': msg}

# ========== 科目 ==========

@app.get('/api/subjects')
def list_subjects():
    """获取所有可用科目"""
    conn = db_module.get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, description FROM subjects ORDER BY id")
        rows = cur.fetchall()
        return [{'id': r[0], 'name': r[1], 'description': r[2]} for r in rows]
    finally:
        cur.close()
        conn.close()

@app.post('/api/subject/switch')
def switch_subject(req: SubjectSwitchReq):
    """切换当前科目"""
    name = req.name
    conn = db_module.get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM subjects WHERE name = %s", (name,))
        if not cur.fetchone():
            raise HTTPException(404, f'科目 "{name}" 不存在')
        set_current_subject(name)
        return {'success': True, 'subject': name}
    finally:
        cur.close()
        conn.close()

# ========== 题目 ==========

@app.get('/api/questions/random')
def get_random_questions(count: Optional[int] = None, question_type: Optional[str] = None):
    return db_module.get_random_questions(count=count, question_type=question_type)

@app.get('/api/questions/{question_id}')
def get_question_by_id(question_id: int):
    q = db_module.get_question_by_id(question_id)
    if not q:
        raise HTTPException(404, '题目不存在')
    return q

@app.get('/api/questions/{parent_id}/children')
def get_child_questions(parent_id: int):
    return db_module.get_child_questions(parent_id)

# ========== 练习记录 ==========

@app.post('/api/practice')
def create_practice(user_id: int):
    pid = db_module.create_practice_record(user_id)
    if pid is None:
        raise HTTPException(500, '创建练习记录失败')
    return {'practice_id': pid}

@app.put('/api/practice/{practice_id}/finish')
def finish_practice(practice_id: int, total: int, correct: int, score: float):
    db_module.finish_practice_record(practice_id, total, correct, score)
    return {'success': True}

# ========== 答题记录 ==========

@app.post('/api/answers')
def save_answer(req: AnswerReq):
    ok = db_module.save_answer_record(
        req.user_id, req.question_id, req.user_answer,
        req.is_correct, req.score, req.practice_id
    )
    if not ok:
        raise HTTPException(500, '保存答题记录失败')
    return {'success': True}

@app.put('/api/answers/score')
def update_answer_score(req: ScoreReq):
    """更新作文/翻译的自评分数"""
    conn = db_module.get_conn()
    cur = conn.cursor()
    try:
        if req.practice_id:
            cur.execute("""
                UPDATE answer_records SET score = %s
                WHERE user_id = %s AND question_id = %s AND practice_id = %s
            """, (req.score, req.user_id, req.question_id, req.practice_id))
        else:
            cur.execute("""
                UPDATE answer_records SET score = %s
                WHERE user_id = %s AND question_id = %s AND score = 0
                ORDER BY answered_at DESC LIMIT 1
            """, (req.score, req.user_id, req.question_id))
        conn.commit()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f'更新分数失败: {e}')
    finally:
        cur.close()
        conn.close()

# ========== 错题本 ==========

@app.get('/api/wrong-answers')
def get_wrong_answers(user_id: int, limit: int = 50):
    subject_id = db_module.get_subject_id()
    return db_module.get_wrong_answers(user_id, limit, subject_id=subject_id)

# ========== 数据分析 ==========

@app.get('/api/stats')
def get_user_stats(user_id: int):
    return db_module.get_user_stats(user_id)

# ========== 知识点进度 ==========

@app.post('/api/knowledge-progress')
def update_knowledge_progress(req: KnowledgeReq):
    db_module.update_knowledge_progress(req.user_id, req.question_id, req.is_correct)
    return {'success': True}

# ========== 笔记本 ==========

@app.get('/api/notebook-pages')
def get_notebook_pages(user_id: int):
    return db_module.get_notebook_pages(user_id)

@app.post('/api/notebook-pages')
def add_notebook_page(req: NoteReq):
    success, page_order, msg = db_module.add_notebook_page(
        req.user_id, req.content, req.note_type, req.image_path, req.question_id
    )
    if not success:
        raise HTTPException(500, msg)
    return {'success': True, 'page_order': page_order, 'msg': msg}

@app.put('/api/notebook-pages/{page_id}')
def update_notebook_page(page_id: int, req: NoteUpdateReq):
    success = db_module.update_notebook_page(
        page_id, req.user_id, req.content, req.note_type, req.image_path
    )
    if not success:
        raise HTTPException(500, '更新失败')
    return {'success': True}

@app.delete('/api/notebook-pages/{page_id}')
def delete_notebook_page(page_id: int, user_id: int):
    success = db_module.delete_notebook_page(user_id, page_id)
    if not success:
        raise HTTPException(500, '删除失败')
    return {'success': True}

# ========== 笔记（题目标注）==========

@app.get('/api/notes')
def get_notes(user_id: int, limit: int = 50):
    return db_module.get_notes(user_id, limit)

@app.post('/api/notes')
def save_note(req: NoteReq):
    success, msg = db_module.save_note(
        req.user_id, req.question_id, req.content, req.note_type, req.image_path
    )
    if not success:
        raise HTTPException(500, msg)
    return {'success': True, 'msg': msg}

# ========== AI 出题 ==========

_AI_SYSTEM_PROMPT = """你是一个出题助手。根据用户提供的题目信息，生成一道同类型、同难度的相似题目。
要求：
1. 保持与原题相同的题型和难度
2. 题目内容不同但考核的知识点相同
3. 如果是选择题，提供4个选项(A/B/C/D)，并标注正确答案
4. 如果是主观题，提供参考答案
5. 用 JSON 格式返回，格式为：{"content":"题目内容","options":"{"A":"...","B":"...","C":"...","D":"..."}","answer":"正确答案","explanation":"解析"}
6. 只返回 JSON，不要有其他文字"""

@app.post('/api/ai/generate')
def ai_generate(req: AIGenerateReq):
    """调用 DeepSeek 生成相似题目"""
    if not DEEPSEEK_API_KEY:
        raise HTTPException(400, 'DeepSeek API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY（或创建 .env 文件）')
    options_str = req.options if req.options else '无'
    if isinstance(options_str, dict):
        options_str = json.dumps(options_str, ensure_ascii=False)
    elif isinstance(options_str, str):
        try:
            json.loads(options_str)
        except:
            options_str = options_str

    user_msg = f"""原题信息：
题型：{req.question_type}
科目：{req.subject or '通用'}
题目：{req.content}
选项：{options_str}
答案：{req.answer}
解析：{req.explanation or '无'}

请生成一道同类型的相似题目。"""

    try:
        resp = http_requests.post(DEEPSEEK_API_URL, json={
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': _AI_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_msg},
            ],
            'temperature': 0.8,
            'max_tokens': 2000,
        }, headers={
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json',
        }, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        reply = data['choices'][0]['message']['content']
        # 提取 JSON
        reply = reply.strip()
        if reply.startswith('```'):
            reply = reply.split('\n', 1)[-1]
            reply = reply.rsplit('```', 1)[0]
        reply = reply.strip()
        result = json.loads(reply)
        return {'success': True, 'question': result}
    except http_requests.Timeout:
        raise HTTPException(504, 'AI 请求超时，请稍后重试')
    except http_requests.RequestException as e:
        raise HTTPException(502, f'AI 服务调用失败: {str(e)}')
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(500, f'AI 返回格式异常: {str(e)}')

_GRADE_SYSTEM_PROMPT = """你是一个评分助手。根据题目和参考答案，对用户答案进行评分。
要求：
1. 公平客观地评分，打出 0 到满分之间的分数
2. 提供简短的评价反馈
3. 用 JSON 格式返回：{"score": 分数, "feedback": "评价内容"}
4. 只返回 JSON，不要有其他文字"""

_DIAGNOSE_SYSTEM_PROMPT = """你是一名严谨、鼓励式的学习诊断导师。请根据题目、标准答案、解析和学生错误答案，判断学生为什么答错。
要求：
1. 诊断必须针对当前答案，不要泛泛讲解
2. error_type 从以下类别中选择一个：知识点缺失、概念混淆、审题错误、推理错误、记忆错误、粗心错误、语言理解错误、其他
3. knowledge_gaps 列出 0-4 个具体薄弱知识点
4. suggestions 给出 1-4 条可以执行的复习建议
5. confidence 是 0 到 1 之间的数字；证据不足时降低置信度
6. 不要责备学生，不要编造题目之外的学习经历
7. 只返回 JSON 对象，结构如下：
{"error_type":"概念混淆","summary":"一句话结论","analysis":"具体分析","knowledge_gaps":["知识点"],"suggestions":["建议"],"next_action":"下一步练习建议","confidence":0.85}"""


def _extract_json_object(reply: str):
    """兼容纯 JSON 与 Markdown 代码块形式的模型返回。"""
    text = reply.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = text.split('\n', 1)[-1]
        text = text.rsplit(fence, 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _normalize_text_list(value, max_items=4):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:200] for item in value[:max_items]
            if str(item).strip()]


def _normalize_diagnosis(result):
    if not isinstance(result, dict):
        raise ValueError('诊断结果不是 JSON 对象')
    error_type = str(result.get('error_type', '其他')).strip()[:64] or '其他'
    summary = str(result.get('summary', '')).strip()[:500]
    analysis = str(result.get('analysis', '')).strip()[:2000]
    next_action = str(result.get('next_action', '')).strip()[:500]
    if not summary:
        raise ValueError('诊断结果缺少 summary')
    try:
        confidence = float(result.get('confidence', 0))
    except (TypeError, ValueError):
        confidence = 0
    return {
        'error_type': error_type,
        'summary': summary,
        'analysis': analysis,
        'knowledge_gaps': _normalize_text_list(result.get('knowledge_gaps')),
        'suggestions': _normalize_text_list(result.get('suggestions')),
        'next_action': next_action,
        'confidence': max(0.0, min(confidence, 1.0)),
    }


@app.post('/api/ai/diagnose')
def ai_diagnose(req: AIDiagnoseReq):
    """诊断客观题错因并保存结构化结果。"""
    if not DEEPSEEK_API_KEY:
        raise HTTPException(400, 'DeepSeek API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY（或创建 .env 文件）')
    user_answer = req.user_answer.strip()
    if not user_answer:
        raise HTTPException(400, '用户答案不能为空')
    question = db_module.get_question_by_id(req.question_id)
    if not question:
        raise HTTPException(404, '题目不存在')

    options = question.get('options') or {}
    if not isinstance(options, str):
        options = json.dumps(options, ensure_ascii=False)
    user_msg = f"""科目：{req.subject or '通用'}
题型：{question.get('type', '')}
题目：{question.get('content', '')}
选项：{options or '无'}
学生答案：{user_answer}
标准答案：{question.get('answer', '')}
题目解析：{question.get('explanation', '') or '无'}

请分析这次错误最可能的原因，并给出具体改进建议。"""

    try:
        resp = http_requests.post(DEEPSEEK_API_URL, json={
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': _DIAGNOSE_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_msg},
            ],
            'temperature': 0.2,
            'max_tokens': 1200,
        }, headers={
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json',
        }, timeout=60)
        resp.raise_for_status()
        reply = resp.json()['choices'][0]['message']['content']
        diagnosis = _normalize_diagnosis(_extract_json_object(reply))
        diagnosis_id = db_module.save_ai_diagnosis(
            req.user_id, req.question_id, user_answer, diagnosis
        )
        return {
            'success': True,
            'diagnosis_id': diagnosis_id,
            'diagnosis': diagnosis,
        }
    except http_requests.Timeout:
        raise HTTPException(504, 'AI 诊断超时，请稍后重试')
    except http_requests.RequestException as e:
        raise HTTPException(502, f'AI 服务调用失败: {str(e)}')
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise HTTPException(500, f'AI 诊断结果格式异常: {str(e)}')
    except Exception as e:
        raise HTTPException(500, f'保存 AI 诊断失败: {str(e)}')


@app.get('/api/ai/diagnoses')
def list_ai_diagnoses(user_id: int, question_id: Optional[int] = None,
                      limit: int = 20):
    return db_module.get_ai_diagnoses(user_id, question_id, limit)

_MATERIAL_SYSTEM_PROMPT = """你是一名课程资料分析与命题专家。请根据提供的资料：
1. 给出忠实、结构清晰的内容总结，不添加资料中没有的事实
2. 提炼核心知识点，每个知识点包含 name 和 description
3. 生成指定数量、题型和难度的练习题
4. 选择题提供 A/B/C/D 四个选项，answer 只填选项字母
5. 判断题用 A=正确、B=错误；填空题和简答题不提供 options
6. 每道题必须给出答案和基于资料的解析
7. 只返回一个 JSON 对象，格式为：
{"title":"资料主题","summary":"总结","knowledge_points":[{"name":"知识点","description":"说明"}],"questions":[{"type":"choice","content":"题目","options":{"A":"...","B":"...","C":"...","D":"..."},"answer":"A","explanation":"解析","difficulty":3,"score":1}]}"""


def _call_material_ai(system_prompt, user_prompt, max_tokens=4000, temperature=0.2):
    resp = http_requests.post(DEEPSEEK_API_URL, json={
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': temperature,
        'max_tokens': max_tokens,
    }, headers={
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json',
    }, timeout=90)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']


def _material_chunks(content, chunk_size=12000, max_chunks=6):
    """按段落切分资料；超长内容均匀取样，避免只覆盖文件开头。"""
    paragraphs = [part.strip() for part in content.split('\n\n') if part.strip()]
    chunks = []
    current = []
    current_size = 0
    for paragraph in paragraphs:
        pieces = [paragraph[index:index + chunk_size]
                  for index in range(0, len(paragraph), chunk_size)] or ['']
        for piece in pieces:
            if current and current_size + len(piece) > chunk_size:
                chunks.append('\n\n'.join(current))
                current = []
                current_size = 0
            current.append(piece)
            current_size += len(piece) + 2
    if current:
        chunks.append('\n\n'.join(current))
    if not chunks:
        chunks = [content]
    if len(chunks) > max_chunks:
        indexes = [round(i * (len(chunks) - 1) / (max_chunks - 1))
                   for i in range(max_chunks)]
        chunks = [chunks[index] for index in indexes]
    return chunks


def _normalize_material_generation(result, question_count, difficulty):
    if not isinstance(result, dict):
        raise ValueError('AI 返回内容不是 JSON 对象')
    summary = str(result.get('summary', '')).strip()
    if not summary:
        raise ValueError('AI 返回内容缺少总结')

    knowledge_points = []
    for item in result.get('knowledge_points', [])[:20]:
        if isinstance(item, dict):
            name = str(item.get('name', '')).strip()[:120]
            description = str(item.get('description', '')).strip()[:500]
        else:
            name = str(item).strip()[:120]
            description = ''
        if name:
            knowledge_points.append({'name': name, 'description': description})

    type_aliases = {
        'multiple_choice': 'choice', '选择题': 'choice',
        '判断题': 'true_false', 'boolean': 'true_false',
        '填空题': 'fill_blank', 'fill': 'fill_blank',
        '简答题': 'short_answer', 'subjective': 'short_answer',
    }
    questions = []
    for item in result.get('questions', []):
        if not isinstance(item, dict):
            continue
        content = str(item.get('content', '')).strip()[:3000]
        answer = str(item.get('answer', '')).strip()[:2000]
        if not content or not answer:
            continue
        qtype = type_aliases.get(str(item.get('type', '')).strip(),
                                 str(item.get('type', '')).strip())
        if qtype not in ('choice', 'true_false', 'fill_blank', 'short_answer'):
            qtype = 'short_answer'
        options = item.get('options')
        if isinstance(options, list):
            options = {chr(65 + i): str(value) for i, value in enumerate(options[:4])}
        if qtype == 'true_false':
            options = {'A': '正确', 'B': '错误'}
        elif qtype == 'choice' and not isinstance(options, dict):
            qtype = 'short_answer'
            options = None
        elif qtype not in ('choice', 'true_false'):
            options = None
        try:
            item_difficulty = int(item.get('difficulty', difficulty))
        except (TypeError, ValueError):
            item_difficulty = difficulty
        questions.append({
            'type': qtype,
            'content': content,
            'options': options,
            'answer': answer,
            'explanation': str(item.get('explanation', '')).strip()[:3000],
            'difficulty': max(1, min(item_difficulty, 5)),
            'score': 1 if qtype in ('choice', 'true_false', 'fill_blank') else 5,
        })
        if len(questions) >= question_count:
            break
    if not questions:
        raise ValueError('AI 未生成有效题目')
    return {
        'title': str(result.get('title', '')).strip()[:300],
        'summary': summary[:12000],
        'knowledge_points': knowledge_points,
        'questions': questions,
    }


@app.post('/api/ai/materials/generate')
def generate_material_bank(req: AIMaterialGenerateReq):
    """分析资料、生成题目并保存到独立 AI 资料题库。"""
    if not DEEPSEEK_API_KEY:
        raise HTTPException(400, 'DeepSeek API Key 未配置')
    content = req.content.strip()
    if len(content) < 30:
        raise HTTPException(400, '资料文字过少，无法分析')
    if len(content) > 150000:
        raise HTTPException(400, '资料超过 15 万字符，请拆分后导入')
    if not 1 <= req.question_count <= 10:
        raise HTTPException(400, '生成题数应为 1-10')
    if not 1 <= req.difficulty <= 5:
        raise HTTPException(400, '难度应为 1-5')

    type_names = {
        'mixed': '混合题型（选择、判断、填空、简答合理搭配）',
        'choice': '选择题', 'true_false': '判断题',
        'fill_blank': '填空题', 'short_answer': '简答题',
    }
    requested_type = type_names.get(req.question_type, type_names['mixed'])
    try:
        if len(content) > 24000:
            notes = []
            chunks = _material_chunks(content)
            for index, chunk in enumerate(chunks, 1):
                note = _call_material_ai(
                    '你是资料提炼助手。忠实提炼本段的关键事实、概念和逻辑，只返回文本摘要。',
                    f'资料第 {index}/{len(chunks)} 段：\n{chunk}',
                    max_tokens=1200, temperature=0.1
                )
                notes.append(f'【第{index}段提炼】\n{note.strip()}')
            source = '\n\n'.join(notes)
            source_label = '以下是长资料各段的忠实提炼结果'
        else:
            source = content
            source_label = '以下是资料原文'

        prompt = f"""科目：{req.subject or '通用'}
文件名：{req.filename}
需要生成：{req.question_count} 道{requested_type}
目标难度：{req.difficulty}/5

{source_label}：
{source}

请总结整份资料、提炼知识点并生成题目。"""
        reply = _call_material_ai(
            _MATERIAL_SYSTEM_PROMPT, prompt, max_tokens=6000, temperature=0.25
        )
        generated = _normalize_material_generation(
            _extract_json_object(reply), req.question_count, req.difficulty
        )
        material_id = db_module.save_ai_material_generation(
            req.user_id, req.subject, req.filename, req.file_type,
            content, generated
        )
        material = db_module.get_ai_material(material_id, req.user_id)
        return {'success': True, 'material': material}
    except http_requests.Timeout:
        raise HTTPException(504, 'AI 分析资料超时，请稍后重试')
    except http_requests.RequestException as e:
        raise HTTPException(502, f'AI 服务调用失败: {str(e)}')
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise HTTPException(500, f'AI 返回格式异常: {str(e)}')
    except Exception as e:
        raise HTTPException(500, f'保存 AI 资料题库失败: {str(e)}')


@app.get('/api/ai/materials')
def list_material_banks(user_id: int, subject: Optional[str] = None,
                        limit: int = 50):
    return db_module.get_ai_materials(user_id, subject, limit)


@app.get('/api/ai/materials/{material_id}')
def get_material_bank(material_id: int, user_id: int):
    material = db_module.get_ai_material(material_id, user_id)
    if not material:
        raise HTTPException(404, '资料题库不存在')
    return material


@app.delete('/api/ai/materials/{material_id}')
def remove_material_bank(material_id: int, user_id: int):
    if not db_module.delete_ai_material(material_id, user_id):
        raise HTTPException(404, '资料题库不存在')
    return {'success': True}

@app.post('/api/ai/grade')
def ai_grade(req: AIGradeReq):
    """调用 DeepSeek 对主观题答案进行评分"""
    if not DEEPSEEK_API_KEY:
        raise HTTPException(400, 'DeepSeek API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY（或创建 .env 文件）')

    user_msg = f"""题目：{req.content}
参考答案：{req.answer}
评分要点：{req.explanation or '无'}
满分：{req.max_score}分

用户答案：{req.user_answer}

请根据参考答案和评分要点，对用户答案给出评分和反馈。"""

    try:
        resp = http_requests.post(DEEPSEEK_API_URL, json={
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': _GRADE_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_msg},
            ],
            'temperature': 0.3,
            'max_tokens': 1000,
        }, headers={
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json',
        }, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        reply = data['choices'][0]['message']['content'].strip()
        if reply.startswith('```'):
            reply = reply.split('\n', 1)[-1]
            reply = reply.rsplit('```', 1)[0].strip()
        result = json.loads(reply)
        return {'success': True, 'score': float(result['score']), 'feedback': result.get('feedback', '')}
    except http_requests.Timeout:
        raise HTTPException(504, 'AI 评分超时')
    except Exception as e:
        raise HTTPException(500, f'AI 评分失败: {str(e)}')

# ========== 启动入口 ==========

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8765)
