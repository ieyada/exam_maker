'''A window for designing and generating exams. Start it with:

    python exam_maker_gui.py

It does the same job as the terminal program (exam_maker.py): pick the question bank, fill in the exam
details, choose the chapters and how many questions of each type/difficulty to draw, then press
"Generate exams". The PDFs, .tex files and the answer key are written to this folder.'''

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import exam_core as core

# Remembers what was typed last time, so it does not have to be entered again
SETTINGS_FILE = core.DOC_DIR / "exam_maker_settings.json"
DEFAULT_BANK = core.PROJECT_DIR / "Exmple_Ques_Bank.xlsx"
TYPE_LABELS = {"TF": "True / False", "MC": "Multiple choice"}
CHAPTERS_PER_ROW = 8


def to_int(text):
    try:
        return int(str(text).strip())
    except ValueError:
        return None


def to_float(text):
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def open_path(path: Path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


class ExamMakerApp(ttk.Frame):

    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=12)
        self.root = root
        self.bank = None
        self.working = False
        self.messages = queue.Queue()      # messages from the generation thread

        self.bank_path = tk.StringVar()
        self.bank_info = tk.StringVar(value="No question bank loaded.")
        self.course = tk.StringVar()
        self.semester = tk.StringVar()
        self.exam_type = tk.StringVar(value="Midterm")
        self.duration = tk.StringVar(value="60")
        self.exam_date = tk.StringVar()
        self.use_today = tk.BooleanVar(value=True)
        self.sections = tk.StringVar()
        self.versions = tk.StringVar(value="2")
        self.chapter_vars = {}             # chapter number -> BooleanVar
        self.counts = {t: {d: tk.StringVar(value="0") for d in core.DIFFICULTIES} for t in core.QUESTION_TYPES}
        self.points = {t: tk.StringVar(value="1") for t in core.QUESTION_TYPES}
        self.summary = tk.StringVar()
        self.status = tk.StringVar(value="Ready.")

        self.build()
        self.load_settings()
        for var in [self.versions, *self.points.values(), *(v for t in self.counts.values() for v in t.values())]:
            var.trace_add("write", lambda *_: self.refresh())
        self.refresh()
        self.after(100, self.poll_messages)

    ################################################################################################
    # Layout
    ################################################################################################

    def build(self):
        style = ttk.Style()
        style.configure("Hint.TLabel", foreground="#666666")
        style.configure("Error.TLabel", foreground="#b00020")
        style.configure("Total.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 6))

        self.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)

        ########## Question bank
        bank = ttk.LabelFrame(self, text="Question bank", padding=8)
        bank.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        bank.columnconfigure(0, weight=1)
        ttk.Entry(bank, textvariable=self.bank_path).grid(row=0, column=0, sticky="ew")
        ttk.Button(bank, text="Browse…", command=self.browse_bank).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(bank, text="Load", command=lambda: self.load_bank(self.bank_path.get())).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(bank, textvariable=self.bank_info, style="Hint.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        ########## Exam details
        details = ttk.LabelFrame(self, text="Exam details", padding=8)
        details.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(0, 8))
        details.columnconfigure(1, weight=1)

        def field(row, label, widget, hint=None):
            ttk.Label(details, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
            widget.grid(row=row, column=1, sticky="ew", pady=3)
            if hint:
                ttk.Label(details, text=hint, style="Hint.TLabel").grid(row=row, column=2, sticky="w", padx=(6, 0))

        field(0, "Course", ttk.Entry(details, textvariable=self.course), "e.g. FINA363")
        field(1, "Semester", ttk.Entry(details, textvariable=self.semester), "e.g. Fall 2025")
        field(2, "Exam type", ttk.Combobox(details, textvariable=self.exam_type, values=list(core.EXAM_TYPES), state="readonly"))
        field(3, "Duration", ttk.Spinbox(details, textvariable=self.duration, from_=1, to=600, increment=5), "minutes")
        self.date_entry = ttk.Entry(details, textvariable=self.exam_date)
        field(4, "Exam date", self.date_entry)
        ttk.Checkbutton(details, text="Today", variable=self.use_today, command=self.toggle_date).grid(row=4, column=2, sticky="w", padx=(6, 0))
        field(5, "Sections", ttk.Entry(details, textvariable=self.sections), "separate with spaces")
        field(6, "Versions", ttk.Spinbox(details, textvariable=self.versions, from_=1, to=core.MAX_VERSIONS), f"1 to {core.MAX_VERSIONS} (A, B, C…)")

        ########## Chapters
        chapters = ttk.LabelFrame(self, text="Chapters to draw questions from", padding=8)
        chapters.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(0, 8))
        chapters.columnconfigure(0, weight=1)
        self.chapter_box = ttk.Frame(chapters)
        self.chapter_box.grid(row=0, column=0, sticky="nw")
        buttons = ttk.Frame(chapters)
        buttons.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Select all", command=lambda: self.select_chapters(True)).pack(side="left")
        ttk.Button(buttons, text="Clear", command=lambda: self.select_chapters(False)).pack(side="left", padx=(6, 0))
        self.build_chapters([])

        ########## Questions
        questions = ttk.LabelFrame(self, text="Questions per version", padding=8)
        questions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        headers = ["", *core.DIFFICULTIES, "Questions", "Points each", "Section points"]
        for col, text in enumerate(headers):
            ttk.Label(questions, text=text).grid(row=0, column=col, padx=8, sticky="w")
            questions.columnconfigure(col, weight=1)

        self.available_labels = {}
        self.question_totals = {}
        self.point_totals = {}
        for i, q_type in enumerate(core.QUESTION_TYPES):
            row = 1 + 2 * i
            ttk.Label(questions, text=TYPE_LABELS[q_type]).grid(row=row, column=0, padx=8, sticky="w")
            for col, difficulty in enumerate(core.DIFFICULTIES, start=1):
                ttk.Spinbox(questions, textvariable=self.counts[q_type][difficulty], from_=0, to=999, width=6).grid(row=row, column=col, padx=8, sticky="w")
                label = ttk.Label(questions, style="Hint.TLabel")
                label.grid(row=row + 1, column=col, padx=8, sticky="nw", pady=(0, 6))
                self.available_labels[q_type, difficulty] = label
            self.question_totals[q_type] = ttk.Label(questions)
            self.question_totals[q_type].grid(row=row, column=4, padx=8, sticky="w")
            ttk.Spinbox(questions, textvariable=self.points[q_type], from_=0, to=100, increment=0.5, width=6).grid(row=row, column=5, padx=8, sticky="w")
            self.point_totals[q_type] = ttk.Label(questions)
            self.point_totals[q_type].grid(row=row, column=6, padx=8, sticky="w")
        ttk.Label(questions, textvariable=self.summary, style="Total.TLabel").grid(row=5, column=0, columnspan=7, sticky="w", padx=8, pady=(4, 0))

        ########## Actions
        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        actions.columnconfigure(2, weight=1)
        self.generate_button = ttk.Button(actions, text="Generate exams", style="Accent.TButton", command=self.generate)
        self.generate_button.grid(row=0, column=0)
        ttk.Button(actions, text="Open output folder", command=lambda: open_path(core.DOC_DIR)).grid(row=0, column=1, padx=(8, 0))
        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=160)
        self.progress.grid(row=0, column=3, padx=(8, 0))
        self.progress.grid_remove()        # only shown while generating
        ttk.Label(actions, textvariable=self.status, style="Hint.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 0))

        ########## Log
        self.log_box = ScrolledText(self, height=8, state="disabled", wrap="word", font=("Consolas", 9))
        self.log_box.grid(row=4, column=0, columnspan=2, sticky="nsew")

        self.toggle_date()

    def build_chapters(self, chapters, selected=None):
        for child in self.chapter_box.winfo_children():
            child.destroy()
        self.chapter_vars = {}
        if not chapters:
            ttk.Label(self.chapter_box, text="Load a question bank to see its chapters.", style="Hint.TLabel").grid(row=0, column=0)
            return
        for i, chapter in enumerate(chapters):
            var = tk.BooleanVar(value=selected is None or chapter in selected)
            var.trace_add("write", lambda *_: self.refresh())
            ttk.Checkbutton(self.chapter_box, text=f"Ch. {chapter}", variable=var).grid(
                row=i // CHAPTERS_PER_ROW, column=i % CHAPTERS_PER_ROW, sticky="w", padx=(0, 10), pady=2)
            self.chapter_vars[chapter] = var

    ################################################################################################
    # Behaviour
    ################################################################################################

    def toggle_date(self):
        self.date_entry.configure(state="disabled" if self.use_today.get() else "normal")

    def select_chapters(self, value):
        for var in self.chapter_vars.values():
            var.set(value)

    def selected_chapters(self):
        return [chapter for chapter, var in self.chapter_vars.items() if var.get()]

    def browse_bank(self):
        current = Path(self.bank_path.get()) if self.bank_path.get() else DEFAULT_BANK
        path = filedialog.askopenfilename(title="Choose the question bank", initialdir=current.parent,
                                          filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if path:
            self.load_bank(path)

    def load_bank(self, path, selected_chapters=None):
        path = Path(path.strip()) if isinstance(path, str) else path
        try:
            bank = core.load_question_bank(path)
        except FileNotFoundError:
            messagebox.showerror("Question bank", f"Could not find the file:\n{path}")
            return
        except Exception as error:
            messagebox.showerror("Question bank", f"Could not read the question bank:\n{error}")
            return

        self.bank = bank
        self.bank_path.set(str(path))
        chapters = sorted(bank.Chapter.unique().tolist())
        types = ", ".join(f"{(bank.Type == t).sum()} {t}" for t in core.QUESTION_TYPES)
        self.bank_info.set(f"{len(bank)} questions ({types}) in {len(chapters)} chapter(s).")
        self.build_chapters(chapters, selected_chapters)
        self.refresh()

    def refresh(self):
        '''Update availability, totals and warnings whenever an input changes.'''
        chapters = self.selected_chapters()
        available = core.topic_availability(self.bank, chapters) if self.bank is not None and chapters else None
        grand_questions, grand_points = 0, 0.0

        for q_type in core.QUESTION_TYPES:
            n_questions = 0
            for difficulty in core.DIFFICULTIES:
                requested = to_int(self.counts[q_type][difficulty].get())
                label = self.available_labels[q_type, difficulty]
                if available is None:
                    label.configure(text="", style="Hint.TLabel")
                else:
                    n_available = available[q_type, difficulty]
                    too_many = requested is not None and requested > n_available
                    label.configure(text=f"{n_available} available", style="Error.TLabel" if too_many else "Hint.TLabel")
                n_questions += max(requested or 0, 0)

            points = to_float(self.points[q_type].get()) or 0.0
            self.question_totals[q_type].configure(text=str(n_questions))
            self.point_totals[q_type].configure(text=core.format_points(n_questions * points))
            grand_questions += n_questions
            grand_points += n_questions * points

        versions = to_int(self.versions.get()) or 0
        self.summary.set(f"Each version: {grand_questions} questions worth {core.format_points(grand_points)} points"
                         f"   ·   {versions} version(s)")

    def read_config(self) -> core.ExamConfig:
        '''Collect the inputs. Raises ValueError naming the first field that is not a valid number.'''
        def number(var, name, convert):
            value = convert(var.get())
            if value is None:
                raise ValueError(f"{name} must be a number.")
            return value

        counts = {t: {d: number(self.counts[t][d], f"{d} {t} questions", to_int) for d in core.DIFFICULTIES}
                  for t in core.QUESTION_TYPES}
        points = {t: number(self.points[t], f"Points per {t} question", to_float) for t in core.QUESTION_TYPES}
        return core.ExamConfig(
            course=self.course.get().strip(),
            semester=self.semester.get().strip(),
            exam_type=self.exam_type.get(),
            duration=number(self.duration, "Duration", to_int),
            exam_date="" if self.use_today.get() else self.exam_date.get().strip(),
            sections=list(dict.fromkeys(self.sections.get().split())),
            versions=number(self.versions, "Versions", to_int),
            chapters=self.selected_chapters(),
            counts=counts,
            points=points,
        )

    def generate(self):
        if self.working:
            return
        if self.bank is None:
            messagebox.showwarning("Generate exams", "Load a question bank first.")
            return
        try:
            config = self.read_config()
        except ValueError as error:
            messagebox.showerror("Generate exams", str(error))
            return
        errors = core.validate(config, self.bank)
        if errors:
            messagebox.showerror("Please fix the following", "\n\n".join("• " + e for e in errors))
            return

        self.save_settings()
        self.set_working(True)
        self.clear_log()
        threading.Thread(target=self.run_generation, args=(config,), daemon=True).start()

    def run_generation(self, config):
        '''Runs in a background thread so the window stays responsive while LaTeX compiles.'''
        try:
            result = core.generate_exams(config, self.bank, log=lambda message: self.messages.put(("log", message)))
            self.messages.put(("done", result))
        except Exception as error:
            self.messages.put(("error", error))

    def poll_messages(self):
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.write_log(payload)
                self.status.set(payload)
            elif kind == "done":
                self.set_working(False)
                self.finished(payload)
            elif kind == "error":
                self.set_working(False)
                self.write_log(f"Error: {payload}")
                self.status.set("Something went wrong. See the messages above.")
                messagebox.showerror("Generate exams", str(payload))
        self.after(100, self.poll_messages)

    def finished(self, result: core.GenerationResult):
        files = "\n".join(f"  • {p.name}" for p in result.pdf_files + [result.answer_key_file])
        note = f"\n\n{len(result.warnings)} warning(s), see the messages in the window." if result.warnings else ""
        self.status.set(f"Created {len(result.pdf_files)} exam PDF(s) and the answer key.")
        if messagebox.askyesno("Exams ready", f"Created:\n{files}{note}\n\nOpen the output folder?"):
            open_path(core.DOC_DIR)

    def set_working(self, working):
        self.working = working
        self.generate_button.configure(state="disabled" if working else "normal")
        if working:
            self.progress.grid()
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def write_log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    ################################################################################################
    # Remembering the last settings
    ################################################################################################

    def save_settings(self):
        settings = {
            "bank_path": self.bank_path.get(),
            "course": self.course.get(), "semester": self.semester.get(), "exam_type": self.exam_type.get(),
            "duration": self.duration.get(), "exam_date": self.exam_date.get(), "use_today": self.use_today.get(),
            "sections": self.sections.get(), "versions": self.versions.get(),
            "chapters": self.selected_chapters(),
            "counts": {t: {d: self.counts[t][d].get() for d in core.DIFFICULTIES} for t in core.QUESTION_TYPES},
            "points": {t: self.points[t].get() for t in core.QUESTION_TYPES},
        }
        try:
            SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        except OSError:
            pass  # not being able to remember settings is not worth interrupting the user for

    def load_settings(self):
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings = {}

        for name in ["course", "semester", "exam_type", "duration", "exam_date", "sections", "versions"]:
            if name in settings:
                getattr(self, name).set(settings[name])
        self.use_today.set(settings.get("use_today", True))
        for t in core.QUESTION_TYPES:
            for d in core.DIFFICULTIES:
                self.counts[t][d].set(settings.get("counts", {}).get(t, {}).get(d, "0"))
            self.points[t].set(settings.get("points", {}).get(t, "1"))
        self.toggle_date()

        bank_path = Path(settings.get("bank_path") or DEFAULT_BANK)
        if bank_path.is_file():
            self.load_bank(bank_path, settings.get("chapters"))
        else:
            self.bank_path.set(str(bank_path))

    def on_close(self):
        if self.working and not messagebox.askyesno("Exam maker", "Exams are still being generated. Quit anyway?"):
            return
        self.save_settings()
        self.root.destroy()


def main():
    if sys.platform == "win32":
        try:  # sharp text on high resolution screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    root.title("Exam Maker")
    root.minsize(820, 720)
    app = ExamMakerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
