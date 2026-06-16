-- =============================================
-- 1. 启用 pgvector 扩展
-- =============================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================
-- 2. 题目类型字典表（可选，便于维护）
-- =============================================
CREATE TABLE IF NOT EXISTS dict_question_types (
    code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(64) NOT NULL
);

-- 预置常用题目类型
INSERT INTO dict_question_types (code, name) VALUES
    ('choice', '选择题'),
    ('cloze_blank', '完形填空空'),
    ('reading_question', '阅读理解子题'),
    ('essay', '作文'),
    ('reading_passage', '阅读理解文章'),
    ('cloze_passage', '完形填空文章')
ON CONFLICT (code) DO NOTHING;

-- =============================================
-- 3. 题目主表
-- =============================================
CREATE TABLE IF NOT EXISTS questions (
    id BIGSERIAL PRIMARY KEY,
    parent_id BIGINT NULL,
    type VARCHAR(32) NOT NULL,
    title TEXT NULL,
    content TEXT NOT NULL,
    options JSONB NULL,
    answer TEXT NULL,
    explanation TEXT NULL,
    difficulty SMALLINT NULL CHECK (difficulty BETWEEN 1 AND 5),
    score FLOAT NULL,
    order_index INT NULL,
    embedding VECTOR(1024) NULL,   -- 向量维度根据嵌入模型调整，此处以1536为例
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- 外键约束：parent_id 引用 questions.id
    CONSTRAINT fk_questions_parent FOREIGN KEY (parent_id) REFERENCES questions(id) ON DELETE CASCADE,
    -- 检查：type 必须在字典表存在（可选，若不需要严格约束可注释）
    CONSTRAINT fk_questions_type FOREIGN KEY (type) REFERENCES dict_question_types(code)
);

-- =============================================
-- 4. 索引（性能优化）
-- =============================================

-- 父子题查询索引
CREATE INDEX IF NOT EXISTS idx_questions_parent_id ON questions(parent_id);

-- 题目类型查询索引（用于过滤）
CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(type);

-- 难度级别索引（便于按难度筛选）
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);

-- 创建时间索引（用于按时间排序）
CREATE INDEX IF NOT EXISTS idx_questions_created_at ON questions(created_at);

-- 向量相似度搜索索引（HNSW 方式，pgvector 0.5.0+ 支持）
-- 若 pgvector 版本较低或不支持 HNSW，可替换为 IVFFlat 索引
-- 注意：建立索引前需保证已有数据，或先建索引后插入数据（HNSW 支持增量）
CREATE INDEX IF NOT EXISTS idx_questions_embedding ON questions 
    USING hnsw (embedding vector_cosine_ops);

-- 可选：IVFFlat 索引（如果 HNSW 不可用，取消注释并注释上面一行）
-- CREATE INDEX IF NOT EXISTS idx_questions_embedding ON questions 
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =============================================
-- 5. 自动更新时间戳触发器（可选）
-- =============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_questions_updated_at ON questions;
CREATE TRIGGER trigger_questions_updated_at
    BEFORE UPDATE ON questions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- 6. 注释（便于理解字段含义）
-- =============================================
COMMENT ON TABLE questions IS '题目主表，支持独立题目及父子结构（如阅读理解文章+子题）';
COMMENT ON COLUMN questions.id IS '题目唯一ID';
COMMENT ON COLUMN questions.parent_id IS '父题ID，NULL表示独立题目或文章/题干；非NULL表示属于某个父题（如阅读理解子题、完形填空空）';
COMMENT ON COLUMN questions.type IS '题目类型，关联 dict_question_types.code';
COMMENT ON COLUMN questions.title IS '题目标题或文章标题（可选）';
COMMENT ON COLUMN questions.content IS '题目内容：选择题的问题、完形填空空的具体句子、文章正文、作文题目等';
COMMENT ON COLUMN questions.options IS '选项，仅选择题使用，JSON格式如 {"A":"答案A","B":"答案B"}';
COMMENT ON COLUMN questions.answer IS '正确答案：选择题存"A"或"A,B"，完形填空空存单词，阅读理解子题存答案文本，作文存参考范文或要点';
COMMENT ON COLUMN questions.explanation IS '题目解析（可选）';
COMMENT ON COLUMN questions.difficulty IS '难度等级，1-5，数值越大越难';
COMMENT ON COLUMN questions.score IS '本题分值';
COMMENT ON COLUMN questions.order_index IS '同一父题下的排序序号，用于阅读理解/完形填空的题目顺序';
COMMENT ON COLUMN questions.embedding IS '题目文本的向量表示，维度由嵌入模型决定（示例为1536），用于相似度查询';
COMMENT ON COLUMN questions.created_at IS '创建时间';
COMMENT ON COLUMN questions.updated_at IS '更新时间';