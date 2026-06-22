"""AI 资料题库 GUI。"""
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import api_client
from .document_reader import DocumentReadError, read_document


FONT_NORMAL = ('Microsoft YaHei', 11)
FONT_SMALL = ('Microsoft YaHei', 9)
COLOR_PRIMARY = '#2c3e50'
COLOR_ACCENT = '#3498db'
COLOR_SUCCESS = '#27ae60'
COLOR_DANGER = '#e74c3c'
COLOR_WARNING = '#f39c12'
COLOR_BG = '#f5f6fa'
COLOR_WHITE = '#ffffff'
COLOR_AI = '#8e44ad'


class AIMaterialPanel:
    """导入资料、查看总结并管理独立生成题库。"""

    TYPE_MAP = {
        '混合题型': 'mixed', '选择题': 'choice', '判断题': 'true_false',
        '填空题': 'fill_blank', '简答题': 'short_answer',
    }

    def __init__(self, parent, user, subject, on_practice):
        self.parent = parent
        self.user = user
        self.subject = subject
        self.on_practice = on_practice
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        header = tk.Frame(self.parent, bg=COLOR_BG, pady=8)
        header.pack(fill='x')
        tk.Label(header, text='🤖 AI 资料题库',
                 font=('Microsoft YaHei', 14, 'bold'),
                 fg=COLOR_PRIMARY, bg=COLOR_BG).pack(side='left', padx=10)
        tk.Button(header, text='刷新', font=FONT_SMALL, bg=COLOR_ACCENT,
                  fg=COLOR_WHITE, bd=0, padx=12, pady=4,
                  command=self._load_data).pack(side='right', padx=10)
        tk.Button(header, text='导入资料并生成', font=FONT_NORMAL, bg=COLOR_AI,
                  fg=COLOR_WHITE, bd=0, padx=15, pady=4,
                  command=self._import_material).pack(side='right', padx=4)

        settings = tk.Frame(self.parent, bg=COLOR_WHITE, bd=1,
                            relief='groove', padx=10, pady=7)
        settings.pack(fill='x', padx=10, pady=(0, 6))
        tk.Label(settings, text='题型：', font=FONT_SMALL,
                 bg=COLOR_WHITE).pack(side='left')
        self.type_var = tk.StringVar(value='混合题型')
        ttk.Combobox(settings, textvariable=self.type_var,
                     values=list(self.TYPE_MAP), state='readonly',
                     width=10).pack(side='left', padx=(0, 12))
        tk.Label(settings, text='题数：', font=FONT_SMALL,
                 bg=COLOR_WHITE).pack(side='left')
        self.count_var = tk.IntVar(value=5)
        tk.Spinbox(settings, from_=1, to=10, textvariable=self.count_var,
                   width=4).pack(side='left', padx=(0, 12))
        tk.Label(settings, text='难度：', font=FONT_SMALL,
                 bg=COLOR_WHITE).pack(side='left')
        self.difficulty_var = tk.IntVar(value=3)
        ttk.Combobox(settings, textvariable=self.difficulty_var,
                     values=[1, 2, 3, 4, 5], state='readonly',
                     width=4).pack(side='left')
        tk.Label(settings, text='支持 TXT / MD / PDF / DOCX 等文本资料',
                 font=FONT_SMALL, fg='#7f8c8d',
                 bg=COLOR_WHITE).pack(side='right')

        content = tk.Frame(self.parent, bg=COLOR_WHITE, bd=1, relief='groove')
        content.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.canvas = tk.Canvas(content, bg=COLOR_WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(content, orient='vertical',
                                  command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas, bg=COLOR_WHITE)
        self.list_frame.bind(
            '<Configure>',
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        )
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.list_frame, anchor='nw'
        )
        self.canvas.bind(
            '<Configure>',
            lambda event: self.canvas.itemconfig(self.canvas_window, width=event.width)
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def _load_data(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        materials = api_client.get_ai_materials(
            self.user['id'], subject=self.subject
        )
        if not materials:
            tk.Label(
                self.list_frame,
                text='还没有 AI 资料题库\n点击“导入资料并生成”开始',
                font=FONT_NORMAL, fg='#7f8c8d', bg=COLOR_WHITE,
                justify='center'
            ).pack(pady=60)
            return
        for material in materials:
            self._render_card(material)

    def _render_card(self, material):
        card = tk.Frame(self.list_frame, bg=COLOR_BG, bd=1,
                        relief='groove', padx=12, pady=9)
        card.pack(fill='x', padx=10, pady=5)
        title_row = tk.Frame(card, bg=COLOR_BG)
        title_row.pack(fill='x')
        tk.Label(
            title_row, text=material.get('title') or material.get('filename'),
            font=('Microsoft YaHei', 11, 'bold'), fg=COLOR_PRIMARY,
            bg=COLOR_BG
        ).pack(side='left')
        tk.Label(
            title_row,
            text=f'{material.get("file_type", "").upper()} · {material.get("question_count", 0)}题',
            font=FONT_SMALL, fg=COLOR_AI, bg=COLOR_BG
        ).pack(side='right')
        tk.Label(
            card, text=(material.get('summary') or '')[:220] +
                       ('…' if len(material.get('summary') or '') > 220 else ''),
            font=FONT_SMALL, fg='#566573', bg=COLOR_BG,
            wraplength=650, justify='left'
        ).pack(anchor='w', pady=5)
        points = material.get('knowledge_points') or []
        names = [str(point.get('name', '')) if isinstance(point, dict) else str(point)
                 for point in points[:6]]
        if names:
            tk.Label(card, text='知识点：' + '、'.join(filter(None, names)),
                     font=FONT_SMALL, fg=COLOR_WARNING, bg=COLOR_BG,
                     wraplength=650, justify='left').pack(anchor='w')
        buttons = tk.Frame(card, bg=COLOR_BG)
        buttons.pack(fill='x', pady=(6, 0))
        tk.Button(
            buttons, text='查看总结与题目', font=FONT_SMALL,
            bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=10, pady=3,
            command=lambda mid=material['id']: self._open_material(mid)
        ).pack(side='left')
        tk.Button(
            buttons, text='删除', font=FONT_SMALL, bg=COLOR_DANGER,
            fg=COLOR_WHITE, bd=0, padx=10, pady=3,
            command=lambda mid=material['id']: self._delete_material(mid)
        ).pack(side='right')

    def _import_material(self):
        path = filedialog.askopenfilename(
            parent=self.parent.winfo_toplevel(), title='选择学习资料',
            filetypes=[
                ('支持的资料', '*.txt *.md *.markdown *.rst *.csv *.json *.py *.html *.htm *.pdf *.docx'),
                ('PDF', '*.pdf'), ('Word 文档', '*.docx'),
                ('文本文件', '*.txt *.md *.csv'), ('所有文件', '*.*'),
            ]
        )
        if not path:
            return
        try:
            document = read_document(path)
            question_count = int(self.count_var.get())
            difficulty = int(self.difficulty_var.get())
        except (DocumentReadError, ValueError) as exc:
            messagebox.showerror('无法读取资料', str(exc), parent=self.parent)
            return
        if not messagebox.askyesno(
            '确认生成',
            f'已提取 {document["char_count"]:,} 个字符。\n'
            f'将生成 {question_count} 道题，可能需要数十秒到数分钟。\n\n'
            '注意：提取的文字内容将发送给 DeepSeek API。\n\n继续吗？',
            parent=self.parent
        ):
            return

        payload = {
            'user_id': self.user['id'],
            'filename': document['filename'],
            'file_type': document['file_type'],
            'content': document['content'],
            'subject': self.subject,
            'question_type': self.TYPE_MAP.get(self.type_var.get(), 'mixed'),
            'question_count': question_count,
            'difficulty': difficulty,
        }
        self._run_generation(payload)

    def _run_generation(self, payload):
        loading = tk.Toplevel(self.parent)
        loading.title('AI 正在分析资料')
        loading.geometry('430x150')
        loading.resizable(False, False)
        loading.transient(self.parent.winfo_toplevel())
        loading.protocol('WM_DELETE_WINDOW', lambda: None)
        tk.Label(loading, text='🤖 正在提炼知识点并生成题目…',
                 font=FONT_NORMAL).pack(pady=(24, 10))
        tk.Label(loading, text='长资料会分段处理，请耐心等待',
                 font=FONT_SMALL, fg='#7f8c8d').pack()
        progress = ttk.Progressbar(loading, mode='indeterminate', length=330)
        progress.pack(pady=12)
        progress.start(12)
        results = queue.Queue(maxsize=1)

        def worker():
            results.put(api_client.generate_ai_material_bank(payload))

        def poll():
            try:
                material, error = results.get_nowait()
            except queue.Empty:
                try:
                    loading.after(150, poll)
                except tk.TclError:
                    pass
                return
            progress.stop()
            loading.destroy()
            if material:
                self._load_data()
                AIMaterialDetailWindow(
                    self.parent, self.user, material, self.on_practice
                )
            else:
                messagebox.showerror('生成失败', error or '未知错误',
                                     parent=self.parent)

        threading.Thread(target=worker, daemon=True).start()
        loading.after(150, poll)

    def _open_material(self, material_id):
        material = api_client.get_ai_material(material_id, self.user['id'])
        if not material:
            messagebox.showerror('错误', '资料题库读取失败', parent=self.parent)
            return
        AIMaterialDetailWindow(
            self.parent, self.user, material, self.on_practice
        )

    def _delete_material(self, material_id):
        if not messagebox.askyesno(
            '确认删除', '将同时删除该资料生成的全部题目，是否继续？',
            parent=self.parent
        ):
            return
        if api_client.delete_ai_material(material_id, self.user['id']):
            self._load_data()
        else:
            messagebox.showerror('删除失败', '请刷新后重试', parent=self.parent)


class AIMaterialDetailWindow(tk.Toplevel):
    """资料总结、知识点和生成题详情。"""

    TYPE_NAMES = {
        'choice': '选择题', 'true_false': '判断题',
        'fill_blank': '填空题', 'short_answer': '简答题',
    }

    def __init__(self, parent, user, material, on_practice):
        super().__init__(parent)
        self.user = user
        self.material = material
        self.on_practice = on_practice
        self.title('AI 资料题库详情')
        self.geometry('800x680')
        self.minsize(700, 560)
        self._build_ui()

    def _build_ui(self):
        toolbar = tk.Frame(self, bg=COLOR_PRIMARY, padx=12, pady=8)
        toolbar.pack(fill='x')
        tk.Label(toolbar, text=self.material.get('title', '资料详情'),
                 font=('Microsoft YaHei', 13, 'bold'),
                 fg=COLOR_WHITE, bg=COLOR_PRIMARY).pack(side='left')
        tk.Button(toolbar, text='查看提取原文', font=FONT_SMALL,
                  bg=COLOR_ACCENT, fg=COLOR_WHITE, bd=0, padx=10,
                  command=self._show_source).pack(side='right')

        canvas = tk.Canvas(self, bg=COLOR_WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=canvas.yview)
        body = tk.Frame(canvas, bg=COLOR_WHITE)
        body.bind('<Configure>',
                  lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        window = canvas.create_window((0, 0), window=body, anchor='nw')
        canvas.bind('<Configure>',
                    lambda e: canvas.itemconfig(window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self._section(body, '📝 内容总结', self.material.get('summary', ''))
        points = self.material.get('knowledge_points') or []
        point_text = []
        for index, point in enumerate(points, 1):
            if isinstance(point, dict):
                text = point.get('name', '')
                if point.get('description'):
                    text += f'：{point["description"]}'
            else:
                text = str(point)
            if text:
                point_text.append(f'{index}. {text}')
        self._section(body, '🧠 核心知识点', '\n'.join(point_text) or '暂无')

        tk.Label(body, text=f'📚 生成题目（{len(self.material.get("questions", []))}）',
                 font=('Microsoft YaHei', 13, 'bold'), fg=COLOR_PRIMARY,
                 bg=COLOR_WHITE).pack(anchor='w', padx=15, pady=(12, 4))
        for index, question in enumerate(self.material.get('questions', []), 1):
            self._question_card(body, index, question)

    def _section(self, parent, title, content):
        frame = tk.Frame(parent, bg=COLOR_BG, bd=1, relief='groove',
                         padx=12, pady=10)
        frame.pack(fill='x', padx=15, pady=6)
        tk.Label(frame, text=title, font=('Microsoft YaHei', 11, 'bold'),
                 fg=COLOR_AI, bg=COLOR_BG).pack(anchor='w')
        tk.Label(frame, text=content, font=FONT_SMALL, fg=COLOR_PRIMARY,
                 bg=COLOR_BG, wraplength=720, justify='left').pack(
                     anchor='w', pady=(5, 0))

    def _question_card(self, parent, index, question):
        card = tk.Frame(parent, bg='#f8f9f9', bd=1, relief='groove',
                        padx=12, pady=9)
        card.pack(fill='x', padx=15, pady=5)
        qtype = self.TYPE_NAMES.get(question.get('type'), question.get('type', ''))
        tk.Label(card, text=f'{index}. [{qtype}] {question.get("content", "")}',
                 font=FONT_NORMAL, fg=COLOR_PRIMARY, bg='#f8f9f9',
                 wraplength=700, justify='left').pack(anchor='w')
        options = question.get('options') or {}
        if isinstance(options, dict):
            for key in sorted(options):
                tk.Label(card, text=f'{key}. {options[key]}', font=FONT_SMALL,
                         fg='#566573', bg='#f8f9f9', wraplength=680,
                         justify='left').pack(anchor='w', padx=15)
        tk.Label(card, text=f'答案：{question.get("answer", "")}',
                 font=FONT_SMALL, fg=COLOR_SUCCESS, bg='#f8f9f9',
                 wraplength=680, justify='left').pack(anchor='w', pady=(5, 0))
        if question.get('explanation'):
            tk.Label(card, text=f'解析：{question["explanation"]}',
                     font=FONT_SMALL, fg='#7f8c8d', bg='#f8f9f9',
                     wraplength=680, justify='left').pack(anchor='w')
        tk.Button(
            card, text='练习此题', font=FONT_SMALL, bg=COLOR_WARNING,
            fg=COLOR_WHITE, bd=0, padx=10, pady=3,
            command=lambda q=question: self.on_practice(q)
        ).pack(anchor='e', pady=(5, 0))

    def _show_source(self):
        window = tk.Toplevel(self)
        window.title('提取的资料原文')
        window.geometry('720x600')
        text = tk.Text(window, wrap='word', font=FONT_SMALL, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(window, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        text.insert('1.0', self.material.get('source_content', ''))
        text.config(state='disabled')
