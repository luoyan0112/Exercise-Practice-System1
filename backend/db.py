"""
数据库操作模块
"""
import json
import hashlib
from datetime import datetime
import psycopg2
import psycopg2.extras
from . import config as _config

DB_CONFIG = _config.DB_CONFIG


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def _hash_password(password):
    """简单密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


# ==================== 用户模块 ====================

def register_user(username, password, nickname=None):
    """注册用户"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, nickname) VALUES (%s, %s, %s) RETURNING id",
            (username, _hash_password(password), nickname or username)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return True, user_id, "注册成功"
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, None, "用户名已存在"
    except Exception as e:
        conn.rollback()
        return False, None, f"注册失败: {str(e)}"
    finally:
        cur.close()
        conn.close()


def login_user(username, password):
    """用户登录"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, username, nickname, password FROM users WHERE username = %s",
            (username,)
        )
        row = cur.fetchone()
        if row and row[3] == _hash_password(password):
            cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (row[0],))
            conn.commit()
            return True, {'id': row[0], 'username': row[1], 'nickname': row[2]}, "登录成功"
        elif row:
            return False, None, "密码错误"
        else:
            return False, None, "用户名不存在"
    except Exception as e:
        conn.rollback()
        return False, None, f"登录失败: {str(e)}"
    finally:
        cur.close()
        conn.close()


# ==================== 题目模块 ====================

def get_subject_id():
    """获取当前科目ID"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM subjects WHERE name = %s", (_config.CURRENT_SUBJECT,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def get_random_questions(count=None, question_type=None):
    """随机获取题目"""
    subject_id = get_subject_id()
    if not subject_id:
        return []
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        child_type_map = {
            'careful_reading': 'careful_reading_question',
            'banked_cloze': 'banked_cloze_blank',
            'long_reading': 'long_reading_question',
        }
        standalone_types = {'writing', 'translation', 'cs_choice', 'cs_comprehensive'}

        if question_type in child_type_map:
            db_child_type = child_type_map[question_type]
            query = """
                SELECT * FROM questions
                WHERE subject_id = %s AND type = %s
                ORDER BY RANDOM()
            """
            params = (subject_id, db_child_type)
        elif question_type in standalone_types:
            query = """
                SELECT * FROM questions
                WHERE subject_id = %s AND type = %s AND parent_id IS NULL
                ORDER BY RANDOM()
            """
            params = (subject_id, question_type)
        else:
            query = """
                SELECT * FROM questions
                WHERE subject_id = %s
                  AND type NOT IN ('careful_reading_passage', 'banked_cloze_passage', 'long_reading_passage')
                ORDER BY RANDOM()
            """
            params = (subject_id,)
        if count is not None:
            query += " LIMIT %s"
            params = params + (count,)
        cur.execute(query, params)
        questions = [dict(row) for row in cur.fetchall()]
        return questions
    finally:
        cur.close()
        conn.close()


def get_question_by_id(question_id):
    """获取单个题目"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT * FROM questions WHERE id = %s", (question_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()
        conn.close()


def get_child_questions(parent_id):
    """获取子题目"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("""
            SELECT * FROM questions
            WHERE parent_id = %s
            ORDER BY order_index
        """, (parent_id,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


# ==================== 答题记录模块 ====================

def save_answer_record(user_id, question_id, user_answer, is_correct, score, practice_id=None):
    """保存答题记录"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO answer_records (user_id, question_id, practice_id, user_answer, is_correct, score)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, question_id, practice_id, user_answer, is_correct, score))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"保存答题记录失败: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def create_practice_record(user_id):
    """创建一次练习会话记录"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        subject_id = get_subject_id()
        cur.execute("""
            INSERT INTO practice_records (user_id, subject_id)
            VALUES (%s, %s) RETURNING id
        """, (user_id, subject_id))
        pid = cur.fetchone()[0]
        conn.commit()
        return pid
    except Exception as e:
        conn.rollback()
        print(f"创建练习记录失败: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def finish_practice_record(practice_id, total, correct, score):
    """完成一次练习会话"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE practice_records
            SET end_time = NOW(), total_questions = %s, correct_count = %s, score = %s
            WHERE id = %s
        """, (total, correct, score, practice_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"更新练习记录失败: {e}")
    finally:
        cur.close()
        conn.close()


def get_wrong_answers(user_id, limit=50, subject_id=None):
    """获取用户的错题（可按科目过滤）"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        if subject_id:
            cur.execute("""
                SELECT DISTINCT ON (ar.question_id) ar.question_id, ar.user_answer, ar.answered_at,
                       q.id, q.type, q.content, q.options, q.answer, q.explanation, q.difficulty, q.score, q.title
                FROM answer_records ar
                JOIN questions q ON ar.question_id = q.id
                WHERE ar.user_id = %s AND ar.is_correct = FALSE AND q.subject_id = %s
                ORDER BY ar.question_id, ar.answered_at DESC
                LIMIT %s
            """, (user_id, subject_id, limit))
        else:
            cur.execute("""
                SELECT DISTINCT ON (ar.question_id) ar.question_id, ar.user_answer, ar.answered_at,
                       q.id, q.type, q.content, q.options, q.answer, q.explanation, q.difficulty, q.score, q.title
                FROM answer_records ar
                JOIN questions q ON ar.question_id = q.id
                WHERE ar.user_id = %s AND ar.is_correct = FALSE
                ORDER BY ar.question_id, ar.answered_at DESC
                LIMIT %s
            """, (user_id, limit))
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


# ==================== 笔记模块 ====================

def save_note(user_id, question_id, content, note_type='text', image_path=None):
    """保存或更新笔记"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, note_type FROM user_notes WHERE user_id = %s AND question_id = %s
        """, (user_id, question_id))
        existing = cur.fetchone()
        if existing:
            if existing[1] == 'drawing' and note_type == 'drawing':
                old = get_note_by_question(user_id, question_id)
                if old and old.get('image_path'):
                    import os
                    try:
                        os.remove(old['image_path'])
                    except:
                        pass
            cur.execute("""
                UPDATE user_notes SET content = %s, note_type = %s, image_path = %s, updated_at = NOW()
                WHERE id = %s
            """, (content, note_type, image_path, existing[0]))
        else:
            cur.execute("""
                INSERT INTO user_notes (user_id, question_id, content, note_type, image_path)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, question_id, content, note_type, image_path))
        conn.commit()
        return True, "笔记保存成功"
    except Exception as e:
        conn.rollback()
        return False, f"保存笔记失败: {str(e)}"
    finally:
        cur.close()
        conn.close()


def get_notes(user_id, limit=50):
    """获取用户的所有笔记"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("""
            SELECT n.*, q.content as question_content, q.type as question_type
            FROM user_notes n
            LEFT JOIN questions q ON n.question_id = q.id
            WHERE n.user_id = %s
            ORDER BY n.updated_at DESC
            LIMIT %s
        """, (user_id, limit))
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def get_note_by_question(user_id, question_id):
    """获取用户对某题的笔记"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("""
            SELECT * FROM user_notes
            WHERE user_id = %s AND question_id = %s
        """, (user_id, question_id))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()
        conn.close()


# ==================== 笔记本模块 ====================

def get_next_page_order(user_id):
    """获取下一页序号"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(MAX(page_order), 0) + 1 FROM user_notes WHERE user_id = %s
    """, (user_id,))
    result = cur.fetchone()[0]
    cur.close()
    conn.close()
    return result


def add_notebook_page(user_id, content='', note_type='text', image_path=None, question_id=None):
    """在笔记本中添加新页面"""
    page_order = get_next_page_order(user_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_notes (user_id, question_id, content, note_type, image_path, page_order)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, question_id, content, note_type, image_path, page_order))
        conn.commit()
        return True, page_order, "页面已添加"
    except Exception as e:
        conn.rollback()
        return False, 0, f"添加页面失败: {str(e)}"
    finally:
        cur.close()
        conn.close()


def get_notebook_pages(user_id):
    """获取笔记本所有页面，按页码升序"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("""
            SELECT n.*, q.content as question_content, q.type as question_type
            FROM user_notes n
            LEFT JOIN questions q ON n.question_id = q.id
            WHERE n.user_id = %s
            ORDER BY n.page_order ASC
        """, (user_id,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def update_notebook_page(page_id, user_id, content=None, note_type=None, image_path=None):
    """更新笔记本页面"""
    import os
    conn = get_conn()
    cur = conn.cursor()
    try:
        if image_path:
            cur.execute("SELECT image_path FROM user_notes WHERE id = %s AND user_id = %s",
                       (page_id, user_id))
            row = cur.fetchone()
            if row and row[0] and row[0] != image_path:
                try:
                    os.remove(row[0])
                except:
                    pass
        sets = []
        params = []
        if content is not None:
            sets.append("content = %s")
            params.append(content)
        if note_type is not None:
            sets.append("note_type = %s")
            params.append(note_type)
        if image_path is not None:
            sets.append("image_path = %s")
            params.append(image_path)
        if not sets:
            return False
        sets.append("updated_at = NOW()")
        params.extend([page_id, user_id])
        sql = f"UPDATE user_notes SET {', '.join(sets)} WHERE id = %s AND user_id = %s"
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"更新笔记页面失败: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def delete_notebook_page(user_id, page_id):
    """删除指定的笔记页面"""
    import os
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT image_path FROM user_notes WHERE id = %s AND user_id = %s",
                   (page_id, user_id))
        row = cur.fetchone()
        if row and row[0]:
            try:
                os.remove(row[0])
            except:
                pass
        cur.execute("DELETE FROM user_notes WHERE id = %s AND user_id = %s",
                   (page_id, user_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


# ==================== 统计模块 ====================

def get_user_stats(user_id):
    """获取用户统计信息（按当前科目过滤）"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        stats = {'subject_name': _config.CURRENT_SUBJECT}
        subject_id = get_subject_id()

        if subject_id:
            # 按科目过滤练习记录
            cur.execute("""
                SELECT COUNT(*) as total, COALESCE(SUM(total_questions), 0) as total_q,
                       COALESCE(SUM(correct_count), 0) as total_c, COALESCE(SUM(score), 0) as total_score
                FROM practice_records WHERE user_id = %s AND subject_id = %s AND end_time IS NOT NULL
            """, (user_id, subject_id))
            row = cur.fetchone()
            stats['total_practices'] = row['total']
            stats['total_questions'] = row['total_q']
            stats['total_correct'] = row['total_c']
            stats['total_score'] = row['total_score']

            if stats['total_questions'] > 0:
                stats['accuracy'] = round(stats['total_correct'] / stats['total_questions'] * 100, 1)
            else:
                stats['accuracy'] = 0

            # 按科目过滤题型统计
            cur.execute("""
                SELECT q.type, dt.name as type_name, COUNT(*) as count,
                       SUM(CASE WHEN ar.is_correct THEN 1 ELSE 0 END) as correct_count
                FROM answer_records ar
                JOIN questions q ON ar.question_id = q.id
                LEFT JOIN dict_question_types dt ON q.type = dt.code
                WHERE ar.user_id = %s AND q.subject_id = %s
                GROUP BY q.type, dt.name
                ORDER BY count DESC
            """, (user_id, subject_id))
            stats['by_type'] = [dict(row) for row in cur.fetchall()]

            # 按科目过滤近期趋势
            cur.execute("""
                SELECT DATE(start_time) as practice_date, total_questions, correct_count,
                       CASE WHEN total_questions > 0 THEN ROUND(correct_count::numeric / total_questions * 100, 1) ELSE 0 END as accuracy
                FROM practice_records
                WHERE user_id = %s AND subject_id = %s AND end_time IS NOT NULL
                ORDER BY start_time DESC LIMIT 7
            """, (user_id, subject_id))
            stats['recent_trend'] = [dict(row) for row in cur.fetchall()]
        else:
            stats.update({'total_practices': 0, 'total_questions': 0,
                         'total_correct': 0, 'total_score': 0, 'accuracy': 0,
                         'by_type': [], 'recent_trend': []})

        # 知识点掌握（已按科目过滤）
        cur.execute("""
            SELECT kp.id, kp.name,
                   COALESCE(ukp.total_attempts, 0) as attempts,
                   COALESCE(ukp.correct_attempts, 0) as correct,
                   COALESCE(ukp.familiarity, 0) as familiarity
            FROM knowledge_points kp
            LEFT JOIN user_knowledge_progress ukp ON kp.id = ukp.knowledge_point_id AND ukp.user_id = %s
            WHERE kp.subject_id = (SELECT id FROM subjects WHERE name = %s)
            ORDER BY kp.id
        """, (user_id, _config.CURRENT_SUBJECT))
        stats['knowledge_progress'] = [dict(row) for row in cur.fetchall()]

        return stats
    finally:
        cur.close()
        conn.close()


def update_knowledge_progress(user_id, question_id, is_correct):
    """更新用户知识点进度"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT knowledge_point_id FROM question_knowledge WHERE question_id = %s
        """, (question_id,))
        kp_ids = [row[0] for row in cur.fetchall()]

        for kp_id in kp_ids:
            cur.execute("""
                INSERT INTO user_knowledge_progress (user_id, knowledge_point_id, total_attempts, correct_attempts, familiarity, last_practiced)
                VALUES (%s, %s, 1, %s, %s, NOW())
                ON CONFLICT (user_id, knowledge_point_id) DO UPDATE SET
                    total_attempts = user_knowledge_progress.total_attempts + 1,
                    correct_attempts = user_knowledge_progress.correct_attempts + %s,
                    familiarity = LEAST(100, (user_knowledge_progress.correct_attempts + %s)::float / (user_knowledge_progress.total_attempts + 1) * 100),
                    last_practiced = NOW()
            """, (user_id, kp_id, 1 if is_correct else 0,
                  int(is_correct), int(is_correct), int(is_correct)))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"更新知识点进度失败: {e}")
    finally:
        cur.close()
        conn.close()
