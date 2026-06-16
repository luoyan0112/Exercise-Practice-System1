"""
计算机考研刷题数据初始化
向已有数据库中添加计算机考研科目和题目数据
运行方式: python scripts/init_cs_data.py
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


def insert_cs_data():
    """插入计算机考研科目 + 4个子科目 + 示例题目"""
    conn = get_conn()
    cur = conn.cursor()

    # ========== 题目类型 ==========
    cs_types = [
        ('cs_choice', '选择题'),
        ('cs_comprehensive', '综合题'),
    ]
    for code, name in cs_types:
        cur.execute("""
            INSERT INTO dict_question_types (code, name)
            VALUES (%s, %s) ON CONFLICT (code) DO NOTHING;
        """, (code, name))

    # ========== 科目 ==========
    cur.execute("""
        INSERT INTO subjects (name, description)
        VALUES ('计算机考研', '计算机学科专业基础综合（408）练习题')
        ON CONFLICT (name) DO NOTHING;
    """)
    cur.execute("SELECT id FROM subjects WHERE name = '计算机考研'")
    subject_id = cur.fetchone()[0]
    print(f'科目ID: {subject_id}')

    # ========== 知识点（4门专业课） ==========
    kp_data = [
        ('数据结构', '线性表、树、图、排序、查找等'),
        ('计算机组成原理', '数据的表示与运算、存储系统、指令系统等'),
        ('操作系统', '进程管理、内存管理、文件系统、I/O管理等'),
        ('计算机网络', '物理层、数据链路层、网络层、传输层、应用层'),
    ]
    kp_map = {}
    for name, desc in kp_data:
        cur.execute("""
            INSERT INTO knowledge_points (subject_id, name, description)
            VALUES (%s, %s, %s) RETURNING id;
        """, (subject_id, name, desc))
        kp_map[name] = cur.fetchone()[0]
        print(f'  知识点 "{name}" -> ID {kp_map[name]}')

    # ========== 示例题目 ==========

    # ---- 数据结构 ----
    ds_kp = kp_map['数据结构']
    ds_questions = [
        {
            'type': 'cs_choice', 'content': '在长度为 n 的顺序表中，删除第 i 个元素（1≤i≤n）时，需要向前移动的元素个数为？',
            'options': json.dumps({'A': 'n-i', 'B': 'n-i+1', 'C': 'n-i-1', 'D': 'i'}),
            'answer': 'A', 'explanation': '删除第i个元素，后面的n-i个元素需要前移。', 'score': 2,
        },
        {
            'type': 'cs_choice', 'content': '下列排序算法中，平均时间复杂度为 O(n log n) 的是？',
            'options': json.dumps({'A': '冒泡排序', 'B': '直接插入排序', 'C': '堆排序', 'D': '简单选择排序'}),
            'answer': 'C', 'explanation': '堆排序、归并排序、快速排序的平均时间复杂度均为 O(n log n)。', 'score': 2,
        },
        {
            'type': 'cs_choice', 'content': '一棵完全二叉树有 1001 个结点，其中叶子结点的个数为？',
            'options': json.dumps({'A': '500', 'B': '501', 'C': '250', 'D': '251'}),
            'answer': 'B', 'explanation': '完全二叉树中，叶子结点数 = ⌈n/2⌉ = ⌈1001/2⌉ = 501。', 'score': 2,
        },
        {
            'type': 'cs_comprehensive', 'content': '请简述哈希表解决冲突的两种主要方法，并比较其优缺点。',
            'answer': '开放定址法：线性探测、平方探测等，优点是不需要额外空间，缺点是容易产生聚集。链地址法：将同义词链入同一链表，优点是处理简单、删除方便，缺点是需要额外指针空间。',
            'score': 10,
        },
    ]

    # ---- 计算机组成原理 ----
    co_kp = kp_map['计算机组成原理']
    co_questions = [
        {
            'type': 'cs_choice', 'content': '在补码表示中，若机器字长为8位，则 -128 的补码表示为？',
            'options': json.dumps({'A': '10000000', 'B': '11111111', 'C': '00000000', 'D': '10000001'}),
            'answer': 'A', 'explanation': '-128 的补码是 10000000，这是8位补码能表示的最小负数。', 'score': 2,
        },
        {
            'type': 'cs_choice', 'content': 'Cache 的地址映射方式中，块冲突概率最低的是？',
            'options': json.dumps({'A': '直接映射', 'B': '全相联映射', 'C': '组相联映射', 'D': '都一样'}),
            'answer': 'B', 'explanation': '全相联映射允许主存块映射到Cache任意位置，冲突概率最低，但硬件实现最复杂。', 'score': 2,
        },
        {
            'type': 'cs_choice', 'content': 'CPU 中程序计数器（PC）的功能是？',
            'options': json.dumps({'A': '存放当前指令', 'B': '存放下一条指令地址', 'C': '存放运算结果', 'D': '存放中断向量'}),
            'answer': 'B', 'explanation': 'PC 存放下一条将要执行的指令的地址。', 'score': 2,
        },
    ]

    # ---- 操作系统 ----
    os_kp = kp_map['操作系统']
    os_questions = [
        {
            'type': 'cs_choice', 'content': '下列调度算法中，可能产生"饥饿"现象的是？',
            'options': json.dumps({'A': '先来先服务', 'B': '时间片轮转', 'C': '优先级调度', 'D': '多级反馈队列'}),
            'answer': 'C', 'explanation': '静态优先级调度中，低优先级进程可能永远得不到CPU，产生"饥饿"。', 'score': 2,
        },
        {
            'type': 'cs_choice', 'content': '在请求分页系统中，LRU 置换算法选择换出的页面是？',
            'options': json.dumps({'A': '最近最少使用的', 'B': '最久未使用的', 'C': '最先调入的', 'D': '访问次数最少的'}),
            'answer': 'A', 'explanation': 'LRU（Least Recently Used）选择最近最少使用的页面换出。', 'score': 2,
        },
        {
            'type': 'cs_comprehensive', 'content': '请说明进程与程序的主要区别。',
            'answer': '1. 程序是静态的指令集合，进程是程序的一次动态执行过程。2. 进程有生命周期（创建-运行-终止），程序可长期保存。3. 进程有PCB（进程控制块）作为存在标志。4. 一个程序可对应多个进程，一个进程可包含多个程序。',
            'score': 8,
        },
    ]

    # ---- 计算机网络 ----
    cn_kp = kp_map['计算机网络']
    cn_questions = [
        {
            'type': 'cs_choice', 'content': 'TCP/IP 参考模型中，传输层的主要协议是？',
            'options': json.dumps({'A': 'IP 和 ICMP', 'B': 'TCP 和 UDP', 'C': 'HTTP 和 FTP', 'D': 'ARP 和 RARP'}),
            'answer': 'B', 'explanation': '传输层主要协议是 TCP（可靠传输）和 UDP（不可靠传输）。', 'score': 2,
        },
        {
            'type': 'cs_choice', 'content': '在CSMA/CD中，若争用期长度为 51.2μs，数据传输速率为 10Mbps，则最短帧长为？',
            'options': json.dumps({'A': '512bit', 'B': '64Byte', 'C': '256bit', 'D': '128Byte'}),
            'answer': 'B', 'explanation': '最短帧长 = 争用期 × 数据速率 = 51.2μs × 10Mbps = 512bit = 64Byte。', 'score': 2,
        },
        {
            'type': 'cs_choice', 'content': '在 TCP 拥塞控制中，当发生超时重传时，拥塞窗口将如何变化？',
            'options': json.dumps({'A': '减半', 'B': '重置为1', 'C': '不变', 'D': '增加1'}),
            'answer': 'B', 'explanation': '超时重传时，慢开始门限设为当前窗口一半，拥塞窗口重置为1，重新开始慢开始。', 'score': 2,
        },
    ]

    all_questions = [
        ('数据结构', ds_kp, ds_questions),
        ('计算机组成原理', co_kp, co_questions),
        ('操作系统', os_kp, os_questions),
        ('计算机网络', cn_kp, cn_questions),
    ]

    total = 0
    for kp_name, kp_id, questions in all_questions:
        for q in questions:
            cur.execute("""
                INSERT INTO questions (subject_id, type, content, options, answer, explanation, score)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """, (subject_id, q['type'], q['content'],
                  q.get('options'), q['answer'], q.get('explanation'), q.get('score', 2)))
            qid = cur.fetchone()[0]
            # 关联知识点
            cur.execute("""
                INSERT INTO question_knowledge (question_id, knowledge_point_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """, (qid, kp_id))
            total += 1
            print(f'  [{kp_name}] 题目 {qid}: {q["content"][:40]}...')

    conn.commit()
    cur.close()
    conn.close()
    print(f'\n共插入 {total} 道计算机考研题目')
    print('完成！')


if __name__ == '__main__':
    insert_cs_data()
