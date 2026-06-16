"""
初始化数据库 - 创建表结构和示例数据
"""
import json
import psycopg2

DB_CONFIG = {
    'host': '127.0.0.1',
    'database': 'ENGLISH_1',
    'user': 'postgres',
    'password': 'ww123w456'
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def drop_all_tables():
    """清理所有表（用于重新初始化）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SET session_replication_role = 'replica';")

    tables = [
        'user_knowledge_progress', 'user_notes', 'answer_records',
        'practice_records', 'question_knowledge', 'questions',
        'knowledge_points', 'users', 'subjects', 'dict_question_types'
    ]
    for t in tables:
        cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")

    cur.execute("SET session_replication_role = 'origin';")
    conn.commit()
    print("所有旧表已清理")
    cur.close()
    conn.close()

def init_database():
    conn = get_conn()
    cur = conn.cursor()

    # ========== 1. 启用扩展 ==========
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # ========== 2. 题目类型字典表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dict_question_types (
        code VARCHAR(32) PRIMARY KEY,
        name VARCHAR(64) NOT NULL
    );
    """)

    # ========== 3. 科目表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id SERIAL PRIMARY KEY,
        name VARCHAR(64) NOT NULL UNIQUE,
        description TEXT
    );
    """)

    # ========== 4. 知识点表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_points (
        id SERIAL PRIMARY KEY,
        subject_id INTEGER REFERENCES subjects(id),
        name VARCHAR(128) NOT NULL,
        description TEXT,
        parent_id INTEGER REFERENCES knowledge_points(id)
    );
    """)

    # ========== 5. 用户表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(64) NOT NULL UNIQUE,
        password VARCHAR(256) NOT NULL,
        nickname VARCHAR(64),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_login TIMESTAMPTZ
    );
    """)

    # ========== 6. 题目主表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id BIGSERIAL PRIMARY KEY,
        parent_id BIGINT NULL,
        subject_id INTEGER REFERENCES subjects(id),
        type VARCHAR(32) NOT NULL,
        title TEXT NULL,
        content TEXT NOT NULL,
        options JSONB NULL,
        answer TEXT NULL,
        explanation TEXT NULL,
        difficulty SMALLINT NULL CHECK (difficulty BETWEEN 1 AND 5),
        score FLOAT NULL,
        order_index INT NULL,
        embedding VECTOR(1024) NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT fk_questions_parent FOREIGN KEY (parent_id) REFERENCES questions(id) ON DELETE CASCADE,
        CONSTRAINT fk_questions_type FOREIGN KEY (type) REFERENCES dict_question_types(code)
    );
    """)

    # ========== 7. 题目-知识点关联表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS question_knowledge (
        id SERIAL PRIMARY KEY,
        question_id BIGINT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        knowledge_point_id INTEGER NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
        UNIQUE(question_id, knowledge_point_id)
    );
    """)

    # ========== 8. 练习记录表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS practice_records (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        subject_id INTEGER REFERENCES subjects(id),
        start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        end_time TIMESTAMPTZ,
        total_questions INT DEFAULT 0,
        correct_count INT DEFAULT 0,
        score FLOAT DEFAULT 0
    );
    """)

    # ========== 9. 答题记录表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS answer_records (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        question_id BIGINT NOT NULL REFERENCES questions(id),
        practice_id INTEGER REFERENCES practice_records(id),
        user_answer TEXT,
        is_correct BOOLEAN,
        score FLOAT,
        answered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # ========== 10. 用户笔记表（共享笔记本） ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_notes (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        question_id BIGINT REFERENCES questions(id),
        content TEXT NOT NULL DEFAULT '',
        note_type VARCHAR(16) NOT NULL DEFAULT 'text',
        image_path TEXT,
        page_order INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # ========== 11. 用户知识点进度表 ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_knowledge_progress (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        knowledge_point_id INTEGER NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
        familiarity FLOAT DEFAULT 0 CHECK (familiarity BETWEEN 0 AND 100),
        total_attempts INT DEFAULT 0,
        correct_attempts INT DEFAULT 0,
        last_practiced TIMESTAMPTZ,
        UNIQUE(user_id, knowledge_point_id)
    );
    """)

    # ========== 索引 ==========
    cur.execute("CREATE INDEX IF NOT EXISTS idx_questions_parent_id ON questions(parent_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(type);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions(subject_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_questions_created_at ON questions(created_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_answer_records_user ON answer_records(user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_answer_records_question ON answer_records(question_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_notes_user ON user_notes(user_id);")

    # ========== 自动更新时间触发器 ==========
    cur.execute("""
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    # 删除并重建触发器
    cur.execute("DROP TRIGGER IF EXISTS trigger_questions_updated_at ON questions;")
    cur.execute("""
    CREATE TRIGGER trigger_questions_updated_at
        BEFORE UPDATE ON questions
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    cur.execute("DROP TRIGGER IF EXISTS trigger_user_notes_updated_at ON user_notes;")
    cur.execute("""
    CREATE TRIGGER trigger_user_notes_updated_at
        BEFORE UPDATE ON user_notes
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    conn.commit()
    print("数据库表创建完成！")
    cur.close()
    conn.close()


def insert_sample_data():
    """插入CET-6风格示例数据"""
    conn = get_conn()
    cur = conn.cursor()

    # ========== 题目类型（CET-6真实题型） ==========
    types_data = [
        ('writing', '写作'),
        ('careful_reading_passage', '仔细阅读文章'),
        ('careful_reading_question', '仔细阅读子题'),
        ('banked_cloze_passage', '选词填空文章'),
        ('banked_cloze_blank', '选词填空空'),
        ('long_reading_passage', '长篇阅读文章'),
        ('long_reading_question', '长篇阅读子题'),
        ('translation', '翻译'),
    ]
    for code, name in types_data:
        cur.execute("""
            INSERT INTO dict_question_types (code, name)
            VALUES (%s, %s) ON CONFLICT (code) DO NOTHING;
        """, (code, name))

    # ========== 科目 ==========
    cur.execute("""
        INSERT INTO subjects (name, description)
        VALUES ('英语', '大学英语六级（CET-6）练习题')
        ON CONFLICT (name) DO NOTHING;
    """)
    cur.execute("SELECT id FROM subjects WHERE name = '英语'")
    subject_id = cur.fetchone()[0]

    # ========== 知识点 ==========
    kps = [
        ('写作', '英语写作与表达能力'),
        ('仔细阅读', '深度阅读理解与细节把握'),
        ('选词填空', '词汇辨析与上下文理解'),
        ('长篇阅读', '快速阅读与信息匹配能力'),
        ('翻译', '汉英互译能力'),
    ]
    kp_map = {}
    for name, desc in kps:
        cur.execute("""
            INSERT INTO knowledge_points (subject_id, name, description)
            VALUES (%s, %s, %s) RETURNING id;
        """, (subject_id, name, desc))
        kp_map[name] = cur.fetchone()[0]

    # ========== 写作（Writing）- 2篇 ==========
    essay_topics = [
        {
            'content': 'For this part, you are allowed 30 minutes to write an essay on the topic:\n\nThe Role of Technology in Modern Education\n\nYou should write at least 150 words but no more than 200 words.\n\nDiscuss how technology has changed the way students learn and how teachers teach. Provide specific examples to support your argument.',
            'answer': '参考范文：Technology has revolutionized modern education in profound ways. Online learning platforms, digital textbooks, and interactive educational software have made knowledge more accessible than ever before. Students can now access courses from top universities worldwide through platforms like Coursera and edX. Teachers can use multimedia tools to create engaging lessons that cater to different learning styles. However, the integration of technology in education also presents challenges, such as the digital divide and the need for digital literacy skills. In conclusion, while technology offers tremendous opportunities for education, it must be implemented thoughtfully to ensure equal access and effective learning outcomes for all students.',
            'explanation': '评分要点：内容完整性（30%）、语言准确性（30%）、结构逻辑性（20%）、词汇丰富度（20%）',
            'difficulty': 4,
            'score': 15,
            'kp': '写作'
        },
        {
            'content': 'For this part, you are allowed 30 minutes to write an essay on the topic:\n\nThe Importance of Learning a Foreign Language\n\nYou should write at least 150 words but no more than 200 words.\n\nExplain why learning a foreign language is valuable in today\'s globalized world.',
            'answer': '参考范文：In our increasingly interconnected world, learning a foreign language has become more important than ever. It not only enhances career opportunities but also broadens one\'s cultural horizons. Bilingual individuals often demonstrate improved cognitive abilities, including better problem-solving skills and mental flexibility. Furthermore, language learning fosters cross-cultural understanding and empathy, which are essential qualities in a globalized society. Therefore, I strongly believe that foreign language education should be promoted and encouraged at all levels of schooling.',
            'explanation': '评分要点：内容完整性（30%）、语言准确性（30%）、结构逻辑性（20%）、词汇丰富度（20%）',
            'difficulty': 4,
            'score': 15,
            'kp': '写作'
        },
    ]

    for eq in essay_topics:
        cur.execute("""
            INSERT INTO questions (subject_id, type, content, answer, explanation, difficulty, score)
            VALUES (%s, 'writing', %s, %s, %s, %s, %s)
            RETURNING id;
        """, (subject_id, eq['content'], eq['answer'], eq['explanation'], eq['difficulty'], eq['score']))
        qid = cur.fetchone()[0]
        if eq['kp'] in kp_map:
            cur.execute("""
                INSERT INTO question_knowledge (question_id, knowledge_point_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """, (qid, kp_map[eq['kp']]))

    # ========== 仔细阅读（Careful Reading）- 1篇文章 + 4道选择题 ==========
    careful_passage = """Climate change is one of the most pressing challenges facing humanity today. Scientists have concluded that human activities, particularly the burning of fossil fuels, are the primary drivers of the rapid warming observed since the Industrial Revolution. The consequences are far-reaching, including rising sea levels, more frequent extreme weather events, and disruptions to ecosystems worldwide. Addressing this crisis requires coordinated global action, including transitioning to renewable energy sources, improving energy efficiency, and adopting sustainable land-use practices. Individual actions, such as reducing waste and choosing sustainable transportation, also play a crucial role in the collective effort to mitigate climate change. However, the effectiveness of these measures depends heavily on government policies and international cooperation. Without strong political will and public support, even the most well-intentioned efforts may fall short of what is needed to avert the worst impacts of climate change."""

    cur.execute("""
        INSERT INTO questions (subject_id, type, title, content, difficulty, score)
        VALUES (%s, 'careful_reading_passage', 'Climate Change and Its Impacts', %s, 3, 8)
        RETURNING id;
    """, (subject_id, careful_passage))
    passage_id = cur.fetchone()[0]

    careful_questions = [
        {
            'content': 'What is identified as the primary cause of climate change?',
            'options': {'A': 'Natural weather patterns', 'B': 'Human activities like burning fossil fuels', 'C': 'Volcanic eruptions', 'D': 'Changes in solar radiation'},
            'answer': 'B',
            'explanation': 'The passage clearly states that "human activities, particularly the burning of fossil fuels, are the primary drivers."',
            'difficulty': 2,
            'score': 2,
            'order': 1
        },
        {
            'content': 'Which of the following is NOT mentioned as a consequence of climate change?',
            'options': {'A': 'Rising sea levels', 'B': 'More frequent extreme weather events', 'C': 'Increased biodiversity', 'D': 'Disruptions to ecosystems'},
            'answer': 'C',
            'explanation': 'Increased biodiversity is not mentioned; climate change tends to reduce biodiversity rather than increase it.',
            'difficulty': 3,
            'score': 2,
            'order': 2
        },
        {
            'content': 'What does the passage say about the role of individual actions?',
            'options': {'A': 'They are unimportant compared to government policies', 'B': 'They play a crucial role in collective efforts', 'C': 'They are the only effective solution', 'D': 'They have no real impact on climate change'},
            'answer': 'B',
            'explanation': 'The passage states that "individual actions... also play a crucial role in the collective effort to mitigate climate change."',
            'difficulty': 2,
            'score': 2,
            'order': 3
        },
        {
            'content': 'What does the author suggest about the effectiveness of climate change measures?',
            'options': {'A': 'Individual efforts alone are sufficient', 'B': 'Government policies and international cooperation are essential', 'C': 'Technology will solve all problems automatically', 'D': 'Climate change is not a serious threat'},
            'answer': 'B',
            'explanation': 'The passage emphasizes that effectiveness "depends heavily on government policies and international cooperation."',
            'difficulty': 3,
            'score': 2,
            'order': 4
        },
    ]

    for cq in careful_questions:
        cur.execute("""
            INSERT INTO questions (parent_id, subject_id, type, content, options, answer, explanation, difficulty, score, order_index)
            VALUES (%s, %s, 'careful_reading_question', %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (passage_id, subject_id, cq['content'], json.dumps(cq['options']), cq['answer'], cq['explanation'], cq['difficulty'], cq['score'], cq['order']))
        qid = cur.fetchone()[0]
        if '仔细阅读' in kp_map:
            cur.execute("""
                INSERT INTO question_knowledge (question_id, knowledge_point_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """, (qid, kp_map['仔细阅读']))

    # ========== 选词填空（Banked Cloze）- 1篇文章 + 10个空 ==========
    banked_passage = """Some people believe that technology has (1)______ our lives in countless ways. It has made communication faster and more (2)______, allowing people to connect across great distances instantly. However, others argue that technology has also caused some (3)______ effects. For example, many people spend too much time on social media, which can (4)______ to anxiety and depression. The constant (5)______ of information can also be overwhelming, making it difficult to focus. Despite these concerns, technology will continue to (6)______ society in the years to come. The key is to find a (7)______ between its advantages and disadvantages. Education plays a crucial role in helping people use technology (8)______ and responsibly. By developing digital literacy skills, individuals can make informed (9)______ about their technology use. Ultimately, technology is a tool that can greatly (10)______ our quality of life when used appropriately."""

    cur.execute("""
        INSERT INTO questions (subject_id, type, title, content, difficulty, score)
        VALUES (%s, 'banked_cloze_passage', 'Technology and Society', %s, 4, 20)
        RETURNING id;
    """, (subject_id, banked_passage))
    banked_id = cur.fetchone()[0]

    # 词库（15个词，正确答案用前10个）
    word_bank = {
        'A': 'transformed', 'B': 'efficient', 'C': 'negative', 'D': 'lead',
        'E': 'flow', 'F': 'shape', 'G': 'balance', 'H': 'wisely',
        'I': 'decisions', 'J': 'enhance', 'K': 'destroyed', 'L': 'ignore',
        'M': 'beneficial', 'N': 'reduce', 'O': 'random'
    }
    # 将词库信息存入第一个空题的 options 中（通过content传递）
    word_bank_text = '【词库】\n' + '  '.join(f'{k}. {word_bank[k]}' for k in sorted(word_bank.keys()))

    banked_blanks = [
        {'content': f'{word_bank_text}\n\n(1) technology has ______ our lives', 'answer': 'A',
         'explanation': '"Transformed" means changed completely, fitting the context of technology changing our lives.', 'order': 1},
        {'content': f'{word_bank_text}\n\n(2) faster and more ______', 'answer': 'B',
         'explanation': '"Efficient" describes something that works well without wasting time or energy.', 'order': 2},
        {'content': f'{word_bank_text}\n\n(3) some ______ effects', 'answer': 'C',
         'explanation': '"Negative" contrasts with the positive effects mentioned earlier in the passage.', 'order': 3},
        {'content': f'{word_bank_text}\n\n(4) can ______ to anxiety', 'answer': 'D',
         'explanation': '"Lead to" is a common collocation meaning to cause or result in something.', 'order': 4},
        {'content': f'{word_bank_text}\n\n(5) constant ______ of information', 'answer': 'E',
         'explanation': '"Flow" of information is a common expression referring to the continuous movement of data.', 'order': 5},
        {'content': f'{word_bank_text}\n\n(6) continue to ______ society', 'answer': 'F',
         'explanation': '"Shape" means to influence or mold, fitting the idea of technology influencing society.', 'order': 6},
        {'content': f'{word_bank_text}\n\n(7) find a ______ between', 'answer': 'G',
         'explanation': '"Balance" is commonly used with "find a ___ between" to describe equilibrium between two things.', 'order': 7},
        {'content': f'{word_bank_text}\n\n(8) use technology ______', 'answer': 'H',
         'explanation': '"Wisely" is an adverb meaning in a wise manner, modifying how technology is used.', 'order': 8},
        {'content': f'{word_bank_text}\n\n(9) make informed ______', 'answer': 'I',
         'explanation': '"Make decisions" is a standard collocation; "informed decisions" means decisions based on good information.', 'order': 9},
        {'content': f'{word_bank_text}\n\n(10) can greatly ______ our quality', 'answer': 'J',
         'explanation': '"Enhance" means to improve or increase the quality of something.', 'order': 10},
    ]

    for bb in banked_blanks:
        # 每个空格的选项是15个词，按字母顺序排列
        opts = {k: word_bank[k] for k in sorted(word_bank.keys())}
        cur.execute("""
            INSERT INTO questions (parent_id, subject_id, type, content, options, answer, explanation, difficulty, score, order_index)
            VALUES (%s, %s, 'banked_cloze_blank', %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (banked_id, subject_id, bb['content'], json.dumps(opts), bb['answer'], bb['explanation'], 3, 2, bb['order']))
        qid = cur.fetchone()[0]
        if '选词填空' in kp_map:
            cur.execute("""
                INSERT INTO question_knowledge (question_id, knowledge_point_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """, (qid, kp_map['选词填空']))

    # ========== 长篇阅读（Long Reading）- 1篇文章 + 5道匹配题 ==========
    long_passage = """[A] Digital transformation has become a key driver of economic growth in the 21st century. Companies across all sectors are investing heavily in new technologies to improve their operations and customer experiences. From artificial intelligence to cloud computing, these innovations are reshaping the business landscape.

[B] The education sector has also been profoundly affected by digital technologies. Online learning platforms have made education more accessible than ever before. Students in remote areas can now access the same quality of education as those in urban centers. However, the digital divide remains a significant challenge that needs to be addressed.

[C] Healthcare is another field where digital technology is making a significant impact. Telemedicine allows patients to consult with doctors remotely, saving time and resources. Electronic health records improve the efficiency and accuracy of medical diagnoses. AI-powered diagnostic tools are helping doctors detect diseases earlier than ever before.

[D] Despite the many benefits of digital transformation, there are also concerns about privacy and security. As more personal data is collected and stored online, the risk of data breaches increases. Companies must invest in robust cybersecurity measures to protect their customers' information.

[E] Looking ahead, the pace of digital transformation is likely to accelerate. Emerging technologies such as 5G networks, the Internet of Things, and quantum computing will open up new possibilities. Governments and businesses need to work together to ensure that the benefits of digital transformation are shared widely across society."""

    cur.execute("""
        INSERT INTO questions (subject_id, type, title, content, difficulty, score)
        VALUES (%s, 'long_reading_passage', 'Digital Transformation', %s, 4, 10)
        RETURNING id;
    """, (subject_id, long_passage))
    long_id = cur.fetchone()[0]

    long_questions = [
        {
            'content': 'Which paragraph discusses the challenges of unequal access to digital education?',
            'options': {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E'},
            'answer': 'B',
            'explanation': 'Paragraph B mentions "the digital divide remains a significant challenge" in education access.',
            'order': 1
        },
        {
            'content': 'Which paragraph describes the role of technology in improving medical services?',
            'options': {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E'},
            'answer': 'C',
            'explanation': 'Paragraph C discusses telemedicine, electronic health records, and AI-powered diagnostic tools.',
            'order': 2
        },
        {
            'content': 'Which paragraph talks about data protection concerns in the digital age?',
            'options': {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E'},
            'answer': 'D',
            'explanation': 'Paragraph D focuses on "concerns about privacy and security" and data breaches.',
            'order': 3
        },
        {
            'content': 'Which paragraph explains how digital technology drives economic development?',
            'options': {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E'},
            'answer': 'A',
            'explanation': 'Paragraph A states that "digital transformation has become a key driver of economic growth."',
            'order': 4
        },
        {
            'content': 'Which paragraph looks at future technological developments and their potential?',
            'options': {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E'},
            'answer': 'E',
            'explanation': 'Paragraph E discusses "emerging technologies such as 5G networks, the Internet of Things, and quantum computing."',
            'order': 5
        },
    ]

    for lq in long_questions:
        cur.execute("""
            INSERT INTO questions (parent_id, subject_id, type, content, options, answer, explanation, difficulty, score, order_index)
            VALUES (%s, %s, 'long_reading_question', %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (long_id, subject_id, lq['content'], json.dumps(lq['options']), lq['answer'], lq['explanation'], 3, 2, lq['order']))
        qid = cur.fetchone()[0]
        if '长篇阅读' in kp_map:
            cur.execute("""
                INSERT INTO question_knowledge (question_id, knowledge_point_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """, (qid, kp_map['长篇阅读']))

    # ========== 翻译（Translation）- 2道汉译英 ==========
    translation_questions = [
        {
            'content': 'Translate the following paragraph into English:\n\n"中国是一个历史悠久、文化丰富的国家。长城是世界上最著名的建筑之一，每年吸引数百万游客前来参观。近年来，中国政府高度重视环境保护，致力于实现绿色可持续发展。"',
            'answer': 'China is a country with a long history and rich culture. The Great Wall is one of the most famous structures in the world, attracting millions of visitors every year. In recent years, the Chinese government has attached great importance to environmental protection and is committed to achieving green and sustainable development.',
            'explanation': 'CET-6翻译评分要点：信息完整度、语法正确性、词汇准确性、表达连贯性。注意时态一致和专有名词大写。',
            'difficulty': 3,
            'score': 10,
            'kp': '翻译'
        },
        {
            'content': 'Translate the following paragraph into English:\n\n"随着互联网的普及，人们的生活方式发生了巨大变化。在线购物、远程办公和网络教育已经成为日常生活的重要组成部分。然而，网络安全问题也日益突出，需要引起我们的高度重视。"',
            'answer': 'With the popularization of the Internet, people\'s lifestyles have undergone tremendous changes. Online shopping, remote work, and online education have become important parts of daily life. However, cybersecurity issues are also becoming increasingly prominent and require our great attention.',
            'explanation': 'CET-6翻译评分要点：信息完整度、语法正确性、词汇准确性、表达连贯性。注意"随着"的译法和被动语态的使用。',
            'difficulty': 3,
            'score': 10,
            'kp': '翻译'
        },
    ]

    for tq in translation_questions:
        cur.execute("""
            INSERT INTO questions (subject_id, type, content, answer, explanation, difficulty, score)
            VALUES (%s, 'translation', %s, %s, %s, %s, %s)
            RETURNING id;
        """, (subject_id, tq['content'], tq['answer'], tq['explanation'], tq['difficulty'], tq['score']))
        qid = cur.fetchone()[0]
        if tq['kp'] in kp_map:
            cur.execute("""
                INSERT INTO question_knowledge (question_id, knowledge_point_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """, (qid, kp_map[tq['kp']]))

    conn.commit()
    print("CET-6 示例数据插入完成！")
    print(f"  科目: 英语 (ID: {subject_id})")
    print(f"  知识点: {len(kps)} 个")
    print(f"  写作: {len(essay_topics)} 篇")
    print(f"  仔细阅读: 1 篇文章 + {len(careful_questions)} 道选择题")
    print(f"  选词填空: 1 篇文章 + {len(banked_blanks)} 道选词题")
    print(f"  长篇阅读: 1 篇文章 + {len(long_questions)} 道匹配题")
    print(f"  翻译: {len(translation_questions)} 道")
    cur.close()
    conn.close()


if __name__ == '__main__':
    import sys
    if '--force' in sys.argv:
        print("强制重新初始化数据库...")
        drop_all_tables()
    print("开始初始化数据库...")
    init_database()
    insert_sample_data()
    print("数据库初始化完成！")
