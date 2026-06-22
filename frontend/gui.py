"""
英语刷题系统 - 主应用程序
基于 tkinter 的 GUI 系统
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, colorchooser
import json
import os
import queue
import threading
from datetime import datetime
from PIL import Image, ImageGrab, ImageTk
from . import api_client as db_module


# ==================== 全局样式 ====================
FONT_TITLE = ('Microsoft YaHei', 14, 'bold')
FONT_NORMAL = ('Microsoft YaHei', 11)
FONT_SMALL = ('Microsoft YaHei', 9)
COLOR_PRIMARY = '#2c3e50'
COLOR_ACCENT = '#3498db'
COLOR_SUCCESS = '#27ae60'
COLOR_DANGER = '#e74c3c'
COLOR_WARNING = '#f39c12'
COLOR_BG = '#f5f6fa'
COLOR_WHITE = '#ffffff'


class LoginWindow:
    """登录/注册窗口"""

    def __init__(self):
        self.window = tk.Tk()
        self.window.title('刷题系统 - 登录')
        self.window.geometry('480x380')
        self.window.configure(bg=COLOR_BG)
        self.window.resizable(False, False)

        # 居中显示
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 480) // 2
        y = (self.window.winfo_screenheight() - 380) // 2
        self.window.geometry(f'+{x}+{y}')

        self.current_user = None
        self._build_ui()

    def _build_ui(self):
        """构建UI"""
        # 标题
        title_frame = tk.Frame(self.window, bg=COLOR_PRIMARY, height=80)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)

        tk.Label(title_frame, text='刷题系统', font=FONT_TITLE,
                 fg=COLOR_WHITE, bg=COLOR_PRIMARY).pack(expand=True)

        # 登录表单
        form_frame = tk.Frame(self.window, bg=COLOR_BG, padx=60, pady=30)
        form_frame.pack(fill='both', expand=True)

        tk.Label(form_frame, text='用户名:', font=FONT_NORMAL,
                 bg=COLOR_BG, anchor='w').pack(fill='x', pady=(10, 2))
        self.entry_username = tk.Entry(form_frame, font=FONT_NORMAL, bd=2, relief='groove')
        self.entry_username.pack(fill='x', ipady=4)

        tk.Label(form_frame, text='密码:', font=FONT_NORMAL,
                 bg=COLOR_BG, anchor='w').pack(fill='x', pady=(10, 2))
        self.entry_password = tk.Entry(form_frame, font=FONT_NORMAL, show='*', bd=2, relief='groove')
        self.entry_password.pack(fill='x', ipady=4)

        # 按钮
        btn_frame = tk.Frame(form_frame, bg=COLOR_BG)
        btn_frame.pack(fill='x', pady=20)

        tk.Button(btn_frame, text='登  录', font=FONT_NORMAL, bg=COLOR_ACCENT, fg=COLOR_WHITE,
                  bd=0, padx=20, pady=6, command=self._login).pack(side='left', expand=True, padx=5)
        tk.Button(btn_frame, text='注  册', font=FONT_NORMAL, bg=COLOR_SUCCESS, fg=COLOR_WHITE,
                  bd=0, padx=20, pady=6, command=self._register).pack(side='right', expand=True, padx=5)

        # 回车键触发登录
        self.window.bind('<Return>', lambda e: self._login())

    def _login(self):
        """登录"""
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        if not username or not password:
            messagebox.showwarning('提示', '请输入用户名和密码')
            return
        success, user, msg = db_module.login_user(username, password)
        if success:
            self.current_user = user
            self.window.destroy()
        else:
            messagebox.showerror('登录失败', msg)

    def _register(self):
        """注册"""
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        if not username or not password:
            messagebox.showwarning('提示', '请输入用户名和密码')
            return
        if len(password) < 3:
            messagebox.showwarning('提示', '密码至少3位')
            return
        success, _, msg = db_module.register_user(username, password)
        if success:
            messagebox.showinfo('注册成功', f'用户 "{username}" 注册成功！请登录。')
        else:
            messagebox.showerror('注册失败', msg)

    def run(self):
        self.window.mainloop()
        return self.current_user


TYPE_NAMES = {
    'writing': '写作', 'translation': '翻译',
    'careful_reading_question': '仔细阅读',
    'banked_cloze_blank': '选词填空',
    'long_reading_question': '长篇阅读',
    'cs_choice': '选择题', 'cs_comprehensive': '综合题',
}

SUBJECT_TYPE_MAP = {
    '英语': {
        '全部': None,
        '写作': 'writing',
        '仔细阅读': 'careful_reading',
        '选词填空': 'banked_cloze',
        '长篇阅读': 'long_reading',
        '翻译': 'translation',
    },
    '计算机考研': {
        '全部': None,
        '选择题': 'cs_choice',
        '综合题': 'cs_comprehensive',
    },
}

class PracticePanel:
    """刷题面板"""

    def __init__(self, parent, user, subject='英语'):
        self.parent = parent
        self.user = user
        self.subject = subject
        self.current_questions = []
        self.current_index = 0
        self.practice_id = None
        self.total_questions = 0
        self.correct_count = 0
        self.total_score = 0
        self.answered = False
        self.answer_states = {}

        self._build_ui()

    def _build_ui(self):
        """构建刷题界面"""
        # 顶部控制栏
        control_frame = tk.Frame(self.parent, bg=COLOR_BG, pady=10)
        control_frame.pack(fill='x')

        tk.Label(control_frame, text='刷题模式', font=FONT_TITLE,
                 bg=COLOR_BG, fg=COLOR_PRIMARY).pack(side='left', padx=10)

        # 题型筛选（按科目动态）
        tk.Label(control_frame, text='题型:', font=FONT_NORMAL,
                 bg=COLOR_BG).pack(side='left', padx=(20, 5))
        type_options = list(SUBJECT_TYPE_MAP.get(self.subject, SUBJECT_TYPE_MAP['英语']).keys())
        self.type_var = tk.StringVar(value='全部')
        type_combo = ttk.Combobox(control_frame, textvariable=self.type_var,
                                  values=type_options,
                                  state='readonly', width=12, font=FONT_NORMAL)
        type_combo.pack(side='left')

        tk.Button(control_frame, text='开始刷题', font=FONT_NORMAL,
                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=15, pady=4,
                  command=self._start_practice).pack(side='left', padx=15)

        # 进度信息
        self.progress_label = tk.Label(control_frame, text='', font=FONT_NORMAL,
                                       bg=COLOR_BG, fg=COLOR_PRIMARY)
        self.progress_label.pack(side='right', padx=10)

        # 主内容区（滚动）
        content_frame = tk.Frame(self.parent, bg=COLOR_WHITE, bd=1, relief='groove')
        content_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        canvas = tk.Canvas(content_frame, bg=COLOR_WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient='vertical', command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg=COLOR_WHITE)

        self.scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw', width=canvas.winfo_width())
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 让canvas宽度自适应
        def _on_configure(e):
            canvas.itemconfig(1, width=e.width)
        canvas.bind('<Configure>', _on_configure)
        # 鼠标滚轮滚动
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', _on_mousewheel)

        self.canvas = canvas

        # 底部提交区域
        self.bottom_frame = tk.Frame(self.parent, bg=COLOR_BG, pady=10)
        self.bottom_frame.pack(fill='x')

        self.prev_btn = tk.Button(self.bottom_frame, text='上一题', font=FONT_NORMAL,
                                  bg='#7f8c8d', fg=COLOR_WHITE, bd=0, padx=20, pady=6,
                                  state='disabled', command=self._previous_question)
        self.prev_btn.pack(side='left', padx=10)

        self.submit_btn = tk.Button(self.bottom_frame, text='提交答案', font=FONT_NORMAL,
                                    bg=COLOR_SUCCESS, fg=COLOR_WHITE, bd=0, padx=30, pady=6,
                                    state='disabled', command=self._submit_answer)
        self.submit_btn.pack(side='left', padx=10)

        self.next_btn = tk.Button(self.bottom_frame, text='下一题', font=FONT_NORMAL,
                                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=30, pady=6,
                                  state='disabled', command=self._next_question)
        self.next_btn.pack(side='left', padx=10)

        tk.Button(self.bottom_frame, text='📓 笔记本', font=FONT_NORMAL,
                  bg='#d35400', fg=COLOR_WHITE, bd=0, padx=15, pady=6,
                  command=self._open_notebook).pack(side='left', padx=5)

        self.result_frame = tk.Frame(self.bottom_frame, bg=COLOR_BG)
        self.result_frame.pack(side='right', padx=10)

        # 初始化提示
        self._show_welcome()

    def _clear_content(self):
        """清除内容区域"""
        for w in self.scrollable_frame.winfo_children():
            w.destroy()

    def _show_welcome(self):
        """显示欢迎信息"""
        self._clear_content()
        tk.Label(self.scrollable_frame, text='欢迎使用刷题系统！',
                 font=('Microsoft YaHei', 16, 'bold'),
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(pady=50)
        tk.Label(self.scrollable_frame, text='选择题型（可选），点击"开始刷题"即可练习全部题目',
                 font=FONT_NORMAL, fg='#7f8c8d', bg=COLOR_WHITE).pack()
        self.progress_label.config(text='')
        self.result_frame.config(bg=COLOR_BG)
        for w in self.result_frame.winfo_children():
            w.destroy()
        self.submit_btn.config(state='disabled')
        self.next_btn.config(state='disabled')
        self.prev_btn.config(state='disabled')

    @staticmethod
    def _parse_options(options):
        """统一解析 options 字段，返回 dict {key: text} 格式"""
        if not options:
            return {}
        if isinstance(options, str):
            try:
                options = json.loads(options)
            except json.JSONDecodeError:
                return {}
        if isinstance(options, list):
            # 列表格式: ["A. text", "B. text"] 或 [{"key":"A","text":"..."}]
            result = {}
            for item in options:
                if isinstance(item, dict):
                    k = item.get('key', item.get('letter', ''))
                    result[k] = item.get('text', item.get('value', ''))
                elif isinstance(item, str) and len(item) >= 3 and item[1] == '.':
                    result[item[0]] = item[2:].strip()
                else:
                    result[chr(65 + len(result))] = str(item)  # A, B, C...
            return result
        if isinstance(options, dict):
            return options
        return {}

    def _build_question_list(self, raw_questions):
        """将原始题目列表处理为练习项目列表：
           - 子题（有 parent_id）按父题分组，合并为复合题
           - 独立题保持原样
        返回 [(item_type, data)] 其中 data 是 dict
        """
        children = [q for q in raw_questions if q.get('parent_id')]
        standalone = [q for q in raw_questions if not q.get('parent_id')]

        # 按 parent_id 分组子题，并按 order_index 排序
        from collections import OrderedDict
        groups = OrderedDict()
        for c in children:
            pid = c['parent_id']
            if pid not in groups:
                groups[pid] = []
            groups[pid].append(c)
        for pid in groups:
            groups[pid].sort(key=lambda x: x.get('order_index', 0))

        items = []
        # 复合题
        for pid, child_list in groups.items():
            parent = db_module.get_question_by_id(pid)
            if parent:
                items.append({
                    'is_composite': True,
                    'parent': parent,
                    'children': child_list,
                    'child_idx': 0,
                })
        # 独立题
        for q in standalone:
            items.append({
                'is_composite': False,
                'question': q,
            })
        return items

    def _start_practice(self):
        """开始新的练习——获取全部符合条件的题目"""
        label = self.type_var.get()

        type_map = SUBJECT_TYPE_MAP.get(self.subject, SUBJECT_TYPE_MAP['英语'])
        db_type = type_map.get(label, None)

        raw = db_module.get_random_questions(count=None, question_type=db_type)
        if not raw:
            messagebox.showinfo('提示', '当前没有符合条件的题目')
            return

        self.current_questions = self._build_question_list(raw)
        self.current_index = 0
        # total_questions = 大题数（用于进度显示）, total_indiv = 独立小题数（用于正确率统计）
        self.total_questions = len(self.current_questions)
        self.total_indiv = sum(
            len(item['children']) if item['is_composite'] else 1
            for item in self.current_questions
        )
        self.correct_count = 0
        self.total_score = 0
        self.answered = False
        self.answer_states = {}

        self.practice_id = db_module.create_practice_record(self.user['id'])

        self.submit_btn.config(state='normal')
        self.next_btn.config(state='disabled')
        self.prev_btn.config(state='disabled')
        self._show_current_question()

    def _get_current_q(self):
        """获取当前正在作答的题目 dict（独立题→自身, 复合题→当前子题）"""
        item = self.current_questions[self.current_index]
        if item['is_composite']:
            return item['children'][item['child_idx']]
        return item['question']

    def _show_current_question(self):
        """显示当前题目（复合题带子题翻页）"""
        if self.current_index >= self.total_questions:
            self._show_result_summary()
            return

        self._clear_content()
        self.answered = False
        self.submit_btn.config(state='normal')
        self.next_btn.config(state='disabled')
        for w in self.result_frame.winfo_children():
            w.destroy()
        self.result_frame.config(bg=COLOR_BG)

        try:
            self._render_current_question()
            q = self._get_current_q()
            state = self.answer_states.get(q.get('id'))
            if state:
                self._restore_answer_state(q, state)
            self._update_previous_button()
        except Exception as e:
            import traceback
            traceback.print_exc()
            err_text = f'⚠ 题目渲染出错\n{type(e).__name__}: {str(e)}'
            tk.Label(self.scrollable_frame,
                     text=err_text,
                     font=FONT_NORMAL, fg=COLOR_DANGER,
                     bg=COLOR_WHITE, justify='left',
                     wraplength=600).pack(pady=40)
            self.submit_btn.config(state='disabled')

    def _update_previous_button(self):
        """根据当前位置更新上一题按钮。"""
        if not self.current_questions:
            self.prev_btn.config(state='disabled')
            return
        if self.current_index >= self.total_questions:
            has_previous = self.total_questions > 0
        else:
            item = self.current_questions[self.current_index]
            has_previous = self.current_index > 0 or (
                item['is_composite'] and item.get('child_idx', 0) > 0
            )
        self.prev_btn.config(state='normal' if has_previous else 'disabled')

    def _previous_question(self):
        """上一题；支持复合题子题和练习完成页返回。"""
        if not self.current_questions:
            return
        if self.current_index >= self.total_questions:
            self.current_index = self.total_questions - 1
            item = self.current_questions[self.current_index]
            if item['is_composite']:
                item['child_idx'] = len(item['children']) - 1
            self._show_current_question()
            return

        item = self.current_questions[self.current_index]
        if item['is_composite'] and item.get('child_idx', 0) > 0:
            item['child_idx'] -= 1
        elif self.current_index > 0:
            self.current_index -= 1
            previous_item = self.current_questions[self.current_index]
            if previous_item['is_composite']:
                previous_item['child_idx'] = len(previous_item['children']) - 1
        else:
            return
        self._show_current_question()

    def _debug_question_data(self, q, label='题目'):
        """调试输出题目数据结构（仅在控制台）"""
        print(f'\n=== {label} data ===')
        print(f'  id: {q.get("id", "N/A")}')
        print(f'  type: {q.get("type", "N/A")}')
        print(f'  has content: {"content" in q}')
        print(f'  content type: {type(q.get("content")).__name__ if q.get("content") is not None else "None"}')
        print(f'  content len: {len(str(q.get("content", "")))}')
        print(f'  has options: {"options" in q}')
        print(f'  options type: {type(q.get("options")).__name__ if q.get("options") is not None else "None"}')
        print(f'  options raw: {str(q.get("options"))[:200]}')
        print(f'  all keys: {list(q.keys())}')
        print('=' * 40)

    def _render_current_question(self):
        """渲染当前题目内容（由 _show_current_question 调用，带异常保护）"""
        item = self.current_questions[self.current_index]

        if item['is_composite']:
            # ===== 复合题：显示父文章 + 子题翻页 =====
            parent = item['parent']
            children = item['children']
            child_idx = item['child_idx']
            q = children[child_idx] if children else None
            if q is None:
                raise ValueError(f'子题列表为空 (parent_id={parent.get("id", "?")})')
            self._debug_question_data(q, '子题')
            self._debug_question_data(parent, '父文章')

            type_name = TYPE_NAMES.get(q['type'], q['type'])

            self.progress_label.config(
                text=f'第 {self.current_index + 1}/{self.total_questions} 大题 ({child_idx+1}/{len(children)}子题)  |  正确: {self.correct_count}  |  得分: {self.total_score}')

            # 标题
            header = tk.Frame(self.scrollable_frame, bg=COLOR_ACCENT, pady=8, padx=15)
            header.pack(fill='x')
            parent_title = parent.get('title', type_name)
            tk.Label(header, text=f'第 {self.current_index + 1} 大题  [{parent_title}]',
                     font=('Microsoft YaHei', 12, 'bold'),
                     fg=COLOR_WHITE, bg=COLOR_ACCENT).pack(anchor='w')

            # 父文章内容
            passage_frame = tk.Frame(self.scrollable_frame, bg='#eaf2f8', bd=1,
                                     relief='groove', padx=15, pady=10)
            passage_frame.pack(fill='x', padx=15, pady=5)
            tk.Label(passage_frame, text='【文章】', font=('Microsoft YaHei', 10, 'bold'),
                     fg=COLOR_ACCENT, bg='#eaf2f8').pack(anchor='w')
            tk.Label(passage_frame, text=parent['content'], font=FONT_SMALL,
                     fg=COLOR_PRIMARY, bg='#eaf2f8',
                     wraplength=630, justify='left', anchor='w').pack(fill='x', pady=3)

            # 分隔+子题号
            sub_header = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, padx=15)
            sub_header.pack(fill='x', pady=(5, 0))
            colors_bg = ['#fef9e7', '#e8f8f5', '#f5eef8', '#fdedec']
            bg_color = colors_bg[child_idx % len(colors_bg)]
            tk.Label(sub_header, text=f'▸ 子题 {child_idx + 1}/{len(children)}',
                     font=('Microsoft YaHei', 11, 'bold'),
                     fg='#7d6608', bg=COLOR_WHITE).pack(anchor='w')

            # 子题内容
            q_frame = tk.Frame(self.scrollable_frame, bg=bg_color, bd=1,
                               relief='groove', padx=15, pady=8)
            q_frame.pack(fill='x', padx=15, pady=3)
            tk.Label(q_frame, text=q['content'], font=FONT_NORMAL,
                     fg=COLOR_PRIMARY, bg=bg_color,
                     wraplength=630, justify='left', anchor='w').pack(fill='x')

            # 选项
            answer_frame = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, padx=15, pady=8)
            answer_frame.pack(fill='x')
            self.answer_var = tk.StringVar()
            tk.Label(answer_frame, text='请选择答案:', font=('Microsoft YaHei', 11, 'bold'),
                     fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')

            try:
                options = self._parse_options(q.get('options'))
                if options:
                    self.option_buttons = []
                    opt_frame = tk.Frame(answer_frame, bg=COLOR_WHITE)
                    opt_frame.pack(fill='x', pady=3)
                    for key in sorted(options.keys()):
                        btn_frame = tk.Frame(opt_frame, bg=COLOR_BG, bd=1,
                                             relief='groove', padx=10, pady=5)
                        btn_frame.pack(fill='x', pady=3)
                        btn = tk.Radiobutton(btn_frame, text=f"{key}. {options[key]}",
                                             variable=self.answer_var, value=key,
                                             font=FONT_NORMAL, bg=COLOR_BG, anchor='w',
                                             indicatoron=0, width=60, height=2,
                                             selectcolor=COLOR_ACCENT)
                        btn.pack(fill='x')
                        self.option_buttons.append(btn)
                else:
                    tk.Label(answer_frame, text='（该题目暂无选项）', font=FONT_SMALL,
                             fg='#95a5a6', bg=COLOR_WHITE).pack(anchor='w')
            except Exception as e:
                tk.Label(answer_frame, text=f'⚠ 选项加载失败: {str(e)}', font=FONT_SMALL,
                         fg=COLOR_DANGER, bg=COLOR_WHITE).pack(anchor='w')
                print(f'选项渲染异常: {e}')
        else:
            # ===== 独立题 =====
            q = item['question']

            type_name = TYPE_NAMES.get(q['type'], q['type'])

            self.progress_label.config(
                text=f'第 {self.current_index + 1}/{self.total_questions} 题  |  正确: {self.correct_count}  |  得分: {self.total_score}')

            header = tk.Frame(self.scrollable_frame, bg=COLOR_ACCENT, pady=8, padx=15)
            header.pack(fill='x')
            tk.Label(header, text=f'第 {self.current_index + 1} 题  [{type_name}]',
                     font=('Microsoft YaHei', 12, 'bold'),
                     fg=COLOR_WHITE, bg=COLOR_ACCENT).pack(anchor='w')

            # 题目内容
            content_frame = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, padx=15, pady=10)
            content_frame.pack(fill='x')
            tk.Label(content_frame, text=q['content'], font=FONT_NORMAL,
                     fg=COLOR_PRIMARY, bg=COLOR_WHITE,
                     wraplength=650, justify='left', anchor='w').pack(fill='x')

            # 答案输入
            answer_frame = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, padx=15, pady=10)
            answer_frame.pack(fill='x')
            self.answer_var = tk.StringVar()

            if q['type'] == 'cs_choice':
                # 选择题：渲染选项
                try:
                    options = self._parse_options(q.get('options'))
                    if options:
                        self.option_buttons = []
                        opt_frame = tk.Frame(answer_frame, bg=COLOR_WHITE)
                        opt_frame.pack(fill='x', pady=3)
                        for key in sorted(options.keys()):
                            btn_frame = tk.Frame(opt_frame, bg=COLOR_BG, bd=1,
                                                 relief='groove', padx=10, pady=5)
                            btn_frame.pack(fill='x', pady=3)
                            btn = tk.Radiobutton(btn_frame, text=f"{key}. {options[key]}",
                                                 variable=self.answer_var, value=key,
                                                 font=FONT_NORMAL, bg=COLOR_BG, anchor='w',
                                                 indicatoron=0, width=60, height=2,
                                                 selectcolor=COLOR_ACCENT)
                            btn.pack(fill='x')
                            self.option_buttons.append(btn)
                    else:
                        tk.Label(answer_frame, text='（该题目暂无选项）', font=FONT_SMALL,
                                 fg='#95a5a6', bg=COLOR_WHITE).pack(anchor='w')
                except Exception as e:
                    tk.Label(answer_frame, text=f'⚠ 选项加载失败', font=FONT_SMALL,
                             fg=COLOR_DANGER, bg=COLOR_WHITE).pack(anchor='w')
            elif q['type'] in ('translation', 'cs_comprehensive'):
                label = '请写出译文:' if q['type'] == 'translation' else '请作答:'
                tk.Label(answer_frame, text=label, font=('Microsoft YaHei', 11, 'bold'),
                         fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')
                self.fill_entry = tk.Text(answer_frame, height=5 if q['type'] == 'translation' else 8,
                                          font=FONT_NORMAL, bd=2, relief='groove', wrap='word')
                self.fill_entry.pack(fill='x', pady=5)
            elif q['type'] == 'writing':
                tk.Label(answer_frame, text='请撰写作文:', font=('Microsoft YaHei', 11, 'bold'),
                         fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')
                self.essay_text = scrolledtext.ScrolledText(answer_frame, height=12,
                                                            font=FONT_NORMAL, wrap='word',
                                                            bd=2, relief='groove')
                self.essay_text.pack(fill='x', pady=5)

        # 滚动到顶部
        self.canvas.yview_moveto(0)

    def _open_notebook(self):
        """打开共享笔记本"""
        NotebookWindow(self.parent, self.user, subject=getattr(self, 'subject', ''))

    def _get_user_answer(self, q):
        """获取用户输入的答案"""
        if q['type'] in ('careful_reading_question', 'banked_cloze_blank', 'long_reading_question', 'cs_choice'):
            return self.answer_var.get().strip()
        elif q['type'] in ('translation', 'cs_comprehensive'):
            return self.fill_entry.get('1.0', 'end-1c').strip()
        elif q['type'] == 'writing':
            return self.essay_text.get('1.0', 'end-1c').strip()
        return ''

    def _grade_answer(self, q, user_answer):
        """批改答案"""
        if q['type'] in ('careful_reading_question', 'banked_cloze_blank', 'long_reading_question', 'cs_choice'):
            return user_answer.upper() == q['answer'].strip().upper()
        elif q['type'] in ('translation', 'cs_comprehensive'):
            # 主观题：展示参考答案，不自动判分
            return None
        elif q['type'] == 'writing':
            return None
        return False

    def _restore_answer_state(self, q, state):
        """恢复已答题目的输入、批改结果和 AI 诊断。"""
        user_answer = state.get('user_answer', '')
        self.answered = True
        self.submit_btn.config(state='disabled')
        self.next_btn.config(state='normal')

        if q['type'] in ('careful_reading_question', 'banked_cloze_blank',
                         'long_reading_question', 'cs_choice'):
            self.answer_var.set(user_answer)
            for button in getattr(self, 'option_buttons', []):
                button.config(state='disabled')
        elif q['type'] in ('translation', 'cs_comprehensive'):
            self.fill_entry.insert('1.0', user_answer)
            self.fill_entry.config(state='disabled')
        elif q['type'] == 'writing':
            self.essay_text.insert('1.0', user_answer)
            self.essay_text.config(state='disabled')

        for widget in self.result_frame.winfo_children():
            widget.destroy()
        is_correct = state.get('is_correct')
        if is_correct is True:
            text = '✓ 已回答正确'
            color = COLOR_SUCCESS
        elif is_correct is False:
            text = '✗ 已回答错误'
            color = COLOR_DANGER
        else:
            score = state.get('score', 0)
            text = f'已完成作答 · 得分 {score}'
            color = COLOR_ACCENT
        tk.Label(
            self.result_frame, text=text, font=('Microsoft YaHei', 11, 'bold'),
            fg=color, bg=COLOR_BG
        ).pack(side='left', padx=10)

        if is_correct is False:
            self._show_answer_feedback(q, user_answer)
            self._show_saved_ai_diagnosis(q, state)
        elif is_correct is None:
            if state.get('score_pending'):
                self.next_btn.config(state='disabled')
                self._show_essay_scoring(q, user_answer, q.get('score', 15))
                return
            history_frame = tk.Frame(
                self.scrollable_frame, bg='#fef9e7', bd=1,
                relief='groove', padx=15, pady=8
            )
            history_frame.pack(fill='x', padx=15, pady=5)
            tk.Label(
                history_frame, text='【你的作答】',
                font=('Microsoft YaHei', 10, 'bold'),
                fg='#7d6608', bg='#fef9e7'
            ).pack(anchor='w')
            tk.Label(
                history_frame, text=user_answer, font=FONT_SMALL,
                fg=COLOR_PRIMARY, bg='#fef9e7', wraplength=630,
                justify='left'
            ).pack(anchor='w', pady=3)
            self._show_answer_feedback(q, user_answer)

    def _show_saved_ai_diagnosis(self, q, state):
        """展示缓存诊断；缓存没有时从数据库读取最近一次匹配记录。"""
        diagnosis = state.get('diagnosis')
        if not diagnosis and state.get('diagnosis_status') != 'loading':
            records = db_module.get_ai_diagnoses(
                self.user['id'], question_id=q['id'], limit=5
            )
            diagnosis = next((
                item for item in records
                if str(item.get('user_answer', '')).strip() ==
                str(state.get('user_answer', '')).strip()
            ), records[0] if records else None)
            if diagnosis:
                state['diagnosis'] = diagnosis
                state['diagnosis_status'] = 'done'

        frame = tk.Frame(
            self.scrollable_frame, bg='#f5eef8', bd=1,
            relief='groove', padx=15, pady=10
        )
        frame.pack(fill='x', padx=15, pady=5)
        if diagnosis:
            self._render_ai_diagnosis(frame, diagnosis)
        elif state.get('diagnosis_status') == 'loading':
            tk.Label(
                frame, text='🤖 AI 仍在分析这次错误，稍后再返回即可查看',
                font=FONT_SMALL, fg='#8e44ad', bg='#f5eef8'
            ).pack(anchor='w')
        else:
            error = state.get('diagnosis_error') or '暂未生成诊断'
            tk.Label(
                frame, text=f'AI 错因诊断：{error}',
                font=FONT_SMALL, fg='#7f8c8d', bg='#f5eef8',
                wraplength=640, justify='left'
            ).pack(anchor='w')

    def _submit_answer(self):
        """提交答案"""
        if self.answered:
            return

        q = self._get_current_q()
        user_answer = self._get_user_answer(q)

        if not user_answer:
            messagebox.showwarning('提示', '请先输入答案')
            return

        self.answered = True
        self.submit_btn.config(state='disabled')

        # 批改
        is_correct = self._grade_answer(q, user_answer)
        answer_state = {
            'user_answer': user_answer,
            'is_correct': is_correct,
            'score': 0,
            'diagnosis': None,
            'diagnosis_status': '',
            'diagnosis_error': '',
            'score_pending': q['type'] in ('writing', 'translation', 'cs_comprehensive'),
        }
        self.answer_states[q['id']] = answer_state

        # 显示结果
        for w in self.result_frame.winfo_children():
            w.destroy()

        if q['type'] in ('writing', 'translation', 'cs_comprehensive'):
            # ===== 主观题：分数制评价 =====
            max_score = q.get('score', 15)

            # 先保存答题记录（暂存答案）
            db_module.save_answer_record(
                self.user['id'], q['id'], user_answer,
                True, 0, self.practice_id
            )

            if q['type'] in ('writing', 'cs_comprehensive'):
                # AI 自动批改
                result_label = tk.Label(self.result_frame,
                    text='🤖 AI 正在评分...', font=FONT_NORMAL, fg='#8e44ad', bg=COLOR_BG)
                result_label.pack(side='left', padx=10)
                self.result_frame.update()

                grade_data = {
                    'question_type': q['type'], 'content': q.get('content', ''),
                    'user_answer': user_answer, 'answer': q.get('answer', ''),
                    'explanation': q.get('explanation', ''),
                    'max_score': max_score,
                }
                ai_result = db_module.ai_grade(grade_data)
                if ai_result:
                    ai_score, ai_feedback = ai_result
                    answer_state['score'] = ai_score
                    answer_state['feedback'] = ai_feedback
                    answer_state['score_pending'] = False
                    self.total_score += ai_score
                    db_module.update_answer_score(self.user['id'], q['id'], ai_score, self.practice_id)
                    self._show_ai_scoring(q, user_answer, ai_score, max_score, ai_feedback)
                else:
                    result_label.config(text='AI 评分失败，请自评', fg=COLOR_DANGER)
                    self._show_essay_scoring(q, user_answer, max_score)
            else:
                # 翻译：自评
                result_label = tk.Label(self.result_frame, text='请参考译文并给自己评分',
                    font=('Microsoft YaHei', 11, 'bold'), fg=COLOR_WARNING, bg=COLOR_BG)
                result_label.pack(side='left', padx=10)
                self._show_essay_scoring(q, user_answer, max_score)

        elif is_correct:
            result_color = COLOR_SUCCESS
            result_text = '✓ 回答正确！'
            self.correct_count += 1
            actual_score = q.get('score', 0) or 0
            answer_state['score'] = actual_score
            self.total_score += actual_score

            db_module.save_answer_record(
                self.user['id'], q['id'], user_answer,
                True, actual_score, self.practice_id
            )
            db_module.update_knowledge_progress(self.user['id'], q['id'], True)

            result_label = tk.Label(self.result_frame, text=result_text,
                                    font=('Microsoft YaHei', 12, 'bold'),
                                    fg=result_color, bg=COLOR_BG)
            result_label.pack(side='left', padx=10)
        else:
            result_color = COLOR_DANGER
            result_text = '✗ 回答错误'
            actual_score = 0
            answer_state['score'] = 0

            db_module.save_answer_record(
                self.user['id'], q['id'], user_answer,
                False, 0, self.practice_id
            )
            db_module.update_knowledge_progress(self.user['id'], q['id'], False)

            result_label = tk.Label(self.result_frame, text=result_text,
                                    font=('Microsoft YaHei', 12, 'bold'),
                                    fg=result_color, bg=COLOR_BG)
            result_label.pack(side='left', padx=10)
            self._show_answer_feedback(q, user_answer)
            self._start_ai_diagnosis(q, user_answer)

        # 更新进度
        self.progress_label.config(
            text=f'第 {self.current_index + 1}/{self.total_questions} 题  |  正确: {self.correct_count}  |  得分: {self.total_score}')

        # 启用下一题按钮
        self.next_btn.config(
            state='disabled' if answer_state.get('score_pending') else 'normal'
        )

    def _show_answer_feedback(self, q, user_answer):
        """显示答题反馈"""
        # 在题目下方显示答案解析
        feedback_frame = tk.Frame(self.scrollable_frame, bg='#fdedec', bd=1,
                                  relief='groove', padx=15, pady=10)
        feedback_frame.pack(fill='x', padx=15, pady=5)

        if q['type'] in ('writing', 'translation', 'cs_comprehensive'):
            label_text = {'writing': '【参考范文】', 'translation': '【参考译文】', 'cs_comprehensive': '【参考答案】'}.get(q['type'], '【参考答案】')
            tk.Label(feedback_frame, text=label_text,
                     font=('Microsoft YaHei', 10, 'bold'),
                     fg=COLOR_DANGER, bg='#fdedec').pack(anchor='w')
            tk.Label(feedback_frame, text=q.get('answer', ''), font=FONT_SMALL,
                     fg=COLOR_PRIMARY, bg='#fdedec', wraplength=650,
                     justify='left').pack(anchor='w', pady=5)
            tk.Label(feedback_frame, text=f'评分要点: {q.get("explanation", "")}',
                     font=FONT_SMALL, fg='#7f8c8d', bg='#fdedec',
                     wraplength=650, justify='left').pack(anchor='w')
        else:
            tk.Label(feedback_frame, text=f'你的答案: {user_answer}',
                     font=FONT_NORMAL, fg=COLOR_DANGER, bg='#fdedec').pack(anchor='w')
            tk.Label(feedback_frame, text=f'正确答案: {q.get("answer", "")}',
                     font=FONT_NORMAL, fg=COLOR_SUCCESS, bg='#fdedec').pack(anchor='w')
            if q.get('explanation'):
                tk.Label(feedback_frame, text=f'解析: {q["explanation"]}',
                         font=FONT_SMALL, fg='#7f8c8d', bg='#fdedec',
                         wraplength=650, justify='left').pack(anchor='w', pady=3)

        # 滚动到底部看到反馈
        self.scrollable_frame.update_idletasks()
        self.canvas.yview_moveto(1)

    def _start_ai_diagnosis(self, q, user_answer):
        """在后台请求 AI 错因诊断，并在当前题目下展示结果。"""
        state = self.answer_states.setdefault(q['id'], {
            'user_answer': user_answer, 'is_correct': False, 'score': 0
        })
        state['diagnosis_status'] = 'loading'
        state['diagnosis_error'] = ''
        diagnosis_frame = tk.Frame(
            self.scrollable_frame, bg='#f5eef8', bd=1,
            relief='groove', padx=15, pady=10
        )
        diagnosis_frame.pack(fill='x', padx=15, pady=5)
        tk.Label(
            diagnosis_frame, text='🤖 AI 正在分析这次错误...',
            font=('Microsoft YaHei', 11, 'bold'),
            fg='#8e44ad', bg='#f5eef8'
        ).pack(anchor='w')
        tk.Label(
            diagnosis_frame, text='可以继续操作，诊断完成后会自动显示',
            font=FONT_SMALL, fg='#7f8c8d', bg='#f5eef8'
        ).pack(anchor='w', pady=(3, 0))

        result_queue = queue.Queue(maxsize=1)

        def worker():
            result = db_module.ai_diagnose(
                self.user['id'], q['id'], user_answer,
                subject=getattr(self, 'subject', '')
            )
            result_queue.put(result)

        def poll_result():
            try:
                diagnosis, error = result_queue.get_nowait()
            except queue.Empty:
                try:
                    if self.parent.winfo_exists():
                        self.parent.after(120, poll_result)
                except tk.TclError:
                    pass
                return

            if self.answer_states.get(q['id']) is not state:
                return
            state['diagnosis'] = diagnosis
            state['diagnosis_status'] = 'done' if diagnosis else 'error'
            state['diagnosis_error'] = error
            try:
                frame_exists = bool(diagnosis_frame.winfo_exists())
            except tk.TclError:
                return
            if not frame_exists:
                try:
                    current_q = self._get_current_q()
                except (IndexError, KeyError):
                    return
                if current_q.get('id') == q.get('id'):
                    self._show_current_question()
                return

            for widget in diagnosis_frame.winfo_children():
                widget.destroy()
            if diagnosis:
                self._render_ai_diagnosis(diagnosis_frame, diagnosis)
            else:
                tk.Label(
                    diagnosis_frame,
                    text=f'AI 错因诊断暂不可用：{error or "未知错误"}',
                    font=FONT_SMALL, fg=COLOR_DANGER, bg='#f5eef8',
                    wraplength=650, justify='left'
                ).pack(anchor='w')
            self.scrollable_frame.update_idletasks()

        threading.Thread(target=worker, daemon=True).start()
        self.parent.after(120, poll_result)
        self.scrollable_frame.update_idletasks()
        self.canvas.yview_moveto(1)

    def _render_ai_diagnosis(self, parent, diagnosis):
        """渲染结构化诊断结果。"""
        header = tk.Frame(parent, bg='#f5eef8')
        header.pack(fill='x')
        tk.Label(
            header, text='🤖 AI 错因诊断',
            font=('Microsoft YaHei', 11, 'bold'),
            fg='#8e44ad', bg='#f5eef8'
        ).pack(side='left')
        confidence = float(diagnosis.get('confidence', 0) or 0) * 100
        tk.Label(
            header,
            text=f'{diagnosis.get("error_type", "其他")} · 置信度 {confidence:.0f}%',
            font=FONT_SMALL, fg='#7d3c98', bg='#eadcf0',
            padx=8, pady=2
        ).pack(side='right')

        tk.Label(
            parent, text=diagnosis.get('summary', ''),
            font=('Microsoft YaHei', 10, 'bold'),
            fg=COLOR_PRIMARY, bg='#f5eef8',
            wraplength=640, justify='left'
        ).pack(anchor='w', pady=(8, 4))

        analysis = diagnosis.get('analysis', '')
        if analysis:
            tk.Label(
                parent, text=f'原因分析：{analysis}',
                font=FONT_SMALL, fg=COLOR_PRIMARY, bg='#f5eef8',
                wraplength=640, justify='left'
            ).pack(anchor='w', pady=2)

        gaps = diagnosis.get('knowledge_gaps') or []
        if gaps:
            tk.Label(
                parent, text=f'薄弱知识点：{"、".join(gaps)}',
                font=FONT_SMALL, fg=COLOR_WARNING, bg='#f5eef8',
                wraplength=640, justify='left'
            ).pack(anchor='w', pady=2)

        suggestions = diagnosis.get('suggestions') or []
        if suggestions:
            tk.Label(
                parent, text='改进建议：',
                font=('Microsoft YaHei', 9, 'bold'),
                fg=COLOR_SUCCESS, bg='#f5eef8'
            ).pack(anchor='w', pady=(5, 0))
            for index, suggestion in enumerate(suggestions, 1):
                tk.Label(
                    parent, text=f'{index}. {suggestion}',
                    font=FONT_SMALL, fg=COLOR_PRIMARY, bg='#f5eef8',
                    wraplength=620, justify='left'
                ).pack(anchor='w', padx=(12, 0), pady=1)

        next_action = diagnosis.get('next_action', '')
        if next_action:
            tk.Label(
                parent, text=f'下一步：{next_action}',
                font=('Microsoft YaHei', 9, 'bold'),
                fg=COLOR_ACCENT, bg='#f5eef8',
                wraplength=640, justify='left'
            ).pack(anchor='w', pady=(6, 0))

    def _show_essay_scoring(self, q, user_answer, max_score):
        """作文评分界面：显示参考范文 + 自评分数输入"""
        # 参考范文框
        ref_frame = tk.Frame(self.scrollable_frame, bg='#eaf2f8', bd=1,
                             relief='groove', padx=15, pady=10)
        ref_frame.pack(fill='x', padx=15, pady=5)

        tk.Label(ref_frame, text='【参考范文】',
                 font=('Microsoft YaHei', 11, 'bold'),
                 fg=COLOR_ACCENT, bg='#eaf2f8').pack(anchor='w')
        tk.Label(ref_frame, text=q.get('answer', ''),
                 font=FONT_NORMAL, fg=COLOR_PRIMARY, bg='#eaf2f8',
                 wraplength=630, justify='left', anchor='w').pack(fill='x', pady=5)

        # 评分要点
        if q.get('explanation'):
            tk.Label(ref_frame, text=f'评分要点: {q["explanation"]}',
                     font=FONT_SMALL, fg='#7f8c8d', bg='#eaf2f8',
                     wraplength=630, justify='left').pack(anchor='w', pady=2)

        # 你的作文
        your_frame = tk.Frame(self.scrollable_frame, bg='#fef9e7', bd=1,
                              relief='groove', padx=15, pady=10)
        your_frame.pack(fill='x', padx=15, pady=5)

        tk.Label(your_frame, text='【你的作文】',
                 font=('Microsoft YaHei', 11, 'bold'),
                 fg='#7d6608', bg='#fef9e7').pack(anchor='w')
        tk.Label(your_frame, text=user_answer,
                 font=FONT_NORMAL, fg=COLOR_PRIMARY, bg='#fef9e7',
                 wraplength=630, justify='left', anchor='w').pack(fill='x', pady=5)

        # 自评分数
        score_frame = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, bd=1,
                               relief='groove', padx=15, pady=12)
        score_frame.pack(fill='x', padx=15, pady=5)

        tk.Label(score_frame, text='✏️ 自我评分',
                 font=('Microsoft YaHei', 11, 'bold'),
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')

        scale_row = tk.Frame(score_frame, bg=COLOR_WHITE)
        scale_row.pack(fill='x', pady=8)

        tk.Label(scale_row, text='评分:', font=FONT_NORMAL,
                 bg=COLOR_WHITE).pack(side='left', padx=5)

        self.essay_score_var = tk.IntVar(value=max_score)
        score_spin = tk.Spinbox(scale_row, from_=0, to=max_score,
                                textvariable=self.essay_score_var,
                                width=5, font=('Microsoft YaHei', 14, 'bold'),
                                justify='center', bd=2, relief='groove')
        score_spin.pack(side='left', padx=10)

        tk.Label(scale_row, text=f'分（满分 {max_score} 分）',
                 font=FONT_NORMAL, fg='#7f8c8d',
                 bg=COLOR_WHITE).pack(side='left')

        # 滑块
        slider = tk.Scale(score_frame, from_=0, to=max_score,
                          orient='horizontal', variable=self.essay_score_var,
                          length=400, showvalue=False,
                          bg=COLOR_WHITE, bd=0, highlightthickness=0)
        slider.pack(fill='x', padx=10)

        # 评分确认按钮
        confirm_btn = tk.Button(score_frame, text='确认评分',
                                font=('Microsoft YaHei', 11, 'bold'),
                                bg=COLOR_SUCCESS, fg=COLOR_WHITE, bd=0,
                                padx=25, pady=5,
                                command=lambda: self._confirm_essay_score(q))
        confirm_btn.pack(pady=5)

        # 滚动到底部
        self.scrollable_frame.update_idletasks()
        self.canvas.yview_moveto(1)

    def _confirm_essay_score(self, q):
        """确认作文评分"""
        score = self.essay_score_var.get()
        max_score = q.get('score', 15)
        if score < 0 or score > max_score:
            messagebox.showwarning('提示', f'分数应在 0-{max_score} 之间')
            return

        # 累加分数
        self.total_score += score
        if q.get('id') in self.answer_states:
            self.answer_states[q['id']]['score'] = score
            self.answer_states[q['id']]['score_pending'] = False
        self.next_btn.config(state='normal')

        # 更新进度显示
        self.progress_label.config(
            text=f'第 {self.current_index + 1}/{self.total_questions} 题  |  得分: {self.total_score}')

        # 在结果区显示得分
        for w in self.result_frame.winfo_children():
            w.destroy()

        # 评语
        ratio = score / max_score
        if ratio >= 0.85:
            comment = '优秀！文笔流畅，逻辑清晰'
        elif ratio >= 0.7:
            comment = '良好！内容充实，表达准确'
        elif ratio >= 0.6:
            comment = '及格！基本完成任务'
        else:
            comment = '仍需努力，注意语法和结构'

        result_frame = tk.Frame(self.result_frame, bg=COLOR_BG)
        result_frame.pack()

        tk.Label(result_frame,
                 text=f'作文得分: {score}/{max_score}',
                 font=('Microsoft YaHei', 14, 'bold'),
                 fg=COLOR_ACCENT, bg=COLOR_BG).pack()
        tk.Label(result_frame, text=comment,
                 font=FONT_NORMAL, fg=COLOR_PRIMARY, bg=COLOR_BG).pack()

        # 更新数据库中的分数记录
        db_module.update_answer_score(self.user['id'], q['id'], score, self.practice_id)

        # 更新知识点进度（作文算作正向练习）
        db_module.update_knowledge_progress(self.user['id'], q['id'], True)

        messagebox.showinfo('评分完成', f'作文得分: {score}/{max_score}\n{comment}')

    def _show_ai_scoring(self, q, user_answer, ai_score, max_score, feedback):
        """显示 AI 评分结果"""
        # 参考范文框
        ref_frame = tk.Frame(self.scrollable_frame, bg='#eaf2f8', bd=1,
                             relief='groove', padx=15, pady=10)
        ref_frame.pack(fill='x', padx=15, pady=5)
        label_text = {'writing': '【参考范文】', 'cs_comprehensive': '【参考答案】'}.get(q['type'], '【参考】')
        tk.Label(ref_frame, text=label_text, font=('Microsoft YaHei', 11, 'bold'),
                 fg=COLOR_ACCENT, bg='#eaf2f8').pack(anchor='w')
        tk.Label(ref_frame, text=q.get('answer', ''), font=FONT_NORMAL,
                 fg=COLOR_PRIMARY, bg='#eaf2f8',
                 wraplength=630, justify='left', anchor='w').pack(fill='x', pady=5)
        if q.get('explanation'):
            tk.Label(ref_frame, text=f'评分要点: {q["explanation"]}',
                     font=FONT_SMALL, fg='#7f8c8d', bg='#eaf2f8',
                     wraplength=630, justify='left').pack(anchor='w', pady=2)

        # 你的答案
        your_frame = tk.Frame(self.scrollable_frame, bg='#fef9e7', bd=1,
                              relief='groove', padx=15, pady=10)
        your_frame.pack(fill='x', padx=15, pady=5)
        tk.Label(your_frame, text='【你的答案】', font=('Microsoft YaHei', 11, 'bold'),
                 fg='#7d6608', bg='#fef9e7').pack(anchor='w')
        tk.Label(your_frame, text=user_answer, font=FONT_NORMAL,
                 fg=COLOR_PRIMARY, bg='#fef9e7',
                 wraplength=630, justify='left', anchor='w').pack(fill='x', pady=5)

        # AI 评分结果
        score_frame = tk.Frame(self.scrollable_frame, bg='#e8f8f5', bd=1,
                               relief='groove', padx=15, pady=12)
        score_frame.pack(fill='x', padx=15, pady=5)
        tk.Label(score_frame, text='🤖 AI 评分', font=('Microsoft YaHei', 12, 'bold'),
                 fg='#1abc9c', bg='#e8f8f5').pack(anchor='w')

        score_row = tk.Frame(score_frame, bg='#e8f8f5')
        score_row.pack(fill='x', pady=8)
        tk.Label(score_row, text=f'{ai_score:.1f} / {max_score} 分',
                 font=('Microsoft YaHei', 22, 'bold'), fg='#1abc9c', bg='#e8f8f5').pack()

        if feedback:
            tk.Label(score_frame, text=f'💬 {feedback}', font=FONT_NORMAL,
                     fg=COLOR_PRIMARY, bg='#e8f8f5',
                     wraplength=630, justify='left').pack(anchor='w', pady=5)

        # 更新进度显示
        self.progress_label.config(
            text=f'第 {self.current_index + 1}/{self.total_questions} 题  |  得分: {self.total_score}')

        # 启用下一题按钮
        self.next_btn.config(state='normal')

        # 滚动到底部
        self.scrollable_frame.update_idletasks()
        self.canvas.yview_moveto(1)

    def _next_question(self):
        """下一题（复合题：先走完子题再进下一大题）"""
        item = self.current_questions[self.current_index]
        if item['is_composite'] and item['child_idx'] < len(item['children']) - 1:
            # 复合题还有下一子题
            item['child_idx'] += 1
            self._show_current_question()
        else:
            # 进下一题
            self.current_index += 1
            if self.current_index < self.total_questions:
                # 重置复合题的子题索引
                next_item = self.current_questions[self.current_index]
                if next_item['is_composite']:
                    next_item['child_idx'] = 0
                self._show_current_question()
            else:
                self._show_result_summary()

    def _show_result_summary(self):
        """显示练习结果总结"""
        self._clear_content()
        for w in self.result_frame.winfo_children():
            w.destroy()
        self.submit_btn.config(state='disabled')
        self.next_btn.config(state='disabled')
        self.prev_btn.config(state='normal' if self.total_questions > 0 else 'disabled')

        # 完成练习记录（按独立小题数统计）
        indiv_total = self.total_indiv if hasattr(self, 'total_indiv') else self.total_questions
        if self.practice_id:
            db_module.finish_practice_record(
                self.practice_id, indiv_total,
                self.correct_count, self.total_score
            )

        accuracy = (self.correct_count / indiv_total * 100) if indiv_total > 0 else 0

        # 结果显示
        result_frame = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, padx=40, pady=40)
        result_frame.pack(fill='both', expand=True)

        tk.Label(result_frame, text='练习完成！', font=('Microsoft YaHei', 20, 'bold'),
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(pady=10)

        stats_frame = tk.Frame(result_frame, bg=COLOR_BG, bd=2, relief='groove', padx=30, pady=20)
        stats_frame.pack(pady=20)

        stats_data = [
            ('总题数', str(indiv_total)),
            ('正确数', str(self.correct_count)),
            ('正确率', f'{accuracy:.1f}%'),
            ('得分', str(self.total_score)),
        ]

        for label, value in stats_data:
            row = tk.Frame(stats_frame, bg=COLOR_BG)
            row.pack(fill='x', pady=5)
            tk.Label(row, text=label, font=FONT_NORMAL, bg=COLOR_BG,
                     width=10, anchor='w').pack(side='left')
            tk.Label(row, text=value, font=('Microsoft YaHei', 14, 'bold'),
                     fg=COLOR_ACCENT, bg=COLOR_BG, anchor='e').pack(side='right')

        # 鼓励语
        if accuracy >= 80:
            msg = '太棒了！继续保持！'
        elif accuracy >= 60:
            msg = '不错！继续努力！'
        else:
            msg = '加油！多练习会进步的！'
        tk.Label(result_frame, text=msg, font=('Microsoft YaHei', 12),
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(pady=10)

        self.progress_label.config(text='练习完成')
        self.progress_label.config(text=f'练习完成 | 正确率: {accuracy:.1f}% | 得分: {self.total_score}')


class WrongAnswerPanel:
    """错题本面板"""

    def __init__(self, parent, user, subject='英语'):
        self.parent = parent
        self.user = user
        self.subject = subject
        self._build_ui()

    def _build_ui(self):
        """构建错题本界面"""
        # 标题
        title_frame = tk.Frame(self.parent, bg=COLOR_BG, pady=10)
        title_frame.pack(fill='x')

        tk.Label(title_frame, text='错题本', font=FONT_TITLE,
                 fg=COLOR_PRIMARY, bg=COLOR_BG).pack(side='left', padx=10)

        tk.Button(title_frame, text='刷新', font=FONT_NORMAL,
                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=15, pady=4,
                  command=self._load_data).pack(side='right', padx=10)

        # 主内容区（滚动）
        content_frame = tk.Frame(self.parent, bg=COLOR_WHITE, bd=1, relief='groove')
        content_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        canvas = tk.Canvas(content_frame, bg=COLOR_WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient='vertical', command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg=COLOR_WHITE)

        self.scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.canvas = canvas

        # 加载数据
        self._load_data()

    def _load_data(self):
        """加载错题数据"""
        for w in self.scrollable_frame.winfo_children():
            w.destroy()

        wrong_answers = db_module.get_wrong_answers(self.user['id'])

        if not wrong_answers:
            tk.Label(self.scrollable_frame, text='暂无错题记录，继续刷题吧！',
                     font=FONT_NORMAL, fg='#7f8c8d', bg=COLOR_WHITE).pack(pady=50)
            return

        latest_diagnoses = {}
        for diagnosis in db_module.get_ai_diagnoses(self.user['id'], limit=100):
            latest_diagnoses.setdefault(diagnosis.get('question_id'), diagnosis)

        for item in wrong_answers:
            card = tk.Frame(self.scrollable_frame, bg=COLOR_BG, bd=1,
                            relief='groove', padx=15, pady=10)
            card.pack(fill='x', padx=10, pady=5)

            type_name = TYPE_NAMES.get(item.get('type'), item.get('type', ''))
            tk.Label(card, text=f'[{type_name}]  {item.get("content", "")[:100]}...',
                     font=FONT_NORMAL, fg=COLOR_PRIMARY, bg=COLOR_BG,
                     wraplength=600, justify='left', anchor='w').pack(anchor='w', fill='x')

            detail_frame = tk.Frame(card, bg=COLOR_BG)
            detail_frame.pack(fill='x', pady=3)

            tk.Label(detail_frame, text=f'你的答案: {item.get("user_answer", "")}',
                     font=FONT_SMALL, fg=COLOR_DANGER, bg=COLOR_BG).pack(anchor='w')
            tk.Label(detail_frame, text=f'正确答案: {item.get("answer", "")}',
                     font=FONT_SMALL, fg=COLOR_SUCCESS, bg=COLOR_BG).pack(anchor='w')
            if item.get('explanation'):
                tk.Label(detail_frame, text=f'解析: {item.get("explanation", "")}',
                         font=FONT_SMALL, fg='#7f8c8d', bg=COLOR_BG,
                         wraplength=600, justify='left').pack(anchor='w', pady=2)

            diagnosis = latest_diagnoses.get(item.get('question_id'))
            if diagnosis:
                ai_frame = tk.Frame(card, bg='#f5eef8', bd=1,
                                    relief='groove', padx=10, pady=6)
                ai_frame.pack(fill='x', pady=(5, 6))
                tk.Label(
                    ai_frame,
                    text=f'🤖 最近诊断 · {diagnosis.get("error_type", "其他")}',
                    font=('Microsoft YaHei', 9, 'bold'),
                    fg='#8e44ad', bg='#f5eef8'
                ).pack(anchor='w')
                tk.Label(
                    ai_frame, text=diagnosis.get('summary', ''),
                    font=FONT_SMALL, fg=COLOR_PRIMARY, bg='#f5eef8',
                    wraplength=580, justify='left'
                ).pack(anchor='w', pady=2)
                gaps = diagnosis.get('knowledge_gaps') or []
                if gaps:
                    tk.Label(
                        ai_frame, text=f'薄弱知识点：{"、".join(gaps)}',
                        font=FONT_SMALL, fg=COLOR_WARNING, bg='#f5eef8',
                        wraplength=580, justify='left'
                    ).pack(anchor='w')
                if diagnosis.get('next_action'):
                    tk.Label(
                        ai_frame, text=f'下一步：{diagnosis["next_action"]}',
                        font=FONT_SMALL, fg=COLOR_ACCENT, bg='#f5eef8',
                        wraplength=580, justify='left'
                    ).pack(anchor='w')

            # 操作按钮
            btn_frame = tk.Frame(card, bg=COLOR_BG)
            btn_frame.pack(fill='x')
            tk.Button(btn_frame, text='重新练习', font=FONT_SMALL,
                      bg=COLOR_WARNING, fg=COLOR_WHITE, bd=0, padx=10, pady=2,
                      command=lambda qid=item.get('question_id'): self._practice_question(qid)).pack(side='left', padx=2)
            tk.Button(btn_frame, text='🤖 AI 相似题', font=FONT_SMALL,
                      bg='#8e44ad', fg=COLOR_WHITE, bd=0, padx=10, pady=2,
                      command=lambda it=item: self._ai_generate(it)).pack(side='left', padx=2)

    def _practice_question(self, question_id):
        """练习单题（打开做题对话框）"""
        PracticeDialog(self.parent, self.user, question_id)

    def _ai_generate(self, item):
        """调用 AI 生成相似题并打开练习"""
        import tkinter.messagebox as mb
        # 准备请求数据
        options = item.get('options', '')
        if isinstance(options, dict):
            options = json.dumps(options, ensure_ascii=False)
        qdata = {
            'question_type': item.get('type', ''),
            'content': item.get('content', ''),
            'options': options,
            'answer': item.get('answer', ''),
            'explanation': item.get('explanation', ''),
            'subject': self.subject,
        }
        # 用顶层窗口显示加载状态
        load_win = tk.Toplevel(self.parent)
        load_win.title('AI 出题中')
        load_win.geometry('300x100')
        load_win.configure(bg=COLOR_WHITE)
        tk.Label(load_win, text='🤖 AI 正在生成相似题目...', font=FONT_NORMAL,
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(expand=True)
        load_win.update()

        try:
            result = db_module.ai_generate_similar(qdata)
            load_win.destroy()
            if result:
                AIPracticeDialog(self.parent, self.user, result, item)
            else:
                mb.showerror('生成失败', 'AI 出题失败，请检查 DeepSeek API Key 配置')
        except Exception as e:
            load_win.destroy()
            mb.showerror('错误', f'AI 出题出错: {str(e)}')


class NotesPanel:
    """笔记本入口面板"""

    def __init__(self, parent, user, subject=''):
        self.parent = parent
        self.user = user
        self.subject = subject
        self._build_ui()

    def _build_ui(self):
        """构建笔记本入口"""
        frame = tk.Frame(self.parent, bg=COLOR_BG)
        frame.pack(expand=True, fill='both')

        # 居中内容
        center = tk.Frame(frame, bg=COLOR_WHITE, bd=2, relief='groove', padx=40, pady=40)
        center.place(relx=0.5, rely=0.5, anchor='center')

        tk.Label(center, text='📓 我的笔记本', font=('Microsoft YaHei', 18, 'bold'),
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(pady=15)

        tk.Label(center, text='所有笔记按页排列，可翻页浏览、自由增删',
                 font=FONT_NORMAL, fg='#7f8c8d', bg=COLOR_WHITE).pack(pady=5)

        # 统计
        pages = db_module.get_notebook_pages(self.user['id'])
        tk.Label(center, text=f'共 {len(pages)} 页',
                 font=FONT_NORMAL, fg=COLOR_ACCENT, bg=COLOR_WHITE).pack(pady=5)

        tk.Button(center, text='📖 打开笔记本', font=('Microsoft YaHei', 12, 'bold'),
                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=25, pady=8,
                  command=self._open_notebook).pack(pady=15)

    def _open_notebook(self):
        NotebookWindow(self.parent, self.user, subject=self.subject)


class StatsPanel:
    """数据分析面板"""

    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self._build_ui()

    def _build_ui(self):
        """构建统计界面"""
        title_frame = tk.Frame(self.parent, bg=COLOR_BG, pady=10)
        title_frame.pack(fill='x')

        self.subject_label = tk.Label(title_frame, text='数据分析', font=FONT_TITLE,
                                      fg=COLOR_PRIMARY, bg=COLOR_BG)
        self.subject_label.pack(side='left', padx=10)

        tk.Button(title_frame, text='刷新数据', font=FONT_NORMAL,
                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=15, pady=4,
                  command=self._load_data).pack(side='right', padx=10)

        # 主内容区（滚动）
        content_frame = tk.Frame(self.parent, bg=COLOR_WHITE, bd=1, relief='groove')
        content_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        canvas = tk.Canvas(content_frame, bg=COLOR_WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient='vertical', command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg=COLOR_WHITE)

        self.scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.canvas = canvas

        self._load_data()

    def _load_data(self):
        """加载统计数据"""
        for w in self.scrollable_frame.winfo_children():
            w.destroy()

        stats = db_module.get_user_stats(self.user['id'])
        subject_name = stats.get('subject_name', '')
        self.subject_label.config(text=f'数据分析 - {subject_name}' if subject_name else '数据分析')

        total_practices = stats.get('total_practices', 0)

        # ====== 概览（有数据时才显示） ======
        if total_practices:
            overview = tk.Frame(self.scrollable_frame, bg=COLOR_BG, padx=20, pady=15)
            overview.pack(fill='x', padx=10, pady=5)

            tk.Label(overview, text='学习概览', font=('Microsoft YaHei', 13, 'bold'),
                     fg=COLOR_PRIMARY, bg=COLOR_BG).pack(anchor='w')

            card_frame = tk.Frame(overview, bg=COLOR_BG)
            card_frame.pack(fill='x', pady=10)

            cards = [
                ('练习次数', str(total_practices), COLOR_ACCENT),
                ('总题数', str(stats.get('total_questions', 0)), COLOR_PRIMARY),
                ('正确率', f'{stats.get("accuracy", 0):.1f}%', COLOR_SUCCESS),
                ('总分', str(stats.get('total_score', 0)), COLOR_WARNING),
            ]

            for label, value, color in cards:
                card = tk.Frame(card_frame, bg=COLOR_WHITE, bd=1, relief='groove',
                                padx=15, pady=10, width=140, height=80)
                card.pack(side='left', padx=5, pady=5)
                card.pack_propagate(False)

                tk.Label(card, text=label, font=FONT_SMALL, fg='#7f8c8d',
                         bg=COLOR_WHITE).pack()
                tk.Label(card, text=value, font=('Microsoft YaHei', 18, 'bold'),
                         fg=color, bg=COLOR_WHITE).pack(expand=True)

        # ====== 题型统计 ======
        type_stats = stats.get('by_type', [])
        if type_stats:
            section = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, padx=20, pady=15)
            section.pack(fill='x', padx=10, pady=5)

            tk.Label(section, text='各题型答题统计', font=('Microsoft YaHei', 13, 'bold'),
                     fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')

            # 表头
            header = tk.Frame(section, bg=COLOR_PRIMARY, padx=10, pady=5)
            header.pack(fill='x', pady=5)
            for i, text in enumerate(['题型', '答题数', '正确数', '正确率']):
                tk.Label(header, text=text, font=('Microsoft YaHei', 10, 'bold'),
                         fg=COLOR_WHITE, bg=COLOR_PRIMARY, width=15).pack(side='left')

            for ts in type_stats:
                total = ts.get('count', 0)
                correct = ts.get('correct_count', 0)
                rate = (correct / total * 100) if total > 0 else 0
                row = tk.Frame(section, bg=COLOR_WHITE, padx=10, pady=3)
                row.pack(fill='x')
                for i, text in enumerate([
                    ts.get('type_name') or TYPE_NAMES.get(ts.get('type', ''), ts.get('type', '')),
                    str(total), str(correct), f'{rate:.1f}%'
                ]):
                    tk.Label(row, text=text, font=FONT_SMALL,
                             fg=COLOR_PRIMARY, bg=COLOR_WHITE,
                             width=15).pack(side='left')

        # ====== 知识点掌握情况 ======
        kp_progress = stats.get('knowledge_progress', [])
        if kp_progress:
            section = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, padx=20, pady=15)
            section.pack(fill='x', padx=10, pady=5)

            tk.Label(section, text='知识点掌握情况', font=('Microsoft YaHei', 13, 'bold'),
                     fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')

            for kp in kp_progress:
                familiarity = kp.get('familiarity', 0)
                name = kp.get('name', '')
                attempts = kp.get('attempts', 0)
                correct = kp.get('correct', 0)

                row = tk.Frame(section, bg=COLOR_WHITE, pady=5)
                row.pack(fill='x', padx=5)

                tk.Label(row, text=name, font=FONT_NORMAL,
                         fg=COLOR_PRIMARY, bg=COLOR_WHITE,
                         width=15, anchor='w').pack(side='left')

                # 进度条
                bar_frame = tk.Frame(row, bg='#ecf0f1', width=200, height=20)
                bar_frame.pack(side='left', padx=10)
                bar_frame.pack_propagate(False)

                fill_color = COLOR_SUCCESS if familiarity >= 60 else (COLOR_WARNING if familiarity >= 30 else COLOR_DANGER)
                fill_width = max(2, int(familiarity * 2))
                fill = tk.Frame(bar_frame, bg=fill_color, width=fill_width, height=20)
                fill.pack(anchor='w')

                tk.Label(row, text=f'{familiarity:.0f}%', font=FONT_SMALL,
                         fg=COLOR_PRIMARY, bg=COLOR_WHITE,
                         width=8).pack(side='left', padx=5)

                tk.Label(row, text=f'(练习{attempts}次, 正确{correct}次)',
                         font=FONT_SMALL, fg='#7f8c8d',
                         bg=COLOR_WHITE).pack(side='left')

        # ====== 近期趋势 ======
        trend = stats.get('recent_trend', [])
        if trend:
            section = tk.Frame(self.scrollable_frame, bg=COLOR_WHITE, padx=20, pady=15)
            section.pack(fill='x', padx=10, pady=5)

            tk.Label(section, text='近期练习趋势（最近7次）', font=('Microsoft YaHei', 13, 'bold'),
                     fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')

            header = tk.Frame(section, bg=COLOR_PRIMARY, padx=10, pady=5)
            header.pack(fill='x', pady=5)
            for text in ['日期', '题数', '正确数', '正确率']:
                tk.Label(header, text=text, font=('Microsoft YaHei', 10, 'bold'),
                         fg=COLOR_WHITE, bg=COLOR_PRIMARY, width=15).pack(side='left')

            for t in reversed(trend):
                row = tk.Frame(section, bg=COLOR_WHITE, padx=10, pady=3)
                row.pack(fill='x')
                date = t.get('practice_date', '')
                if hasattr(date, 'strftime'):
                    date = date.strftime('%m-%d')
                for text in [str(date), str(t.get('total_questions', 0)),
                             str(t.get('correct_count', 0)),
                             f'{t.get("accuracy", 0):.1f}%']:
                    tk.Label(row, text=text, font=FONT_SMALL,
                             fg=COLOR_PRIMARY, bg=COLOR_WHITE,
                             width=15).pack(side='left')

        if not total_practices:
            tk.Label(self.scrollable_frame, text='还没有练习记录，开始刷题吧！',
                     font=FONT_NORMAL, fg='#7f8c8d', bg=COLOR_WHITE).pack(pady=30)


class PracticeDialog(tk.Toplevel):
    """单题练习对话框"""

    def __init__(self, parent, user, question_id):
        super().__init__(parent)
        self.user = user
        self.question_id = question_id
        self.title('重新练习')
        self.geometry('700x600')
        self.configure(bg=COLOR_WHITE)

        # 居中
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 700) // 2
        y = (self.winfo_screenheight() - 600) // 2
        self.geometry(f'+{x}+{y}')

        self._load_question()
        self.grab_set()

    def _load_question(self):
        """加载题目"""
        q = db_module.get_question_by_id(self.question_id)
        if not q:
            messagebox.showerror('错误', '题目不存在')
            self.destroy()
            return

        # 题目内容
        content_text = tk.Text(self, wrap='word', font=FONT_NORMAL,
                               bg=COLOR_WHITE, fg=COLOR_PRIMARY,
                               padx=15, pady=10, height=8)
        content_text.pack(fill='x', padx=10, pady=10)
        content_text.insert('1.0', q['content'])
        content_text.config(state='disabled')

        # 答案输入
        answer_frame = tk.Frame(self, bg=COLOR_WHITE, padx=15)
        answer_frame.pack(fill='x')

        tk.Label(answer_frame, text='你的答案:', font=('Microsoft YaHei', 11, 'bold'),
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')

        if q['type'] in ('careful_reading_question', 'banked_cloze_blank', 'long_reading_question', 'cs_choice'):
            self.answer_var = tk.StringVar()
            try:
                options = PracticePanel._parse_options(q.get('options'))
                if options:
                    for key in sorted(options.keys()):
                        tk.Radiobutton(answer_frame, text=f"{key}. {options[key]}",
                                       variable=self.answer_var, value=key,
                                       font=FONT_NORMAL, bg=COLOR_WHITE).pack(anchor='w')
                else:
                    tk.Label(answer_frame, text='（该题目暂无选项）', font=FONT_SMALL,
                             fg='#95a5a6', bg=COLOR_WHITE).pack(anchor='w')
            except Exception as e:
                tk.Label(answer_frame, text=f'⚠ 选项加载失败', font=FONT_SMALL,
                         fg=COLOR_DANGER, bg=COLOR_WHITE).pack(anchor='w')
                print(f'PracticeDialog 选项渲染异常: {e}')
        elif q['type'] in ('writing', 'translation', 'cs_comprehensive'):
            self.answer_text = tk.Text(answer_frame, height=6 if q['type'] != 'cs_comprehensive' else 10,
                                       font=FONT_NORMAL, bd=2, relief='groove', wrap='word')
            self.answer_text.pack(fill='x', pady=5)

        # 提交
        tk.Button(self, text='提交', font=FONT_NORMAL,
                  bg=COLOR_SUCCESS, fg=COLOR_WHITE, bd=0, padx=30, pady=6,
                  command=lambda: self._submit(q)).pack(pady=15)

    def _submit(self, q):
        """提交答案"""
        if q['type'] in ('careful_reading_question', 'banked_cloze_blank', 'long_reading_question'):
            user_answer = self.answer_var.get().strip()
        else:
            user_answer = self.answer_text.get('1.0', 'end-1c').strip()

        if not user_answer:
            messagebox.showwarning('提示', '请输入答案')
            return

        # ----- 主观题：分数制评价 -----
        if q['type'] in ('writing', 'translation', 'cs_comprehensive'):
            self._submit_essay_score(q, user_answer)
            return

        # ----- 客观题：对错评判 -----
        if q['type'] in ('careful_reading_question', 'banked_cloze_blank', 'long_reading_question', 'cs_choice'):
            is_correct = user_answer.upper() == q['answer'].strip().upper()
        else:
            is_correct = None

        # 保存记录
        score = q.get('score', 0) if is_correct else 0
        db_module.save_answer_record(self.user['id'], q['id'], user_answer,
                                     bool(is_correct) if is_correct is not None else False,
                                     score)
        db_module.update_knowledge_progress(self.user['id'], q['id'],
                                            bool(is_correct) if is_correct is not None else False)

        # 显示结果
        result = tk.Toplevel(self)
        result.title('批改结果')
        result.geometry('500x350')
        result.configure(bg=COLOR_WHITE)

        if is_correct:
            tk.Label(result, text='✓ 回答正确！', font=('Microsoft YaHei', 16, 'bold'),
                     fg=COLOR_SUCCESS, bg=COLOR_WHITE).pack(pady=15)
        else:
            tk.Label(result, text='✗ 回答错误', font=('Microsoft YaHei', 16, 'bold'),
                     fg=COLOR_DANGER, bg=COLOR_WHITE).pack(pady=15)
            tk.Label(result, text=f'你的答案: {user_answer}', font=FONT_NORMAL,
                     fg=COLOR_DANGER, bg=COLOR_WHITE).pack()
            tk.Label(result, text=f'正确答案: {q["answer"]}', font=FONT_NORMAL,
                     fg=COLOR_SUCCESS, bg=COLOR_WHITE).pack()

        if q.get('explanation'):
            tk.Label(result, text=f'\n解析:\n{q["explanation"]}', font=FONT_NORMAL,
                     fg=COLOR_PRIMARY, bg=COLOR_WHITE,
                     wraplength=450, justify='left').pack(pady=10, padx=20)

        tk.Button(result, text='关闭', font=FONT_NORMAL,
                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=20, pady=5,
                  command=lambda: (result.destroy(), self.destroy())).pack(pady=15)

    def _submit_essay_score(self, q, user_answer):
        """作文自评分数提交"""
        max_score = q.get('score', 15)

        # 先暂存答案（分数0）
        db_module.save_answer_record(self.user['id'], q['id'], user_answer,
                                     True, 0)

        # 创建评分弹窗
        score_win = tk.Toplevel(self)
        score_win.title('作文自评')
        score_win.geometry('600x550')
        score_win.configure(bg=COLOR_WHITE)
        score_win.resizable(False, False)

        # 居中
        score_win.update_idletasks()
        x = (score_win.winfo_screenwidth() - 600) // 2
        y = (score_win.winfo_screenheight() - 550) // 2
        score_win.geometry(f'+{x}+{y}')

        # 你的作文
        tk.Label(score_win, text='【你的作文】', font=('Microsoft YaHei', 11, 'bold'),
                 fg='#7d6608', bg='#fef9e7', anchor='w').pack(fill='x', padx=15, pady=(10, 0))
        your_text = tk.Text(score_win, height=6, font=FONT_SMALL, wrap='word',
                            bg='#fef9e7', fg=COLOR_PRIMARY, bd=0)
        your_text.pack(fill='x', padx=15, pady=5)
        your_text.insert('1.0', user_answer)
        your_text.config(state='disabled')

        # 参考范文
        tk.Label(score_win, text='【参考范文】', font=('Microsoft YaHei', 11, 'bold'),
                 fg=COLOR_ACCENT, bg='#eaf2f8', anchor='w').pack(fill='x', padx=15, pady=(10, 0))
        ref_text = tk.Text(score_win, height=6, font=FONT_SMALL, wrap='word',
                           bg='#eaf2f8', fg=COLOR_PRIMARY, bd=0)
        ref_text.pack(fill='x', padx=15, pady=5)
        ref_text.insert('1.0', q.get('answer', ''))
        ref_text.config(state='disabled')

        # 评分要点
        if q.get('explanation'):
            tk.Label(score_win, text=f'评分要点: {q["explanation"]}',
                     font=FONT_SMALL, fg='#7f8c8d', bg=COLOR_WHITE,
                     wraplength=550, justify='left').pack(padx=15, pady=5, anchor='w')

        # 分数输入
        score_frame = tk.Frame(score_win, bg=COLOR_WHITE, pady=10)
        score_frame.pack(fill='x', padx=15)

        tk.Label(score_frame, text='自我评分:', font=('Microsoft YaHei', 12, 'bold'),
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack()

        score_var = tk.IntVar(value=max_score)

        slide_frame = tk.Frame(score_frame, bg=COLOR_WHITE)
        slide_frame.pack(pady=10)

        tk.Label(slide_frame, text='0', font=FONT_NORMAL,
                 fg='#7f8c8d', bg=COLOR_WHITE).pack(side='left', padx=5)

        slider = tk.Scale(slide_frame, from_=0, to=max_score,
                          orient='horizontal', variable=score_var,
                          length=350, tickinterval=max_score//2,
                          bg=COLOR_WHITE, bd=0, highlightthickness=0)
        slider.pack(side='left')

        tk.Label(slide_frame, text=str(max_score), font=FONT_NORMAL,
                 fg='#7f8c8d', bg=COLOR_WHITE).pack(side='left', padx=5)

        score_display = tk.Label(score_frame, textvariable=score_var,
                                 font=('Microsoft YaHei', 20, 'bold'),
                                 fg=COLOR_ACCENT, bg=COLOR_WHITE)
        score_display.pack()
        tk.Label(score_frame, text=f'满分 {max_score} 分', font=FONT_NORMAL,
                 fg='#7f8c8d', bg=COLOR_WHITE).pack()

        def confirm_score():
            s = score_var.get()
            if s < 0 or s > max_score:
                messagebox.showwarning('提示', f'分数应在 0-{max_score} 之间')
                return

            # 更新答题记录中的分数
            db_module.update_answer_score(self.user['id'], q['id'], s)

            # 更新知识点进度（作文算正向练习）
            db_module.update_knowledge_progress(self.user['id'], q['id'], True)

            # 评语
            ratio = s / max_score
            if ratio >= 0.85:
                comment = '优秀！文笔流畅，逻辑清晰'
            elif ratio >= 0.7:
                comment = '良好！内容充实，表达准确'
            elif ratio >= 0.6:
                comment = '及格！基本完成任务'
            else:
                comment = '仍需努力，注意语法和结构'

            messagebox.showinfo('评分完成', f'作文得分: {s}/{max_score}\n{comment}')
            score_win.destroy()
            self.destroy()

        tk.Button(score_win, text='确认评分', font=('Microsoft YaHei', 12, 'bold'),
                  bg=COLOR_SUCCESS, fg=COLOR_WHITE, bd=0, padx=30, pady=8,
                  command=confirm_score).pack(pady=10)

        score_win.grab_set()


class AIPracticeDialog(tk.Toplevel):
    """AI 生成题练习对话框"""

    def __init__(self, parent, user, ai_question, original_item=None):
        super().__init__(parent)
        self.user = user
        self.q = ai_question  # {content, options, answer, explanation}
        self.original_item = original_item
        self.title('🤖 AI 相似题练习')
        self.geometry('700x600')
        self.configure(bg=COLOR_WHITE)
        self.answer_var = tk.StringVar()

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 700) // 2
        y = (self.winfo_screenheight() - 600) // 2
        self.geometry(f'+{x}+{y}')

        self._build_ui()
        self.grab_set()

    def _build_ui(self):
        """构建界面"""
        # 标题
        header = tk.Frame(self, bg='#8e44ad', pady=8, padx=15)
        header.pack(fill='x')
        tk.Label(header, text='🤖 AI 生成的相似题目', font=('Microsoft YaHei', 12, 'bold'),
                 fg=COLOR_WHITE, bg='#8e44ad').pack(anchor='w')

        # 题目内容
        content_text = tk.Text(self, wrap='word', font=FONT_NORMAL,
                               bg='#f5eef8', fg=COLOR_PRIMARY,
                               padx=15, pady=10, height=6, relief='groove', bd=1)
        content_text.pack(fill='x', padx=15, pady=10)
        content_text.insert('1.0', self.q.get('content', '无题目内容'))
        content_text.config(state='disabled')

        # 答案区域
        answer_frame = tk.Frame(self, bg=COLOR_WHITE, padx=15)
        answer_frame.pack(fill='x')

        tk.Label(answer_frame, text='你的答案:', font=('Microsoft YaHei', 11, 'bold'),
                 fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor='w')

        options_raw = self.q.get('options', '')
        if options_raw:
            try:
                options = PracticePanel._parse_options(options_raw)
                if options:
                    for key in sorted(options.keys()):
                        tk.Radiobutton(answer_frame, text=f"{key}. {options[key]}",
                                       variable=self.answer_var, value=key,
                                       font=FONT_NORMAL, bg=COLOR_WHITE, anchor='w',
                                       indicatoron=0, width=60, height=2,
                                       selectcolor=COLOR_ACCENT).pack(anchor='w', pady=2)
                else:
                    self._add_text_input(answer_frame)
            except Exception:
                self._add_text_input(answer_frame)
        else:
            self._add_text_input(answer_frame)

        # 提交
        tk.Button(self, text='提交答案', font=FONT_NORMAL,
                  bg=COLOR_SUCCESS, fg=COLOR_WHITE, bd=0, padx=30, pady=6,
                  command=self._submit).pack(pady=10)

    def _add_text_input(self, parent):
        """添加文本输入框"""
        self.answer_text = tk.Text(parent, height=6, font=FONT_NORMAL,
                                    bd=2, relief='groove', wrap='word')
        self.answer_text.pack(fill='x', pady=5)

    def _get_answer(self):
        """获取用户答案"""
        if hasattr(self, 'answer_text'):
            return self.answer_text.get('1.0', 'end-1c').strip()
        return self.answer_var.get().strip()

    def _submit(self):
        """提交批改"""
        user_answer = self._get_answer()
        if not user_answer:
            messagebox.showwarning('提示', '请输入答案')
            return

        correct_answer = self.q.get('answer', '').strip()
        is_objective = bool(self.q.get('options'))

        # 批改
        result = tk.Toplevel(self)
        result.title('批改结果')
        result.geometry('550x400')
        result.configure(bg=COLOR_WHITE)
        result.update_idletasks()
        rx = (result.winfo_screenwidth() - 550) // 2
        ry = (result.winfo_screenheight() - 400) // 2
        result.geometry(f'+{rx}+{ry}')

        if is_objective:
            is_correct = user_answer.upper() == correct_answer.upper()
            if is_correct:
                tk.Label(result, text='✓ 回答正确！', font=('Microsoft YaHei', 16, 'bold'),
                         fg=COLOR_SUCCESS, bg=COLOR_WHITE).pack(pady=15)
            else:
                tk.Label(result, text='✗ 回答错误', font=('Microsoft YaHei', 16, 'bold'),
                         fg=COLOR_DANGER, bg=COLOR_WHITE).pack(pady=15)
                tk.Label(result, text=f'你的答案: {user_answer}', font=FONT_NORMAL,
                         fg=COLOR_DANGER, bg=COLOR_WHITE).pack()
                tk.Label(result, text=f'正确答案: {correct_answer}', font=FONT_NORMAL,
                         fg=COLOR_SUCCESS, bg=COLOR_WHITE).pack()
        else:
            tk.Label(result, text='参考答案:', font=('Microsoft YaHei', 12, 'bold'),
                     fg=COLOR_ACCENT, bg=COLOR_WHITE).pack(anchor='w', padx=20, pady=(15, 5))
            ref_text = tk.Text(result, wrap='word', font=FONT_NORMAL,
                               fg=COLOR_PRIMARY, bg='#eaf2f8',
                               padx=10, pady=10, height=8, relief='groove', bd=1)
            ref_text.pack(fill='x', padx=20, pady=5)
            ref_text.insert('1.0', correct_answer)
            ref_text.config(state='disabled')

        # 解析
        explanation = self.q.get('explanation', '')
        if explanation:
            tk.Label(result, text=f'解析: {explanation}', font=FONT_NORMAL,
                     fg=COLOR_PRIMARY, bg=COLOR_WHITE,
                     wraplength=500, justify='left').pack(pady=10, padx=20)

        tk.Button(result, text='关闭', font=FONT_NORMAL,
                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=20, pady=5,
                  command=lambda: (result.destroy(), self.destroy())).pack(pady=15)


class ScreenshotSelector(tk.Toplevel):
    """全屏截图区域选择器——截取屏幕画面→拖拽选区"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_win = parent
        self.start_x = self.start_y = 0
        self.rect_id = None
        self.sel_info_id = None
        self.selection = None    # (x1, y1, x2, y2) 物理像素坐标

        # 1. 截全屏，计算 DPI 缩放比
        raw_img = ImageGrab.grab()
        self.sw_phys, self.sh_phys = raw_img.size
        self.sw = self.winfo_screenwidth()   # tkinter 逻辑宽
        self.sh = self.winfo_screenheight()  # tkinter 逻辑高
        # 缩放比 = PIL 物理尺寸 / tkinter 逻辑尺寸
        self.dpi_scale_x = self.sw_phys / self.sw if self.sw > 0 else 1.0
        self.dpi_scale_y = self.sh_phys / self.sh if self.sh > 0 else 1.0
        self.dpi_scale = max(self.dpi_scale_x, self.dpi_scale_y)
        # 缩放到逻辑尺寸用于显示（避免窗口超出屏幕）
        if self.dpi_scale != 1.0:
            self.full_img = raw_img.resize((self.sw, self.sh), Image.LANCZOS)
        else:
            self.full_img = raw_img

        # 3. 全屏无边框窗口
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.geometry(f'{self.sw}x{self.sh}+0+0')

        # 深色半透明遮罩层
        self.image_tk = ImageTk.PhotoImage(self.full_img)
        self.cv = tk.Canvas(self, cursor='cross', highlightthickness=0,
                            width=self.sw, height=self.sh)
        self.cv.pack()
        self.cv.create_image(0, 0, image=self.image_tk, anchor='nw', tags='bg')

        # 半透明黑色覆盖层
        self.cv.create_rectangle(0, 0, self.sw, self.sh,
                                 fill='black', stipple='gray25', tags='overlay')

        # 提示
        dpi_info = f'DPI缩放: {self.dpi_scale:.2f}x' if self.dpi_scale != 1.0 else ''
        self.cv.create_text(
            self.sw // 2, self.sh - 30,
            text=f'按住左键拖拽选择区域 ｜ Esc 取消  {dpi_info}',
            fill='white', font=('Microsoft YaHei', 14, 'bold'),
            tags='hint'
        )

        # 绑定鼠标
        self.cv.bind('<Button-1>', self._on_press)
        self.cv.bind('<B1-Motion>', self._on_drag)
        self.cv.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Escape>', lambda e: self._cancel())
        self.focus_set()
        self.grab_set()

    def _logical_to_physical(self, x, y):
        """逻辑像素 → 物理像素（xy 独立缩放）"""
        if self.dpi_scale != 1.0:
            return int(x * self.dpi_scale_x), int(y * self.dpi_scale_y)
        return x, y

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.cv.delete('overlay')
        if self.rect_id:
            self.cv.delete(self.rect_id)
        if self.sel_info_id:
            self.cv.delete(self.sel_info_id)
        self.rect_id = self.cv.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline='#3498db', width=3, fill='', tags='sel'
        )

    def _on_drag(self, event):
        if self.rect_id:
            self.cv.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)
        w = abs(event.x - self.start_x)
        h = abs(event.y - self.start_y)
        self.cv.delete('info')
        self.sel_info_id = self.cv.create_text(
            event.x + 80, event.y - 15,
            text=f'{w}×{h}', fill='#f1c40f',
            font=('Microsoft YaHei', 12, 'bold'), anchor='w', tags='info'
        )

    def _on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        if x2 - x1 < 30 or y2 - y1 < 30:
            self._cancel()
            return
        # 转换为物理像素（高 DPI 屏幕兼容）
        x1, y1 = self._logical_to_physical(x1, y1)
        x2, y2 = self._logical_to_physical(x2, y2)
        self.selection = (x1, y1, x2, y2)
        self.destroy()

    def _cancel(self):
        self.selection = None
        self.destroy()


class DrawingCanvas(tk.Toplevel):
    """画笔绘图窗口——可拖拽缩放，对截取区域进行标注"""

    NOTES_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'notes_images')

    def __init__(self, parent, user, question, captured_image, save_to_notebook=False, page_id=None):
        """
        save_to_notebook=True  → 存入共享笔记本（question 可为 None）
        save_to_notebook=False → 存入当前题目的笔记
        page_id               → 不为 None 时覆盖更新已有笔记页
        """
        super().__init__(parent)
        self.user = user
        self.question = question
        self.save_to_notebook = save_to_notebook
        self.page_id = page_id

        self.title('画笔标注 - 拖拽右下角缩放')
        self.configure(bg='#2c3e50')

        # 原始截图（全分辨率，用于保存）
        self.orig_img = captured_image.copy()
        self.orig_w, self.orig_h = self.orig_img.size

        os.makedirs(self.NOTES_DIR, exist_ok=True)

        # 绘图状态
        self.strokes = []          # 每笔: {points: [(ix,iy),...], color, width, eraser}
        self.redo_stack = []       # 已撤销的笔画（用于重做）
        self.current_points = []   # 当前笔的坐标（缩放后画布坐标）
        self.drawing = False
        self.brush_color = '#e74c3c'
        self.eraser_mode = False

        # 显示缩放比
        self.display_scale = 1.0

        self._build_ui()

        # 初始大小（约屏幕 2/3）
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        iw, ih = self.orig_w, self.orig_h
        # 初始窗口尺寸：宽度取屏幕 2/3，高度自适应，但最小 400x300
        init_w = min(int(sw * 0.7), iw + 40, 1100)
        init_h = min(int(init_w * ih / iw + 80), int(sh * 0.75), ih + 80)
        init_w = max(init_w, 400)
        init_h = max(init_h, 300)
        self.geometry(f'{init_w}x{init_h}+{(sw-init_w)//2}+{max(30, (sh-init_h)//4)}')
        self.minsize(350, 250)
        self.grab_set()

    def _build_ui(self):
        """构建绘图界面"""
        # 工具栏
        toolbar = tk.Frame(self, bg='#2c3e50', pady=4, padx=5)
        toolbar.pack(fill='x')

        # 颜色按钮
        colors = [
            ('#e74c3c', '红'), ('#3498db', '蓝'), ('#2ecc71', '绿'),
            ('#f39c12', '橙'), ('#9b59b6', '紫'), ('#1abc9c', '青'),
            ('#2c3e50', '黑'), ('#95a5a6', '灰'),
        ]
        for color, name in colors:
            btn = tk.Button(toolbar, bg=color, width=2, bd=1, relief='raised',
                            command=lambda c=color: self._set_color(c))
            btn.pack(side='left', padx=2)
            btn.bind('<Enter>', lambda e, n=name: self._show_tip(e, n))
            btn.bind('<Leave>', lambda e: self._hide_tip())

        tk.Label(toolbar, text='  ', bg='#2c3e50').pack(side='left')
        tk.Frame(toolbar, width=1, bg='#7f8c8d').pack(side='left', fill='y', padx=5)

        # 粗细
        tk.Label(toolbar, text='粗细:', font=('Microsoft YaHei', 9),
                 fg=COLOR_WHITE, bg='#2c3e50').pack(side='left')
        self.size_var = tk.IntVar(value=3)
        tk.Scale(toolbar, from_=1, to=12, orient='horizontal',
                 variable=self.size_var, bg='#2c3e50', fg=COLOR_WHITE,
                 bd=0, highlightthickness=0, length=70,
                 troughcolor='#34495e', showvalue=False).pack(side='left')

        tk.Frame(toolbar, width=1, bg='#7f8c8d').pack(side='left', fill='y', padx=5)

        # 橡皮擦
        self.eraser_btn = tk.Button(toolbar, text='🧹 橡皮擦', font=FONT_SMALL,
                                    bg='#7f8c8d', fg=COLOR_WHITE, bd=1,
                                    command=self._toggle_eraser)
        self.eraser_btn.pack(side='left', padx=3)

        # 撤销
        tk.Button(toolbar, text='↩ 撤销', font=FONT_SMALL,
                  bg='#e67e22', fg=COLOR_WHITE, bd=1, padx=6,
                  command=self._undo).pack(side='left', padx=3)
        # 重做
        self.redo_btn = tk.Button(toolbar, text='↪ 重做', font=FONT_SMALL,
                                  bg='#d35400', fg=COLOR_WHITE, bd=1, padx=6,
                                  state='disabled', command=self._redo)
        self.redo_btn.pack(side='left', padx=3)

        # 清空
        tk.Button(toolbar, text='🗑 清空', font=FONT_SMALL,
                  bg=COLOR_DANGER, fg=COLOR_WHITE, bd=1, padx=6,
                  command=self._clear_all).pack(side='left', padx=3)

        # 提示
        self.tip_label = tk.Label(toolbar, text='', font=('Microsoft YaHei', 9),
                                  fg='#bdc3c7', bg='#2c3e50', width=14, anchor='w')
        self.tip_label.pack(side='left', padx=5)

        # 保存+关闭
        tk.Button(toolbar, text='💾 保存', font=('Microsoft YaHei', 10, 'bold'),
                  bg=COLOR_SUCCESS, fg=COLOR_WHITE, bd=0, padx=14, pady=3,
                  command=self._save).pack(side='right', padx=5)
        tk.Button(toolbar, text='✕ 关闭', font=('Microsoft YaHei', 9),
                  bg=COLOR_DANGER, fg=COLOR_WHITE, bd=0, padx=8, pady=3,
                  command=self._close).pack(side='right', padx=3)

        # 画布区（填充窗口，随窗口缩放）
        self.cv_frame = tk.Frame(self, bg=COLOR_WHITE)
        self.cv_frame.pack(fill='both', expand=True, padx=4, pady=4)

        self.cv = tk.Canvas(self.cv_frame, bg=COLOR_WHITE, bd=1,
                            relief='sunken', cursor='pencil', highlightthickness=0)
        self.cv.pack(fill='both', expand=True)

        # 初始显示
        self._update_display()

        # 窗口缩放事件
        self.cv.bind('<Configure>', self._on_canvas_resize)

        # 鼠标绘图事件
        self.cv.bind('<Button-1>', self._start_stroke)
        self.cv.bind('<B1-Motion>', self._add_point)
        self.cv.bind('<ButtonRelease-1>', self._finish_stroke)

    def _update_display(self):
        """根据当前缩放比重新渲染背景图"""
        new_w = max(10, int(self.orig_w * self.display_scale))
        new_h = max(10, int(self.orig_h * self.display_scale))
        resized = self.orig_img.resize((new_w, new_h), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        self.cv.delete('bg')
        self.cv.create_image(0, 0, image=self.tk_image, anchor='nw', tags='bg')
        self.cv.lower('bg')
        self._redraw_all()

    def _on_canvas_resize(self, event):
        """画布尺寸变化时重新计算缩放"""
        if event.width < 50 or event.height < 50:
            return
        scale_x = event.width / self.orig_w
        scale_y = event.height / self.orig_h
        new_scale = min(scale_x, scale_y)
        if abs(new_scale - self.display_scale) > 0.005:
            self.display_scale = new_scale
            self._update_display()

    # ---- 坐标变换 ----
    def _canvas_to_img(self, cx, cy):
        """画布坐标 → 原始图片坐标"""
        return cx / self.display_scale, cy / self.display_scale

    def _img_to_canvas(self, ix, iy):
        """原始图片坐标 → 画布坐标"""
        return ix * self.display_scale, iy * self.display_scale

    def _set_color(self, color):
        """设置画笔颜色"""
        self.brush_color = color
        self.eraser_mode = False
        self.eraser_btn.config(bg='#7f8c8d', relief='raised')
        self._show_tip(None, f'颜色已选')

    def _toggle_eraser(self):
        """切换橡皮擦模式"""
        self.eraser_mode = not self.eraser_mode
        if self.eraser_mode:
            self.eraser_btn.config(bg='#c0392b', relief='sunken')
            self._show_tip(None, '橡皮擦模式')
        else:
            self.eraser_btn.config(bg='#7f8c8d', relief='raised')
            self._show_tip(None, '画笔模式')

    def _show_tip(self, event, text):
        self.tip_label.config(text=text)

    def _hide_tip(self):
        self.tip_label.config(text='')

    def _start_stroke(self, event):
        """开始一笔（存储图像坐标，绘制画布坐标）"""
        self.drawing = True
        ix, iy = self._canvas_to_img(event.x, event.y)
        self.current_points_img = [(ix, iy)]
        if self.eraser_mode:
            # 橡皮擦模式：显示擦除指示器（空心圆）
            w = self._eraser_display_width()
            self.cv.create_oval(event.x - w/2, event.y - w/2,
                                event.x + w/2, event.y + w/2,
                                outline='#e74c3c', width=2, dash=(4,2), tags='eraser_indicator')
        else:
            cx, cy = event.x, event.y
            w = self.size_var.get()
            self.cv.create_oval(cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2,
                                fill=self.brush_color, outline=self.brush_color, tags='stroke')

    def _add_point(self, event):
        """继续画线"""
        if not self.drawing:
            return
        ix, iy = self._canvas_to_img(event.x, event.y)
        last_ix, last_iy = self.current_points_img[-1]
        self.current_points_img.append((ix, iy))
        if self.eraser_mode:
            # 橡皮擦：显示擦除路径指示器
            w = self._eraser_display_width()
            self.cv.create_line(event.x - 20, event.y - 20,
                                event.x + 20, event.y + 20,
                                fill='#e74c3c', width=2, dash=(4,2), tags='eraser_indicator')
            self.cv.create_line(event.x + 20, event.y - 20,
                                event.x - 20, event.y + 20,
                                fill='#e74c3c', width=2, dash=(4,2), tags='eraser_indicator')
        else:
            cx1, cy1 = self._img_to_canvas(last_ix, last_iy)
            cx2, cy2 = self._img_to_canvas(ix, iy)
            w = self.size_var.get()
            self.cv.create_line(cx1, cy1, cx2, cy2, fill=self.brush_color, width=w,
                               capstyle='round', smooth=True, tags='stroke')

    def _eraser_display_width(self):
        """橡皮擦指示器显示尺寸"""
        return self.size_var.get() * 6

    def _finish_stroke(self, event):
        """结束一笔"""
        if not self.drawing:
            return
        self.drawing = False
        # 清除橡皮擦指示器
        self.cv.delete('eraser_indicator')
        if self.eraser_mode:
            # ==== 真橡皮擦：移除相交的笔迹 ====
            erased = self._get_eraser_intersections(self.current_points_img,
                                                    self.size_var.get() * 3)
            if erased:
                # 把被擦掉的笔画存入重做栈（可撤销恢复）
                for idx in sorted(erased, reverse=True):
                    self.redo_stack.append(self.strokes.pop(idx))
                self._redraw_all()
                self._update_redo_btn()
                self._show_tip(None, f'已擦除 {len(erased)} 笔')
            else:
                self._show_tip(None, '没有擦除任何笔迹')
            self.current_points_img = []
            return
        # ==== 普通画笔 ====
        w = self.size_var.get()
        self.strokes.append({
            'points': list(self.current_points_img),
            'color': self.brush_color,
            'width': w,
        })
        self.current_points_img = []
        # 新笔画清空重做栈
        self.redo_stack.clear()
        self._update_redo_btn()

    def _get_eraser_intersections(self, eraser_points, eraser_width):
        """检测橡皮擦路径与哪些笔迹相交，返回要删除的 stroke 索引列表"""
        if not eraser_points or not self.strokes:
            return []
        radius = max(eraser_width / 2, 5)
        radius2 = radius * radius
        to_remove = set()
        for i, stroke in enumerate(self.strokes):
            # 对每个已有笔画，检查其坐标点是否在橡皮擦半径内
            for sp in stroke['points']:
                for ep in eraser_points:
                    dx = sp[0] - ep[0]
                    dy = sp[1] - ep[1]
                    if dx * dx + dy * dy <= radius2:
                        to_remove.add(i)
                        break
                if i in to_remove:
                    break
        return sorted(to_remove)

    def _undo(self):
        """撤销上一笔"""
        if not self.strokes:
            self._show_tip(None, '没有可撤销的笔画')
            return
        self.redo_stack.append(self.strokes.pop())
        self._redraw_all()
        self._update_redo_btn()
        self._show_tip(None, f'已撤销（剩余 {len(self.strokes)} 笔）')

    def _redo(self):
        """重做上一笔撤销"""
        if not self.redo_stack:
            self._show_tip(None, '没有可恢复的笔画')
            return
        self.strokes.append(self.redo_stack.pop())
        self._redraw_all()
        self._update_redo_btn()
        self._show_tip(None, f'已重做（可恢复 {len(self.redo_stack)} 笔）')

    def _update_redo_btn(self):
        """更新重做按钮的状态"""
        if hasattr(self, 'redo_btn'):
            self.redo_btn.config(state='normal' if self.redo_stack else 'disabled')

    def _clear_all(self):
        """清空所有笔画"""
        if not self.strokes:
            return
        if messagebox.askyesno('确认清空', '确定要清空所有画笔标注吗？'):
            self.strokes.clear()
            self.redo_stack.clear()
            self._update_redo_btn()
            self._redraw_all()
            self._show_tip(None, '已清空')

    def _redraw_all(self):
        """重绘所有笔画（图像坐标→画布坐标）"""
        self.cv.delete('stroke')
        s = self.display_scale
        for stroke in self.strokes:
            pts = stroke['points']
            if len(pts) < 2:
                continue
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                self.cv.create_line(x1 * s, y1 * s, x2 * s, y2 * s,
                                   fill=stroke['color'],
                                   width=stroke['width'],
                                   capstyle='round', smooth=True,
                                   tags='stroke')

    def _save(self):
        """保存标注后的图片到本地，并记录到数据库"""
        if not self.strokes:
            if not messagebox.askyesno('确认', '没有画笔标注，是否保存空白截图？'):
                return

        # 合成最终图片：在原始截图（全分辨率）上绘制笔画
        img = self.orig_img.copy()
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        for stroke in self.strokes:
            pts = stroke['points']
            if len(pts) < 2:
                continue
            color = stroke['color']
            width = stroke['width']
            # 绘制所有线段
            for i in range(len(pts) - 1):
                draw.line([pts[i], pts[i + 1]], fill=color, width=max(1, int(width)))

        # 生成唯一文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:20]
        qid = self.question['id'] if self.question else 'notebook'
        filename = f'note_{self.user["id"]}_{qid}_{timestamp}.png'
        filepath = os.path.join(self.NOTES_DIR, filename)

        img.save(filepath, 'PNG')
        img.close()

        # 保存到数据库（笔记本 / 更新已有页 / 题目笔记）
        if self.page_id is not None:
            # 覆盖更新已有笔记本页
            success = db_module.update_notebook_page(
                self.page_id, self.user['id'],
                content=f'画笔标注 - {timestamp}',
                note_type='drawing',
                image_path=filepath
            )
            msg = '' if success else '更新失败'
        elif self.save_to_notebook:
            qid = self.question['id'] if self.question else None
            note_label = '画笔绘制' if self.question is None else '截图笔记'
            success, _, msg = db_module.add_notebook_page(
                self.user['id'],
                content=f'{note_label} - {timestamp}',
                note_type='drawing',
                image_path=filepath,
                question_id=qid
            )
        else:
            success, msg = db_module.save_note(
                self.user['id'], self.question['id'],
                f'绘图笔记 - {timestamp}',
                note_type='drawing',
                image_path=filepath
            )

        if success:
            messagebox.showinfo('成功', '绘图笔记已保存')
            self.destroy()
        else:
            messagebox.showerror('失败', msg)
            # 出错时清理文件
            try:
                os.remove(filepath)
            except:
                pass

    def _close(self):
        """关闭不保存"""
        if self.strokes:
            if not messagebox.askyesno('确认关闭', '有未保存的标注，确定关闭吗？'):
                return
        self.destroy()


COLOR_DRAWING_BG = '#2c3e50'

class NotebookWindow(tk.Toplevel):
    """共享笔记本——翻页浏览、加页、截图添加、直接绘制"""

    def __init__(self, parent, user, subject=''):
        super().__init__(parent)
        self.user = user
        self.subject = subject
        self.pages = []
        self.current_idx = 0
        self._drawing_mode = False
        self._drawing_strokes = []
        self._current_pts = []

        self.title(f'📓 {subject}笔记本' if subject else '📓 笔记本')
        self.geometry('700x550')
        self.configure(bg=COLOR_WHITE)
        self.minsize(500, 400)

        self._build_ui()
        self._load_data()

        # 居中
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 700) // 2
        y = (self.winfo_screenheight() - 550) // 2
        self.geometry(f'+{x}+{y}')
        self.grab_set()

    def _build_ui(self):
        """构建笔记本UI"""
        # 顶部工具栏
        toolbar = tk.Frame(self, bg='#2c3e50', pady=6, padx=10)
        toolbar.pack(fill='x')

        tk.Label(toolbar, text='📓 共享笔记本', font=('Microsoft YaHei', 12, 'bold'),
                 fg=COLOR_WHITE, bg='#2c3e50').pack(side='left')
        self.mode_label = tk.Label(toolbar, text='', font=('Microsoft YaHei', 9, 'bold'),
                                   fg='#f1c40f', bg='#2c3e50')
        self.mode_label.pack(side='left', padx=8)

        tk.Button(toolbar, text='✏️ 截图添加', font=FONT_SMALL,
                  bg='#8e44ad', fg=COLOR_WHITE, bd=0, padx=10, pady=3,
                  command=self._add_screenshot).pack(side='right', padx=3)
        self.draw_btn = tk.Button(toolbar, text='🖌️ 画笔标注', font=FONT_SMALL,
                                  bg='#e67e22', fg=COLOR_WHITE, bd=0, padx=10, pady=3,
                                  command=self._toggle_drawing_mode)
        self.draw_btn.pack(side='right', padx=3)
        tk.Button(toolbar, text='➕ 新建页', font=FONT_SMALL,
                  bg=COLOR_SUCCESS, fg=COLOR_WHITE, bd=0, padx=10, pady=3,
                  command=self._add_text_page).pack(side='right', padx=3)

        # 页面内容显示区
        content_frame = tk.Frame(self, bg=COLOR_WHITE, bd=1, relief='groove')
        content_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.page_canvas = tk.Canvas(content_frame, bg='#fef9e7',
                                     highlightthickness=0)
        self.page_canvas.pack(fill='both', expand=True)
        self.page_canvas.bind('<Configure>', self._on_canvas_configure)

        # 底部翻页栏
        nav_frame = tk.Frame(self, bg=COLOR_BG, pady=8)
        nav_frame.pack(fill='x')

        self.prev_btn = tk.Button(nav_frame, text='◀ 上一页', font=FONT_NORMAL,
                                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=20, pady=5,
                                  command=self._prev_page)
        self.prev_btn.pack(side='left', padx=20)

        self.page_label = tk.Label(nav_frame, text='', font=('Microsoft YaHei', 12, 'bold'),
                                   fg=COLOR_PRIMARY, bg=COLOR_BG)
        self.page_label.pack(side='left', expand=True)

        self.next_btn = tk.Button(nav_frame, text='下一页 ▶', font=FONT_NORMAL,
                                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=20, pady=5,
                                  command=self._next_page)
        self.next_btn.pack(side='right', padx=20)

        # 删除按钮
        self.del_btn = tk.Button(nav_frame, text='🗑 删除此页', font=FONT_SMALL,
                                 bg=COLOR_DANGER, fg=COLOR_WHITE, bd=0, padx=10, pady=3,
                                 command=self._delete_current)
        self.del_btn.pack(side='bottom', pady=3)

    def _load_data(self):
        """加载所有页面"""
        self.pages = db_module.get_notebook_pages(self.user['id'])
        self.current_idx = 0 if self.pages else -1
        self._show_current()

    def _on_canvas_configure(self, event):
        """画布尺寸变化时处理"""
        if self._drawing_mode and hasattr(self, '_draw_overlay'):
            cw = self.page_canvas.winfo_width() or 600
            ch = self.page_canvas.winfo_height() or 400
            self.page_canvas.coords(self._draw_overlay, 0, 0, cw, ch)
            self.page_canvas.tag_raise('_draw_capture')
        elif self._adjust_active:
            # 调整模式中不重绘（避免销毁手柄）
            pass
        else:
            self._show_current()

    def _show_current(self):
        """显示当前页面"""
        self.page_canvas.delete('all')

        if not self.pages or self.current_idx < 0:
            w = self.page_canvas.winfo_width() or 600
            h = self.page_canvas.winfo_height() or 300
            self.page_canvas.create_text(w // 2, h // 2,
                text='📓 笔记本是空的\n点击「新建页」或「截图添加」开始记录\n已有笔记页可用「画笔标注」涂写\n截图添加将叠加到当前页，可拖拽移动、滚轮缩放',
                fill='#95a5a6', font=('Microsoft YaHei', 14), justify='center', tags='empty')
            self.page_label.config(text='无内容')
            self.prev_btn.config(state='disabled')
            self.next_btn.config(state='disabled')
            self.del_btn.config(state='disabled')
            return

        page = self.pages[self.current_idx]
        total = len(self.pages)
        self.page_label.config(text=f'第 {self.current_idx + 1} 页 / 共 {total} 页')
        self.prev_btn.config(state='normal' if self.current_idx > 0 else 'disabled')
        self.next_btn.config(state='normal' if self.current_idx < total - 1 else 'disabled')
        self.del_btn.config(state='normal')

        note_type = page.get('note_type', 'text')
        cw = max(100, self.page_canvas.winfo_width() - 40)
        y_offset = 15

        # 标题信息
        q_content = page.get('question_content', '')
        if q_content:
            self.page_canvas.create_text(20, y_offset, anchor='nw',
                text=f'📎 来自题目: {q_content[:80]}...',
                fill='#7f8c8d', font=FONT_SMALL, tags='info')
            y_offset += 25

        # 科目标签
        _, _, subj = self._parse_content(page)
        if subj:
            tag_colors = {'英语': '#3498db', '计算机考研': '#8e44ad'}
            tc = tag_colors.get(subj, '#95a5a6')
            self.page_canvas.create_text(20, y_offset, anchor='nw',
                text=f'🏷 {subj}',
                fill=tc, font=('Microsoft YaHei', 9, 'bold'), tags='info')
            y_offset += 20

        # 页码
        created = page.get('created_at', '')
        if created and hasattr(created, 'strftime'):
            self.page_canvas.create_text(20, y_offset, anchor='nw',
                text=f'📅 {created.strftime("%Y-%m-%d %H:%M")}',
                fill='#95a5a6', font=FONT_SMALL, tags='info')
            y_offset += 22

        y_offset += 10

        if note_type == 'drawing':
            # 绘图页：显示图片
            img_path = page.get('image_path', '')
            if img_path and os.path.exists(img_path):
                try:
                    pil_img = Image.open(img_path)
                    # 缩放以适应画布
                    max_w = cw
                    max_h = self.page_canvas.winfo_height() - y_offset - 20
                    if max_h < 100:
                        max_h = 300
                    w, h = pil_img.size
                    scale = min(max_w / w, max_h / h, 1.0)
                    if scale < 1:
                        nw, nh = int(w * scale), int(h * scale)
                        pil_img = pil_img.resize((nw, nh), Image.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    self.page_canvas.create_image(20, y_offset, image=tk_img,
                                                  anchor='nw', tags='img')
                    self.page_canvas.img_ref = tk_img
                except Exception as e:
                    self.page_canvas.create_text(20, y_offset, anchor='nw',
                        text=f'[图片加载失败: {e}]', fill=COLOR_DANGER,
                        font=FONT_NORMAL, tags='err')
            else:
                self.page_canvas.create_text(20, y_offset, anchor='nw',
                    text='[图片文件不存在]', fill='#95a5a6',
                    font=FONT_NORMAL, tags='err')
        else:
            # 文字页
            self._render_text_content(page, y_offset, cw)

        # 渲染叠加层（截图贴在当前页上）
        self._render_overlays(page)

    def _parse_content(self, page):
        """解析页面 content，返回 (text, overlays, subject)"""
        raw = page.get('content', '')
        text = raw
        overlays = []
        subject = ''
        if raw.startswith('{'):
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    text = data.get('text', '')
                    overlays = data.get('overlays', [])
                    subject = data.get('subject', '')
            except (json.JSONDecodeError, TypeError):
                pass
        return text, overlays, subject

    def _format_content(self, text, overlays, subject=''):
        """将 text + overlays + subject 格式化为存储用的字符串"""
        data = {'text': text, 'overlays': overlays}
        if subject:
            data['subject'] = subject
        if not overlays and not subject:
            return text  # 纯文本向后兼容
        return json.dumps(data, ensure_ascii=False)

    def _render_text_content(self, page, y_offset, cw):
        """渲染文字内容"""
        text, _, subj = self._parse_content(page)
        self.page_canvas.create_text(25, y_offset, anchor='nw',
            text=text if text else '(空白页)',
            fill=COLOR_PRIMARY, font=FONT_NORMAL,
            width=cw, tags='text')

    def _render_overlays(self, page):
        """在画布上渲染所有叠加层（截图在下，画笔在上）"""
        _, overlays, _ = self._parse_content(page)
        if not overlays:
            return
        self._overlay_data = overlays
        self._overlay_items = {}
        cw = self.page_canvas.winfo_width() or 600
        ch = self.page_canvas.winfo_height() or 400

        # 第一遍：渲染图片叠加层（截图）
        for i, ov in enumerate(overlays):
            if ov.get('type') == 'strokes':
                continue
            img_path = ov.get('image_path', '')
            if not img_path or not os.path.exists(img_path):
                continue
            try:
                pil_img = Image.open(img_path)
                ov_w, ov_h = ov.get('w', 200), ov.get('h', 150)
                max_scale = min(cw * 0.9 / ov_w, ch * 0.7 / ov_h, 2.0)
                disp_w, disp_h = int(ov_w * max_scale), int(ov_h * max_scale)
                pil_resized = pil_img.resize((disp_w, disp_h), Image.LANCZOS)
                tk_img = ImageTk.PhotoImage(pil_resized)
                tag_img = f'overlay_img_{i}'
                tag_all = f'overlay_{i}'
                x, y = ov.get('x', 20), ov.get('y', 40)

                self.page_canvas.create_rectangle(
                    x, y, x + disp_w, y + disp_h,
                    outline='#3498db', width=2, dash=(4, 2),
                    tags=(tag_all, f'border_{i}'))
                self.page_canvas.create_image(x, y, image=tk_img,
                    anchor='nw', tags=(tag_all, tag_img))
                if not hasattr(self, '_overlay_tk_refs'):
                    self._overlay_tk_refs = []
                self._overlay_tk_refs.append(tk_img)

                if not self._drawing_mode:
                    self.page_canvas.tag_bind(tag_all, '<Button-3>',
                        lambda e, idx=i: self._overlay_toggle(e, idx))
            except Exception as e:
                print(f'图片叠加层 {i} 渲染失败: {e}')

        # 第二遍：渲染画笔笔画（保持在最上层）
        for i, ov in enumerate(overlays):
            if ov.get('type') != 'strokes':
                continue
            for stroke in ov.get('strokes', []):
                pts = stroke.get('points', [])
                color = stroke.get('color', '#e74c3c')
                width = stroke.get('width', 3)
                for j in range(len(pts) - 1):
                    self.page_canvas.create_line(
                        pts[j][0], pts[j][1], pts[j+1][0], pts[j+1][1],
                        fill=color, width=width, capstyle='round', smooth=True,
                        tags=f'_saved_stroke_{i}')

    # ---- 叠加层交互：右键切换调整模式 ----
    _adjust_idx = -1
    _adjust_active = False
    _adj_start_x = 0
    _adj_start_y = 0
    _HANDLE_SIZE = 14               # 手柄尺寸（比之前大）
    _corner_handles = {}
    _img_cache = {}                 # idx -> PIL Image（缓存原图避免反复读盘）

    def _overlay_toggle(self, event, idx):
        if self._adjust_active and self._adjust_idx != idx:
            self._deactivate_adjust(self._adjust_idx)
        if self._adjust_active and self._adjust_idx == idx:
            self._deactivate_adjust(idx)
        else:
            self._activate_adjust(idx)

    def _activate_adjust(self, idx):
        self._adjust_active = True
        self._adjust_idx = idx
        self._adj_mode = ''
        ov = self._overlay_data[idx]
        img_path = ov.get('image_path', '')
        if img_path and os.path.exists(img_path):
            try:
                self._img_cache[idx] = Image.open(img_path)
            except:
                pass
        self.page_canvas.itemconfig(f'border_{idx}', outline='#e74c3c', width=3, dash='')
        self._draw_handles(idx)
        # canvas 级事件绑定（比 tag_bind 更稳定）
        self._adj_bind1 = self.page_canvas.bind('<Button-1>', self._adj_canvas_down, add='+')
        self._adj_bind2 = self.page_canvas.bind('<B1-Motion>', self._adj_canvas_move, add='+')
        self._adj_bind3 = self.page_canvas.bind('<ButtonRelease-1>', self._adj_canvas_up, add='+')
        self._adj_bind4 = self.page_canvas.bind('<Button-2>', self._adj_canvas_middle, add='+')
        self._show_tip('调整模式：拖拽移动/缩放 | 中键删除 | 右键固定')

    def _deactivate_adjust(self, idx):
        if not self._adjust_active:
            return
        self._adjust_active = False
        self._adj_mode = ''
        self.page_canvas.itemconfig(f'border_{idx}', outline='#3498db', width=2, dash=(4, 2))
        self._clear_handles(idx)
        self._img_cache.pop(idx, None)
        self.page_canvas.unbind('<Button-1>', self._adj_bind1)
        self.page_canvas.unbind('<B1-Motion>', self._adj_bind2)
        self.page_canvas.unbind('<ButtonRelease-1>', self._adj_bind3)
        self.page_canvas.unbind('<Button-2>', self._adj_bind4)
        self._save_overlay_positions()
        self._adjust_idx = -1
        self._show_tip('已固定')

    def _draw_handles(self, idx):
        """绘制 8 个黄色控制手柄（不带 tag_bind，由 canvas 级事件处理）"""
        self._clear_handles(idx)
        bxy = self.page_canvas.coords(f'border_{idx}')
        if not bxy or len(bxy) < 4:
            return
        x1, y1, x2, y2 = bxy[0], bxy[1], bxy[2], bxy[3]
        cx2, cy2 = (x1 + x2) / 2, (y1 + y2) / 2
        hs = self._HANDLE_SIZE
        half = hs // 2
        points = [
            ('tl', x1, y1), ('tr', x2 - hs, y1),
            ('bl', x1, y2 - hs), ('br', x2 - hs, y2 - hs),
            ('mt', cx2 - half, y1), ('mb', cx2 - half, y2 - hs),
            ('ml', x1, cy2 - half), ('mr', x2 - hs, cy2 - half),
        ]
        self._corner_handles[idx] = []
        for hname, hx, hy in points:
            rid = self.page_canvas.create_rectangle(
                hx, hy, hx + hs, hy + hs,
                fill='#f1c40f', outline='#2c3e50', width=1,
                tags=f'adj_{hname}_{idx}')
            self._corner_handles[idx].append(rid)

    def _clear_handles(self, idx):
        for hid in self._corner_handles.get(idx, []):
            self.page_canvas.delete(hid)
        self._corner_handles[idx] = []

    def _get_handle_at(self, x, y):
        """检测 (x,y) 处是否有手柄"""
        items = self.page_canvas.find_overlapping(x - 2, y - 2, x + 2, y + 2)
        for item in items:
            for t in self.page_canvas.gettags(item):
                if t.startswith('adj_'):
                    return t  # 如 'adj_tl_0'
        return ''

    def _adj_canvas_down(self, event):
        """按下鼠标——检测是移动还是缩放"""
        if not self._adjust_active:
            return
        idx = self._adjust_idx
        self._adj_start_x = event.x
        self._adj_start_y = event.y
        tag = self._get_handle_at(event.x, event.y)
        if tag:
            self._adj_mode = f'resize:{tag}'
        else:
            # 检测是否点击了图片本身
            items = self.page_canvas.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)
            img_tag = f'overlay_img_{idx}'
            self._adj_mode = 'move' if any(img_tag in self.page_canvas.gettags(it) for it in items) else ''

    def _adj_canvas_move(self, event):
        """拖拽——执行移动或缩放"""
        if not self._adjust_active or not self._adj_mode:
            return
        idx = self._adjust_idx
        dx = event.x - self._adj_start_x
        dy = event.y - self._adj_start_y
        self._adj_start_x = event.x
        self._adj_start_y = event.y

        if self._adj_mode == 'move':
            self.page_canvas.move(f'overlay_img_{idx}', dx, dy)
            self.page_canvas.move(f'border_{idx}', dx, dy)
            for hid in self._corner_handles.get(idx, []):
                self.page_canvas.move(hid, dx, dy)
            return

        # resize
        if self._adj_mode.startswith('resize:'):
            tag = self._adj_mode[7:]  # 'adj_tl_0'
            parts = tag.split('_')    # ['adj', 'tl', '0']
            handle = parts[1] if len(parts) >= 2 else ''
            img_xy = self.page_canvas.coords(f'overlay_img_{idx}')
            bdr_xy = self.page_canvas.coords(f'border_{idx}')
            if not img_xy or not bdr_xy or len(bdr_xy) < 4:
                return
            cx, cy = img_xy[0], img_xy[1]
            bw, bh = bdr_xy[2] - bdr_xy[0], bdr_xy[3] - bdr_xy[1]
            new_x, new_y, new_w, new_h = cx, cy, bw, bh
            if 'l' in handle: new_x = cx + dx; new_w = bw - dx
            if 'r' in handle: new_w = bw + dx
            if 't' in handle: new_y = cy + dy; new_h = bh - dy
            if 'b' in handle: new_h = bh + dy
            new_w, new_h = max(30, int(new_w)), max(30, int(new_h))
            # clamp 后重算位置，保证对角不动
            if 'l' in handle: new_x = cx + bw - new_w
            if 't' in handle: new_y = cy + bh - new_h
            orig = self._img_cache.get(idx)
            if orig is None:
                return
            try:
                tk_img = ImageTk.PhotoImage(orig.resize((new_w, new_h), Image.LANCZOS))
                self.page_canvas.itemconfig(f'overlay_img_{idx}', image=tk_img)
                self._overlay_tk_refs.append(tk_img)
                self.page_canvas.coords(f'overlay_img_{idx}', new_x, new_y)
                self.page_canvas.coords(f'border_{idx}', new_x, new_y, new_x + new_w, new_y + new_h)
                self._draw_handles(idx)
            except Exception as e:
                print(f'缩放失败: {e}')

    def _adj_canvas_up(self, event):
        """松开鼠标"""
        self._adj_mode = ''

    def _adj_canvas_middle(self, event):
        """鼠标中键——删除当前调整的截图"""
        if not self._adjust_active:
            return
        idx = self._adjust_idx
        if not messagebox.askyesno('确认删除', f'确定要删除截图叠加层 {idx+1} 吗？'):
            return
        page = self.pages[self.current_idx]
        text, overlays, subj = self._parse_content(page)
        if idx >= len(overlays):
            return
        # 清理图片文件
        old_path = overlays[idx].get('image_path', '')
        if old_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except:
                pass
        overlays.pop(idx)
        new_content = self._format_content(text, overlays, subj)
        ok = db_module.update_notebook_page(
            page['id'], self.user['id'], content=new_content)
        if not ok:
            messagebox.showerror('失败', '删除截图失败')
            return
        # 清理调整状态（不调用 _deactivate_adjust，避免触发 _save_overlay_positions 覆盖已删除的数据）
        self._adjust_active = False
        self._adj_mode = ''
        self._clear_handles(idx)
        self._img_cache.pop(idx, None)
        self._img_cache.clear()
        self.page_canvas.unbind('<Button-1>', self._adj_bind1)
        self.page_canvas.unbind('<B1-Motion>', self._adj_bind2)
        self.page_canvas.unbind('<ButtonRelease-1>', self._adj_bind3)
        self.page_canvas.unbind('<Button-2>', self._adj_bind4)
        self._adjust_idx = -1
        page['content'] = new_content
        self._load_data()
        self._show_tip('截图已删除')

    def _save_overlay_positions(self):
        """将当前画布上的叠加层位置保存到数据库"""
        if not self.pages or self.current_idx < 0:
            return
        page = self.pages[self.current_idx]
        text, _, subj = self._parse_content(page)
        overlays = self._overlay_data if hasattr(self, '_overlay_data') else []

        for i, ov in enumerate(overlays):
            coords = self.page_canvas.coords(f'overlay_img_{i}')
            bbox_coords = self.page_canvas.coords(f'border_{i}')
            if coords and bbox_coords:
                ov['x'] = int(coords[0])
                ov['y'] = int(coords[1])
                ov['w'] = int(bbox_coords[2] - bbox_coords[0])
                ov['h'] = int(bbox_coords[3] - bbox_coords[1])

        new_content = self._format_content(text, overlays, subj)
        db_module.update_notebook_page(
            page['id'], self.user['id'],
            content=new_content
        )
        # 更新本地缓存
        page['content'] = new_content

    def _prev_page(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._show_current()

    def _next_page(self):
        if self.current_idx < len(self.pages) - 1:
            self.current_idx += 1
            self._show_current()

    def _add_text_page(self):
        """新建空白页——直接创建，无需输入"""
        content = self._format_content('', [], self.subject)
        ok, _, msg = db_module.add_notebook_page(
            self.user['id'], content=content, note_type='text')
        if ok:
            self._load_data()
            self.current_idx = len(self.pages) - 1
            self._show_current()
        else:
            messagebox.showerror('失败', msg)

    def _toggle_drawing_mode(self):
        """切换画笔模式（直接在页面上绘制）"""
        if not self.pages or self.current_idx < 0:
            messagebox.showinfo('提示', '请先新建一个笔记页再进行绘制')
            return
        if self._drawing_mode:
            self._exit_drawing_mode()
        else:
            self._enter_drawing_mode()

    def _enter_drawing_mode(self):
        """进入画笔模式"""
        self._drawing_mode = True
        self._drawing_strokes = []
        self._current_pts = []
        # 更新 UI
        self.draw_btn.config(text='💾 保存画笔', bg='#27ae60')
        self.mode_label.config(text='✏️ 绘制中… Ctrl+Z撤销 右键/回车退出')
        # 重新绘制页面（叠加层不设交互）
        self._show_current()
        # 在画布最上层盖一张透明矩形，拦截鼠标事件（避免叠加层继续响应拖拽）
        cw = self.page_canvas.winfo_width() or 600
        ch = self.page_canvas.winfo_height() or 400
        self._draw_overlay = self.page_canvas.create_rectangle(
            0, 0, cw, ch, fill='', outline='', tags='_draw_capture')
        self.page_canvas.tag_bind('_draw_capture', '<Button-1>', self._draw_start)
        self.page_canvas.tag_bind('_draw_capture', '<B1-Motion>', self._draw_move)
        self.page_canvas.tag_bind('_draw_capture', '<ButtonRelease-1>', self._draw_end)
        self.page_canvas.tag_bind('_draw_capture', '<Enter>', lambda e: self.page_canvas.config(cursor='pencil'))
        self.page_canvas.tag_bind('_draw_capture', '<Leave>', lambda e: self.page_canvas.config(cursor=''))
        # 窗口级快捷键
        self._draw_bind_id4 = self.bind('<Button-3>', lambda e: self._exit_drawing_mode())
        self._draw_bind_id5 = self.bind('<Return>', lambda e: self._exit_drawing_mode())
        self._draw_bind_id6 = self.bind('<Control-z>', lambda e: self._undo_last_stroke())

    def _exit_drawing_mode(self):
        """退出画笔模式"""
        if not self._drawing_mode:
            return
        self._drawing_mode = False
        # 保存笔画
        if self._drawing_strokes:
            self._save_drawing_strokes()
        # 移除窗口级快捷键
        self.unbind('<Button-3>')
        self.unbind('<Return>')
        self.unbind('<Control-z>')
        # 更新 UI
        self.draw_btn.config(text='🖌️ 画笔标注', bg='#e67e22')
        self.mode_label.config(text='')
        self._drawing_strokes = []
        self._current_pts = []
        # 刷新页面（delete('all') 会自动清除 _draw_capture 矩形）
        self._show_current()

    def _draw_start(self, event):
        """开始绘制一笔"""
        if not self._drawing_mode:
            return
        self._current_pts = [(event.x, event.y)]
        # 画起点圆点
        r = 2
        self.page_canvas.create_oval(
            event.x - r, event.y - r, event.x + r, event.y + r,
            fill='#e74c3c', outline='', tags='_drawing_stroke')
        self.page_canvas.tag_raise('_drawing_stroke')

    def _draw_move(self, event):
        """继续绘制"""
        if not self._drawing_mode or not self._current_pts:
            return
        last_x, last_y = self._current_pts[-1]
        self._current_pts.append((event.x, event.y))
        self.page_canvas.create_line(
            last_x, last_y, event.x, event.y,
            fill='#e74c3c', width=3, capstyle='round', smooth=True,
            tags='_drawing_stroke')
        self.page_canvas.tag_raise('_drawing_stroke')

    def _draw_end(self, event):
        """结束一笔"""
        if not self._drawing_mode or not self._current_pts:
            return
        if len(self._current_pts) >= 2:
            self._drawing_strokes.append({
                'points': list(self._current_pts),
                'color': '#e74c3c',
                'width': 3,
            })
        self._current_pts = []

    def _undo_last_stroke(self):
        """撤销上一笔（Ctrl+Z）"""
        if not self._drawing_strokes:
            self._show_tip('没有可撤销的笔画')
            return
        self._drawing_strokes.pop()
        # 清除画布上所有临时笔画，重新绘制剩余笔画
        self.page_canvas.delete('_drawing_stroke')
        for stroke in self._drawing_strokes:
            pts = stroke['points']
            for j in range(len(pts) - 1):
                self.page_canvas.create_line(
                    pts[j][0], pts[j][1], pts[j+1][0], pts[j+1][1],
                    fill=stroke['color'], width=stroke['width'],
                    capstyle='round', smooth=True, tags='_drawing_stroke')
        self.page_canvas.tag_raise('_drawing_stroke')
        self._show_tip(f'已撤销（剩余 {len(self._drawing_strokes)} 笔）')

    def _save_drawing_strokes(self):
        """将绘制的笔画保存为叠加层"""
        if not self._drawing_strokes:
            return
        page = self.pages[self.current_idx]
        text, overlays, subj = self._parse_content(page)
        overlays.append({
            'type': 'strokes',
            'strokes': self._drawing_strokes,
        })
        new_content = self._format_content(text, overlays, subj)
        ok = db_module.update_notebook_page(
            page['id'], self.user['id'], content=new_content)
        if ok:
            page['content'] = new_content
            self._show_tip(f'已保存 {len(self._drawing_strokes)} 笔绘制')

    def _add_screenshot(self, hide_window=True):
        """截图叠加到当前页（可拖拽移动、缩放）"""
        if not self.pages or self.current_idx < 0:
            messagebox.showinfo('提示', '请先新建一个笔记页，然后将截图叠加到该页')
            return

        if hide_window and messagebox.askyesno('截图选项',
            '截图前是否隐藏笔记本窗口？\n（隐藏后可截取被窗口挡住的内容）'):
            self.withdraw()
            self.update()
            import time
            time.sleep(0.3)

        restored = False
        def _restore():
            nonlocal restored
            if not restored:
                restored = True
                try:
                    self.deiconify()
                    self.lift()
                    self.focus_set()
                except:
                    pass

        try:
            selector = ScreenshotSelector(self)
            self.wait_window(selector)
            if selector.selection is None:
                _restore()
                return

            x1, y1, x2, y2 = selector.selection
            self.update()
            import time
            time.sleep(0.1)
            captured = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            if captured is None or captured.size[0] < 10:
                _restore()
                return

            _restore()

            # 保存截图图片到本地
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:20]
            os.makedirs(DrawingCanvas.NOTES_DIR, exist_ok=True)
            filename = f'screenshot_{self.user["id"]}_{timestamp}.png'
            filepath = os.path.join(DrawingCanvas.NOTES_DIR, filename)
            captured.save(filepath, 'PNG')

            # 叠加到当前页
            page = self.pages[self.current_idx]
            text, overlays, subj = self._parse_content(page)
            cw = self.page_canvas.winfo_width() or 600
            default_x = 30
            default_y = 60 + len(overlays) * 30
            overlays.append({
                'image_path': filepath,
                'x': default_x,
                'y': default_y,
                'w': captured.width,
                'h': captured.height,
            })
            new_content = self._format_content(text, overlays, subj)
            ok = db_module.update_notebook_page(
                page['id'], self.user['id'],
                content=new_content,
                note_type=page.get('note_type', 'text')
            )
            if ok:
                page['content'] = new_content
                self._show_current()  # 刷新显示叠加层
                self._show_tip(f'截图已叠加到当前页（可拖拽移动、滚轮缩放）')
            else:
                messagebox.showerror('失败', '保存截图叠加层失败')
                try:
                    os.remove(filepath)
                except:
                    pass
        except Exception as e:
            _restore()
            import traceback
            traceback.print_exc()
            messagebox.showerror('错误', f'截图失败: {str(e)}')

    def _show_tip(self, msg):
        """在导航栏显示提示信息（3秒后恢复页码显示）"""
        old_text = self.page_label.cget('text')
        self.page_label.config(text=msg)
        self.after(3000, lambda: self._restore_page_label(old_text))

    def _restore_page_label(self, old_text):
        """恢复页码标签（不触发重绘，避免销毁调整模式状态）"""
        try:
            if self._adjust_active:
                return  # 调整模式中保持提示
            total = len(self.pages) if hasattr(self, 'pages') and self.pages else 0
            idx = self.current_idx if hasattr(self, 'current_idx') else 0
            if total > 0:
                self.page_label.config(text=f'第 {idx + 1} 页 / 共 {total} 页')
            else:
                self.page_label.config(text=old_text)
        except Exception:
            self.page_label.config(text=old_text)

    def _delete_current(self):
        if not self.pages or self.current_idx < 0:
            return
        page = self.pages[self.current_idx]
        if messagebox.askyesno('确认删除', f'确定要删除第 {self.current_idx + 1} 页吗？'):
            if db_module.delete_notebook_page(self.user['id'], page['id']):
                self._load_data()
            else:
                messagebox.showerror('失败', '删除失败')


class MainApplication:
    """主应用程序"""

    def __init__(self, user):
        self.user = user
        self.current_subject = '英语'
        self.window = tk.Tk()
        self.window.title(f'英语刷题系统 - 欢迎, {user["nickname"]}')
        self.window.geometry('800x650')
        self.window.configure(bg=COLOR_BG)
        self.window.minsize(800, 600)

        # 居中
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 800) // 2
        y = (self.window.winfo_screenheight() - 650) // 2
        self.window.geometry(f'+{x}+{y}')

        self._build_ui()
        self._load_subjects()

    def _load_subjects(self):
        """加载科目列表到下拉框"""
        subjects = db_module.get_subjects()
        if subjects:
            names = [s['name'] for s in subjects]
            self.subject_combo['values'] = names
            if self.current_subject in names:
                self.subject_combo.set(self.current_subject)

    def _on_subject_change(self, event=None):
        """切换科目"""
        name = self.subject_combo.get()
        if not name or name == self.current_subject:
            return
        ok = db_module.switch_subject(name)
        if ok:
            self.current_subject = name
            self.window.title(f'刷题系统 - {name} - 欢迎, {self.user["nickname"]}')
            self._rebuild_tabs()
        else:
            import tkinter.messagebox as mb
            mb.showerror('错误', f'切换科目失败：科目 "{name}" 不存在')

    def _rebuild_tabs(self):
        """刷新所有标签页"""
        # 清除旧标签页
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

        # 刷题面板
        pf = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(pf, text='  刷题  ')
        self.practice_panel = PracticePanel(pf, self.user, subject=self.current_subject)

        # 错题本
        wf = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(wf, text='  错题本  ')
        WrongAnswerPanel(wf, self.user, subject=self.current_subject)

        # 笔记本
        nf = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(nf, text='  笔记本  ')
        NotesPanel(nf, self.user, subject=self.current_subject)

        # AI 资料题库（独立于正式 questions 题库）
        af = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(af, text='  AI资料题库  ')
        from .material_panel import AIMaterialPanel
        AIMaterialPanel(
            af, self.user, self.current_subject,
            on_practice=lambda question: AIPracticeDialog(
                self.window, self.user, question
            )
        )

        # 数据分析
        sf = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(sf, text='  数据分析  ')
        StatsPanel(sf, self.user)

    def _build_ui(self):
        """构建主界面"""
        # 顶部栏
        top_bar = tk.Frame(self.window, bg=COLOR_PRIMARY, height=50)
        top_bar.pack(fill='x')
        top_bar.pack_propagate(False)

        tk.Label(top_bar, text='刷题系统', font=('Microsoft YaHei', 14, 'bold'),
                 fg=COLOR_WHITE, bg=COLOR_PRIMARY).pack(side='left', padx=15, pady=10)

        # 科目选择
        tk.Label(top_bar, text='科目:', font=('Microsoft YaHei', 10),
                 fg='#bdc3c7', bg=COLOR_PRIMARY).pack(side='left', padx=(5, 2))
        self.subject_combo = ttk.Combobox(top_bar, width=14,
                                          font=('Microsoft YaHei', 10), state='readonly')
        self.subject_combo.pack(side='left', padx=2)
        self.subject_combo.bind('<<ComboboxSelected>>', self._on_subject_change)

        tk.Label(top_bar, text=f'用户: {self.user["nickname"]}',
                 font=FONT_NORMAL, fg='#bdc3c7', bg=COLOR_PRIMARY).pack(side='right', padx=20)

        # 退出按钮
        tk.Button(top_bar, text='退出登录', font=FONT_SMALL,
                  bg=COLOR_DANGER, fg=COLOR_WHITE, bd=0, padx=10, pady=3,
                  command=self._logout).pack(side='right', padx=10)

        # Notebook 标签页
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # 初始构建（英语科目）
        self._rebuild_tabs()

    def _logout(self):
        """退出登录"""
        if messagebox.askyesno('确认退出', '确定要退出登录吗？'):
            self.window.destroy()

    def run(self):
        self.window.protocol('WM_DELETE_WINDOW', self._logout)
        self.window.mainloop()


def main():
    """主程序入口"""
    login = LoginWindow()
    user = login.run()
    if user:
        app = MainApplication(user)
        app.run()


if __name__ == '__main__':
    main()
