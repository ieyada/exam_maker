'''A window for designing and generating exams. Start it with:

    python exam_maker_gui.py

It does the same job as the terminal program (exam_maker.py): pick the question bank, fill in the exam
details, choose the chapters and how many questions of each type/difficulty to draw, then press
"Generate exams". The PDFs, .tex files and the answer key are written to this folder.

The window uses ttkbootstrap for its look (pip install ttkbootstrap).'''

import json
import os
import queue
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

try:
    import ttkbootstrap as tb
except ImportError:
    sys.exit("The window needs the ttkbootstrap package. Install it with:  pip install ttkbootstrap")

import exam_core as core

# Remembers what was typed last time, so it does not have to be entered again
SETTINGS_FILE = core.DOC_DIR / "exam_maker_settings.json"
DEFAULT_BANK = core.PROJECT_DIR / "Exmple_Ques_Bank.xlsx"
LIGHT_THEME, DARK_THEME = "bootstrap-light", "bootstrap-dark"
TYPE_LABELS = {"TF": "True / False", "MC": "Multiple choice"}
CHAPTERS_PER_ROW = 7
FONT = "Segoe UI"


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


def year_label(first_year):
    return f"{first_year}-{first_year + 1}"


def open_path(path: Path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


class ExamMakerApp(tb.Frame):

    def __init__(self, root: tb.Window):
        super().__init__(root, padding=(20, 16))
        self.root = root
        self.bank = None
        self.working = False
        self.messages = queue.Queue()      # messages from the generation thread

        this_year = core.current_academic_year()
        self.year_choices = [year_label(y) for y in range(this_year - 2, this_year + 4)]

        self.bank_path = tb.StringVar()
        self.bank_info = tb.StringVar(value="No question bank loaded.")
        self.course = tb.StringVar()
        self.exam_type = tb.StringVar(value="Midterm")
        self.semester = tb.StringVar(value=core.SEMESTERS[0])
        self.academic_year = tb.StringVar(value=year_label(this_year))
        self.duration = tb.StringVar(value="60")
        self.sections = tb.StringVar()
        self.versions = tb.StringVar(value="2")
        self.dark_mode = tb.BooleanVar(value=False)
        self.chapter_vars = {}             # chapter number -> BooleanVar
        self.counts = {t: {d: tb.StringVar(value="0") for d in core.DIFFICULTIES} for t in core.QUESTION_TYPES}
        self.points = {t: tb.StringVar(value="1") for t in core.QUESTION_TYPES}
        self.file_preview = tb.StringVar()
        self.summary = tb.StringVar()
        self.status = tb.StringVar(value="Ready.")

        self.build()
        self.load_settings()
        watched = [self.versions, self.course, self.exam_type, self.semester, self.academic_year,
                   *self.points.values(), *(v for t in self.counts.values() for v in t.values())]
        for var in watched:
            var.trace_add("write", lambda *_: self.refresh())
        self.refresh()
        self.after(100, self.poll_messages)

    ################################################################################################
    # Layout
    ################################################################################################

    def card(self, text, **grid):
        frame = tb.Labelframe(self, text=f" {text} ", padding=(14, 10))
        frame.grid(sticky="nsew", pady=(0, 12), **grid)
        return frame

    def build(self):
        self.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(5, weight=1)

        ########## Header
        header = tb.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        tb.Label(header, text="Exam Maker", font=(FONT, 20, "bold")).grid(row=0, column=0, sticky="w")
        tb.Label(header, text="Draw exam versions from your question bank and build the PDFs and answer key.",
                 bootstyle="secondary").grid(row=1, column=0, sticky="w")
        tb.Checkbutton(header, text="Dark mode", variable=self.dark_mode, bootstyle="toggle",
                       command=self.apply_theme).grid(row=0, column=1, rowspan=2, sticky="e")

        ########## Question bank
        bank = self.card("Question bank", row=1, column=0, columnspan=2)
        bank.columnconfigure(0, weight=1)
        tb.Entry(bank, textvariable=self.bank_path).grid(row=0, column=0, sticky="ew")
        tb.Button(bank, text="Browse…", bootstyle="primary-outline", command=self.browse_bank).grid(row=0, column=1, padx=(8, 0))
        tb.Button(bank, text="Reload", bootstyle="secondary-outline",
                  command=lambda: self.load_bank(self.bank_path.get(), self.selected_chapters())).grid(row=0, column=2, padx=(8, 0))
        tb.Label(bank, textvariable=self.bank_info, bootstyle="secondary").grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ########## Exam details
        details = self.card("Exam details", row=2, column=0, padx=(0, 6))
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)

        def field(row, col, label, widget):
            tb.Label(details, text=label).grid(row=row, column=col, sticky="w", pady=4, padx=(0 if col == 0 else 16, 8))
            widget.grid(row=row, column=col + 1, sticky="ew", pady=4)

        field(0, 0, "Course", tb.Entry(details, textvariable=self.course, width=12))
        field(0, 2, "Exam type", tb.Combobox(details, textvariable=self.exam_type, values=list(core.EXAM_TYPES), state="readonly", width=12))
        field(1, 0, "Semester", tb.Combobox(details, textvariable=self.semester, values=list(core.SEMESTERS), state="readonly", width=12))
        field(1, 2, "Academic year", tb.Combobox(details, textvariable=self.academic_year, values=self.year_choices, state="readonly", width=12))
        self.date_entry = tb.DateEntry(details, date_format="%B %d, %Y", popup_title="Exam date", width=16)
        field(2, 0, "Exam date", self.date_entry)
        field(2, 2, "Duration (min)", tb.Spinbox(details, textvariable=self.duration, from_=1, to=600, increment=5, width=12))
        field(3, 0, "Versions", tb.Spinbox(details, textvariable=self.versions, from_=1, to=core.MAX_VERSIONS, width=12))
        field(3, 2, "Sections", tb.Entry(details, textvariable=self.sections, width=12))
        tb.Label(details, text="Separate sections with spaces", bootstyle="secondary").grid(row=4, column=3, sticky="w")
        tb.Label(details, textvariable=self.file_preview, bootstyle="info").grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

        ########## Chapters
        chapters = self.card("Chapters", row=2, column=1, padx=(6, 0))
        chapters.columnconfigure(0, weight=1)
        self.chapter_box = tb.Frame(chapters)
        self.chapter_box.grid(row=0, column=0, sticky="nw")
        buttons = tb.Frame(chapters)
        buttons.grid(row=1, column=0, sticky="sw", pady=(10, 0))
        tb.Button(buttons, text="Select all", bootstyle="secondary-outline", command=lambda: self.select_chapters(True)).pack(side="left")
        tb.Button(buttons, text="Clear", bootstyle="secondary-outline", command=lambda: self.select_chapters(False)).pack(side="left", padx=(8, 0))
        self.build_chapters([])

        ########## Questions
        questions = self.card("Questions per version", row=3, column=0, columnspan=2)
        headers = ["", *core.DIFFICULTIES, "Questions", "Points each", "Section points"]
        for col, text in enumerate(headers):
            tb.Label(questions, text=text, font=(FONT, 9, "bold")).grid(row=0, column=col, padx=8, pady=(0, 4), sticky="w")
            questions.columnconfigure(col, weight=1)

        self.available_labels = {}
        self.question_totals = {}
        self.point_totals = {}
        for i, q_type in enumerate(core.QUESTION_TYPES):
            row = 1 + 2 * i
            tb.Label(questions, text=TYPE_LABELS[q_type]).grid(row=row, column=0, padx=8, sticky="w")
            for col, difficulty in enumerate(core.DIFFICULTIES, start=1):
                tb.Spinbox(questions, textvariable=self.counts[q_type][difficulty], from_=0, to=999, width=6).grid(row=row, column=col, padx=8, sticky="w")
                label = tb.Label(questions, bootstyle="secondary", font=(FONT, 8))
                label.grid(row=row + 1, column=col, padx=8, sticky="nw", pady=(1, 8))
                self.available_labels[q_type, difficulty] = label
            self.question_totals[q_type] = tb.Label(questions)
            self.question_totals[q_type].grid(row=row, column=4, padx=8, sticky="w")
            tb.Spinbox(questions, textvariable=self.points[q_type], from_=0, to=100, increment=0.5, width=6).grid(row=row, column=5, padx=8, sticky="w")
            self.point_totals[q_type] = tb.Label(questions)
            self.point_totals[q_type].grid(row=row, column=6, padx=8, sticky="w")
        tb.Separator(questions).grid(row=5, column=0, columnspan=7, sticky="ew", pady=(2, 8))
        tb.Label(questions, textvariable=self.summary, font=(FONT, 10, "bold")).grid(row=6, column=0, columnspan=7, sticky="w", padx=8)

        ########## Actions
        actions = tb.Frame(self)
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        actions.columnconfigure(2, weight=1)
        self.generate_button = tb.Button(actions, text="Generate exams", bootstyle="primary", padding=(22, 8), command=self.generate)
        self.generate_button.grid(row=0, column=0, rowspan=2)
        tb.Button(actions, text="Open output folder", bootstyle="secondary-outline", padding=(14, 8),
                  command=lambda: open_path(core.DOC_DIR)).grid(row=0, column=1, rowspan=2, padx=(10, 0))
        self.progress = tb.Progressbar(actions, mode="indeterminate", bootstyle="striped", length=180)
        self.progress.grid(row=0, column=3, sticky="e")
        self.progress.grid_remove()        # only shown while generating
        tb.Label(actions, textvariable=self.status, bootstyle="secondary").grid(row=1, column=2, columnspan=2, sticky="e", pady=(4, 0))

        ########## Log
        self.log_box = tb.ScrolledText(self, height=7, wrap="word", font=("Consolas", 9), auto_hide=True)
        self.log_box.grid(row=5, column=0, columnspan=2, sticky="nsew")
        self.log_box.configure(state="disabled")

    def build_chapters(self, chapters, selected=None):
        for child in self.chapter_box.winfo_children():
            child.destroy()
        self.chapter_vars = {}
        if not chapters:
            tb.Label(self.chapter_box, text="Load a question bank to see its chapters.", bootstyle="secondary").grid(row=0, column=0)
            return
        for i, chapter in enumerate(chapters):
            var = tb.BooleanVar(value=selected is None or chapter in selected)
            var.trace_add("write", lambda *_: self.refresh())
            tb.Checkbutton(self.chapter_box, text=str(chapter), variable=var, bootstyle="primary-outline-toolbutton", width=3).grid(
                row=i // CHAPTERS_PER_ROW, column=i % CHAPTERS_PER_ROW, sticky="w", padx=(0, 6), pady=3)
            self.chapter_vars[chapter] = var

    ################################################################################################
    # Behaviour
    ################################################################################################

    def apply_theme(self):
        self.root.theme_use(DARK_THEME if self.dark_mode.get() else LIGHT_THEME)

    def select_chapters(self, value):
        for var in self.chapter_vars.values():
            var.set(value)

    def selected_chapters(self):
        return [chapter for chapter, var in self.chapter_vars.items() if var.get()]

    def selected_year(self):
        return int(self.academic_year.get()[:4])

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
        self.build_chapters(chapters, selected_chapters or None)
        self.refresh()

    def refresh(self):
        '''Update availability, totals and the file name preview whenever an input changes.'''
        chapters = self.selected_chapters()
        available = core.topic_availability(self.bank, chapters) if self.bank is not None and chapters else None
        grand_questions, grand_points = 0, 0.0

        for q_type in core.QUESTION_TYPES:
            n_questions = 0
            for difficulty in core.DIFFICULTIES:
                requested = to_int(self.counts[q_type][difficulty].get())
                label = self.available_labels[q_type, difficulty]
                if available is None:
                    label.configure(text="", bootstyle="secondary")
                else:
                    n_available = available[q_type, difficulty]
                    too_many = requested is not None and requested > n_available
                    label.configure(text=f"{n_available} available", bootstyle="danger" if too_many else "secondary")
                n_questions += max(requested or 0, 0)

            points = to_float(self.points[q_type].get()) or 0.0
            self.question_totals[q_type].configure(text=str(n_questions))
            self.point_totals[q_type].configure(text=core.format_points(n_questions * points))
            grand_questions += n_questions
            grand_points += n_questions * points

        versions = to_int(self.versions.get()) or 0
        self.summary.set(f"Each version: {grand_questions} questions worth {core.format_points(grand_points)} points"
                         f"   ·   {versions} version(s)")

        preview = core.ExamConfig(course=self.course.get().strip() or "COURSE", exam_type=self.exam_type.get(),
                                  semester=self.semester.get(), academic_year=self.selected_year())
        last = core.VERSION_LETTERS[max(min(versions, core.MAX_VERSIONS), 1) - 1]
        self.file_preview.set(f"Files: {preview.file_stem('A')}.pdf" + (f" … {last}.pdf" if last != "A" else ""))

    def read_config(self) -> core.ExamConfig:
        '''Collect the inputs. Raises ValueError naming the first field that is not valid.'''
        def number(var, name, convert):
            value = convert(var.get())
            if value is None:
                raise ValueError(f"{name} must be a number.")
            return value

        exam_date = self.date_entry.get_date()
        if exam_date is None:
            raise ValueError("Choose the exam date.")
        counts = {t: {d: number(self.counts[t][d], f"{d} {t} questions", to_int) for d in core.DIFFICULTIES}
                  for t in core.QUESTION_TYPES}
        points = {t: number(self.points[t], f"Points per {t} question", to_float) for t in core.QUESTION_TYPES}
        return core.ExamConfig(
            course=self.course.get().strip(),
            semester=self.semester.get(),
            academic_year=self.selected_year(),
            exam_type=self.exam_type.get(),
            duration=number(self.duration, "Duration", to_int),
            exam_date=core.format_date(exam_date),
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

        existing = [core.DOC_DIR / f"{config.file_stem(v)}.pdf" for v in config.version_letters]
        existing = [p.name for p in existing if p.exists()]
        if existing and not messagebox.askyesno(
                "Replace exams?", "These exams already exist and will be replaced:\n\n" + "\n".join(existing) + "\n\nContinue?"):
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
                self.status.set("Something went wrong. See the messages below.")
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
        exam_date = self.date_entry.get_date()
        settings = {
            "bank_path": self.bank_path.get(),
            "course": self.course.get(), "exam_type": self.exam_type.get(),
            "semester": self.semester.get(), "academic_year": self.academic_year.get(),
            "exam_date": exam_date.date().isoformat() if exam_date else "",
            "duration": self.duration.get(), "sections": self.sections.get(), "versions": self.versions.get(),
            "dark_mode": self.dark_mode.get(),
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

        for name in ["course", "exam_type", "duration", "sections", "versions"]:
            if name in settings:
                getattr(self, name).set(settings[name])
        if settings.get("semester") in core.SEMESTERS:
            self.semester.set(settings["semester"])
        if settings.get("academic_year") in self.year_choices:
            self.academic_year.set(settings["academic_year"])
        for t in core.QUESTION_TYPES:
            for d in core.DIFFICULTIES:
                self.counts[t][d].set(settings.get("counts", {}).get(t, {}).get(d, "0"))
            self.points[t].set(settings.get("points", {}).get(t, "1"))

        # an exam date from the past is most likely left over from the previous exam, so start from today
        try:
            saved_date = date.fromisoformat(settings.get("exam_date", ""))
        except ValueError:
            saved_date = None
        self.date_entry.set_date(saved_date if saved_date and saved_date >= date.today() else date.today())

        self.dark_mode.set(settings.get("dark_mode", False))
        self.apply_theme()

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
    root = tb.Window(title="Exam Maker", theme=LIGHT_THEME, minsize=(900, 780))
    app = ExamMakerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
