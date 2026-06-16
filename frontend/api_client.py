"""
英语刷题系统 - API 客户端模块
与 db.py 保持相同函数名和签名，供 app.py 无缝替换
"""
import requests

BASE_URL = 'http://127.0.0.1:8765'

_session = requests.Session()
_token: str | None = None


def _set_token(token: str):
    global _token
    _token = token
    _session.headers.update({'Authorization': f'Bearer {token}'})


def _get(url, **params):
    try:
        r = _session.get(f'{BASE_URL}{url}', params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f'[API GET {url}] 错误: {e}')
        raise


def _post(url, **data):
    try:
        r = _session.post(f'{BASE_URL}{url}', json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f'[API POST {url}] 错误: {e}')
        raise


def _put(url, **data):
    try:
        r = _session.put(f'{BASE_URL}{url}', json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f'[API PUT {url}] 错误: {e}')
        raise


def _delete(url, **params):
    try:
        r = _session.delete(f'{BASE_URL}{url}', params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f'[API DELETE {url}] 错误: {e}')
        raise


# ==================== 用户模块 ====================


def login_user(username, password):
    """登录，返回 (success, user_dict, msg)"""
    try:
        data = _post('/api/login', username=username, password=password)
        _set_token(data['token'])
        return True, data['user'], data['msg']
    except Exception as e:
        resp = getattr(e, 'response', None)
        if resp is not None:
            detail = resp.json().get('detail', '登录失败')
            return False, None, detail
        return False, None, f'连接后端失败: {e}'


def register_user(username, password, nickname=None):
    """注册，返回 (success, user_id, msg)"""
    try:
        data = _post('/api/register', username=username, password=password, nickname=nickname)
        return True, data['user_id'], data['msg']
    except Exception as e:
        resp = getattr(e, 'response', None)
        if resp is not None:
            detail = resp.json().get('detail', '注册失败')
            return False, None, detail
        return False, None, f'连接后端失败: {e}'


# ==================== 题目模块 ====================


# ==================== 科目模块 ====================


def get_subjects():
    """获取所有科目列表"""
    try:
        return _get('/api/subjects')
    except Exception:
        return []


def switch_subject(name):
    """切换当前科目"""
    try:
        _post('/api/subject/switch', name=name)
        return True
    except Exception as e:
        resp = getattr(e, 'response', None)
        if resp is not None and resp.status_code == 404:
            print(f'科目 "{name}" 不存在')
        return False


# ==================== AI 出题 ====================


def ai_generate_similar(question_data):
    """调用 AI 生成相似题目"""
    try:
        data = _post('/api/ai/generate', **question_data)
        if data.get('success'):
            return data.get('question')
        return None
    except Exception as e:
        resp = getattr(e, 'response', None)
        if resp is not None:
            detail = resp.json().get('detail', '生成失败')
            print(f'AI 出题失败: {detail}')
        else:
            print(f'AI 出题失败: {e}')
        return None


def ai_grade(question_data):
    """调用 AI 对主观题答案评分，返回 (score, feedback) 或 None"""
    try:
        data = _post('/api/ai/grade', **question_data)
        if data.get('success'):
            return data.get('score'), data.get('feedback', '')
        return None
    except Exception as e:
        resp = getattr(e, 'response', None)
        if resp is not None:
            print(f'AI 评分失败: {resp.json().get("detail", "")}')
        else:
            print(f'AI 评分失败: {e}')
        return None


# ==================== 题目模块 ====================


def get_random_questions(count=None, question_type=None):
    """随机获取题目"""
    try:
        return _get('/api/questions/random', count=count, question_type=question_type)
    except Exception:
        return []


def get_question_by_id(question_id):
    """获取单个题目"""
    try:
        return _get(f'/api/questions/{question_id}')
    except Exception:
        return None


def get_child_questions(parent_id):
    """获取子题目"""
    try:
        return _get(f'/api/questions/{parent_id}/children')
    except Exception:
        return []


# ==================== 练习记录模块 ====================


def create_practice_record(user_id):
    """创建练习会话，返回 practice_id"""
    try:
        data = _post('/api/practice', user_id=user_id)
        return data['practice_id']
    except Exception:
        return None


def finish_practice_record(practice_id, total, correct, score):
    """完成练习会话"""
    try:
        _put(f'/api/practice/{practice_id}/finish',
             total=total, correct=correct, score=score)
    except Exception:
        pass


# ==================== 答题记录模块 ====================


def save_answer_record(user_id, question_id, user_answer, is_correct, score, practice_id=None):
    """保存答题记录"""
    try:
        _post('/api/answers',
              user_id=user_id, question_id=question_id,
              user_answer=user_answer, is_correct=bool(is_correct),
              score=float(score), practice_id=practice_id)
        return True
    except Exception:
        return False


def update_answer_score(user_id, question_id, score, practice_id=None):
    """更新作文/翻译的自评分数"""
    try:
        _put('/api/answers/score',
             user_id=user_id, question_id=question_id,
             score=float(score), practice_id=practice_id)
        return True
    except Exception as e:
        print(f'更新作文分数失败: {e}')
        return False


def get_wrong_answers(user_id, limit=50):
    """获取错题"""
    try:
        return _get('/api/wrong-answers', user_id=user_id, limit=limit)
    except Exception:
        return []


def get_answer_history(user_id, question_id):
    """获取答题历史（暂不通过 API）"""
    return []


# ==================== 笔记模块 ====================


def save_note(user_id, question_id, content, note_type='text', image_path=None):
    """保存笔记"""
    try:
        _post('/api/notes',
              user_id=user_id, question_id=question_id,
              content=content, note_type=note_type, image_path=image_path)
        return True, '笔记保存成功'
    except Exception as e:
        resp = getattr(e, 'response', None)
        msg = resp.json().get('detail', '保存失败') if resp else str(e)
        return False, msg


def get_notes(user_id, limit=50):
    """获取所有笔记"""
    try:
        return _get('/api/notes', user_id=user_id, limit=limit)
    except Exception:
        return []


def get_note_by_question(user_id, question_id):
    """获取某题笔记（暂不通过 API）"""
    return None


# ==================== 笔记本模块 ====================


def get_notebook_pages(user_id):
    """获取笔记本所有页面"""
    try:
        return _get('/api/notebook-pages', user_id=user_id)
    except Exception:
        return []


def add_notebook_page(user_id, content='', note_type='text', image_path=None, question_id=None):
    """添加笔记本页面，返回 (success, page_order, msg)"""
    try:
        data = _post('/api/notebook-pages',
                     user_id=user_id, content=content,
                     note_type=note_type, image_path=image_path,
                     question_id=question_id)
        return True, data.get('page_order', 0), data['msg']
    except Exception as e:
        resp = getattr(e, 'response', None)
        msg = resp.json().get('detail', '添加失败') if resp else str(e)
        return False, 0, msg


def update_notebook_page(page_id, user_id, content=None, note_type=None, image_path=None):
    """更新笔记本页面"""
    try:
        _put(f'/api/notebook-pages/{page_id}',
             user_id=user_id, content=content,
             note_type=note_type, image_path=image_path)
        return True
    except Exception:
        return False


def delete_notebook_page(user_id, page_id):
    """删除笔记本页面"""
    try:
        _delete(f'/api/notebook-pages/{page_id}', user_id=user_id)
        return True
    except Exception:
        return False


# ==================== 统计模块 ====================


def get_user_stats(user_id):
    """获取用户统计"""
    try:
        return _get('/api/stats', user_id=user_id)
    except Exception:
        return {}


def update_knowledge_progress(user_id, question_id, is_correct):
    """更新知识点进度"""
    try:
        _post('/api/knowledge-progress',
              user_id=user_id, question_id=question_id, is_correct=bool(is_correct))
    except Exception:
        pass


# ==================== 兼容 db.py 的原始连接（已废弃） ====================

def get_conn():
    """前后端分离后不可用，抛出明确错误"""
    raise RuntimeError('前后端分离模式下禁止直接操作数据库连接，请使用 API 函数')
