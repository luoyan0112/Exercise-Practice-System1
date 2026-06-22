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
