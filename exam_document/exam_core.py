'''Core logic of the exam maker: load the question bank, draw questions for each version,
write the LaTeX documents, compile them and export the answer key.

Nothing in this module asks the user for input, so both the terminal program (exam_maker.py)
and the window (exam_maker_gui.py) share it.'''

from __future__ import annotations

import csv
import os
import shutil
import string
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pylatex as pl
from pylatex.base_classes import Command, Options
from pylatex.package import Package
from pylatex.utils import NoEscape, escape_latex


####################################################################################################
####################### Constants ##################################################################
####################################################################################################

# All paths are relative to this file, so the program works no matter where it is launched from
DOC_DIR = Path(__file__).resolve().parent          # where the .tex/.pdf files are written
PROJECT_DIR = DOC_DIR.parent                       # where the question bank usually lives
RESOURCES_DIR = DOC_DIR / "resources"
FORMULAS_DIR = RESOURCES_DIR / "formulas"

QUESTION_TYPES = ("TF", "MC")
# The order matters: the hardest (usually scarcest) questions are drawn first
DIFFICULTIES = ("Difficult", "Medium", "Easy")
REQUIRED_COLUMNS = ["Question", "A", "B", "C", "D", "Answer", "Type", "Chapter", "Topic", "Difficulty"]
TEXT_COLUMNS = ["Question", "A", "B", "C", "D", "Answer", "Topic"]

# Exam name -> short code used in the file names
EXAM_TYPES = {"Midterm": "M", "Midterm 1": "M1", "Midterm 2": "M2", "Final": "F"}
VERSION_LETTERS = string.ascii_uppercase
MAX_VERSIONS = len(VERSION_LETTERS)

PACKAGES = ['graphicx', 'soul', 'tikz', 'booktabs', 'color', 'pdfpages', 'lastpage', 'textcomp',
            'lmodern', 'newpxtext', 'newpxmath', 'longtable', 'csvsimple']
LINE = "%" * 70

# Files LaTeX leaves behind that are not needed once the PDF exists
AUX_EXTENSIONS = (".aux", ".log", ".fls", ".fdb_latexmk", ".out", ".synctex.gz")

# Do not flash a console window for every LaTeX run when started from the window
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


####################################################################################################
####################### Configuration ##############################################################
####################################################################################################

def format_points(value: float) -> str:
    '''1.0 -> "1", 0.5 -> "0.5", 2.25 -> "2.25"'''
    return f"{value:g}"


def is_whole_or_half(value: float) -> bool:
    return abs(value * 2 - round(value * 2)) < 1e-9


def exam_points(value: float) -> str:
    '''Point values for the exam class, which only accepts whole and half points: 2.5 -> 2\\half'''
    whole = int(round(value * 2)) // 2
    if not round(value * 2) % 2:
        return str(whole)
    return (str(whole) if whole else "") + r"\half"


@dataclass
class ExamConfig:
    '''Everything needed to design an exam.'''
    course: str = ""
    semester: str = ""
    exam_type: str = "Midterm"
    duration: int = 60
    exam_date: str = ""               # empty means \today
    sections: list = field(default_factory=list)
    versions: int = 1
    chapters: list = field(default_factory=list)
    # number of questions to draw per type and difficulty, e.g. counts["TF"]["Easy"] = 2
    counts: dict = field(default_factory=lambda: {t: {d: 0 for d in DIFFICULTIES} for t in QUESTION_TYPES})
    # points per correct question, per type
    points: dict = field(default_factory=lambda: {t: 1.0 for t in QUESTION_TYPES})

    def total(self, q_type: str) -> int:
        return sum(self.counts[q_type].values())

    @property
    def exam_code(self) -> str:
        return EXAM_TYPES[self.exam_type]

    @property
    def version_letters(self) -> str:
        return VERSION_LETTERS[:self.versions]

    def file_stem(self, version: str) -> str:
        return f"{self.course.replace(' ', '')}_{self.exam_code}_{version}"

    @property
    def answer_key_name(self) -> str:
        return f"{self.course.replace(' ', '')}_{self.exam_code}_answer_key.xlsx"


####################################################################################################
####################### Question bank ##############################################################
####################################################################################################

def load_question_bank(path) -> pd.DataFrame:
    '''Read and tidy up the question bank Excel file. Raises ValueError if its structure is wrong.'''
    bank = pd.read_excel(path, usecols="A:J")

    missing = [col for col in REQUIRED_COLUMNS if col not in bank.columns]
    if missing:
        raise ValueError(f"The question bank is missing the column(s): {', '.join(missing)}. "
                         "Use Exmple_Ques_Bank.xlsx as a template.")

    # Drop empty rows, then normalise the text so small typos ("tf", "easy ") do not lose questions
    bank = bank[REQUIRED_COLUMNS].dropna(subset=["Question", "Answer", "Type", "Chapter", "Topic", "Difficulty"])
    try:
        bank["Chapter"] = bank["Chapter"].astype(int)
    except ValueError:
        raise ValueError("The Chapter column must only contain whole numbers.") from None
    for col in TEXT_COLUMNS:
        bank[col] = bank[col].fillna("").astype(str).str.strip()
    bank["Type"] = bank["Type"].astype(str).str.strip().str.upper()
    bank["Difficulty"] = bank["Difficulty"].astype(str).str.strip().str.capitalize()

    return bank.reset_index(drop=True)


def topic_availability(bank: pd.DataFrame, chapters) -> dict:
    '''Number of distinct topics available for each (type, difficulty) within the given chapters.
    Each drawn question comes from a different topic, so this is the most that can be requested.'''
    pool = bank[bank.Chapter.isin(list(chapters))]
    counts = pool.groupby(["Type", "Difficulty"]).Topic.nunique()
    return {(t, d): int(counts.get((t, d), 0)) for t in QUESTION_TYPES for d in DIFFICULTIES}


def validate(config: ExamConfig, bank: pd.DataFrame) -> list:
    '''Return a list of problems with the configuration (empty if everything is fine).'''
    errors = []
    if not config.course.strip():
        errors.append("Enter the course name/number.")
    if config.exam_type not in EXAM_TYPES:
        errors.append(f"Exam type must be one of: {', '.join(EXAM_TYPES)}.")
    if not 1 <= config.versions <= MAX_VERSIONS:
        errors.append(f"The number of versions must be between 1 and {MAX_VERSIONS}.")
    if config.duration <= 0:
        errors.append("The exam duration must be a positive number of minutes.")
    if not config.chapters:
        errors.append("Select at least one chapter.")
    if sum(config.total(t) for t in QUESTION_TYPES) == 0:
        errors.append("Request at least one question.")
    for q_type in QUESTION_TYPES:
        if config.points[q_type] < 0:
            errors.append(f"Points per {q_type} question cannot be negative.")
        if any(n < 0 for n in config.counts[q_type].values()):
            errors.append(f"Number of {q_type} questions cannot be negative.")
        section_total = config.total(q_type) * config.points[q_type]
        if not is_whole_or_half(section_total):
            errors.append(f"The {q_type} section would be worth {format_points(section_total)} points; the LaTeX "
                          "exam class only supports whole or half points per section (e.g. 5 or 2.5).")

    if config.chapters:
        available = topic_availability(bank, config.chapters)
        for (q_type, difficulty), n_available in available.items():
            requested = config.counts[q_type][difficulty]
            if requested > n_available:
                errors.append(f"{requested} {difficulty} {q_type} question(s) requested, but the selected "
                              f"chapters only have {n_available} distinct topic(s) at that level.")
    return errors


####################################################################################################
####################### Drawing questions ##########################################################
####################################################################################################

def draw_version(config: ExamConfig, bank: pd.DataFrame, rng: np.random.Generator) -> dict:
    '''Draw the questions of one exam version: {"TF": DataFrame, "MC": DataFrame}.
    Within a question type every question comes from a different topic.'''
    pool = bank[bank.Chapter.isin(config.chapters)]
    drawn = {}

    for q_type in QUESTION_TYPES:
        type_pool = pool[pool.Type == q_type]
        used_topics = set()
        picks = []

        for difficulty in DIFFICULTIES:
            n = config.counts[q_type][difficulty]
            if n == 0:
                continue
            candidates = type_pool[(type_pool.Difficulty == difficulty) & ~type_pool.Topic.isin(used_topics)]
            topics = candidates.Topic.unique()
            if len(topics) < n:
                raise ValueError(f"Not enough {difficulty} {q_type} topics left to draw {n} question(s) "
                                 f"(only {len(topics)} not already used by another difficulty level).")

            # choose the topics, then one random question for each chosen topic
            chosen = rng.choice(topics, n, replace=False)
            picks.append(candidates[candidates.Topic.isin(chosen)].groupby("Topic").sample(n=1, random_state=rng))
            used_topics.update(chosen)

        questions = pd.concat(picks) if picks else type_pool.iloc[0:0]
        # shuffle so difficulty levels are mixed in the exam
        drawn[q_type] = questions.sample(frac=1, random_state=rng).reset_index(drop=True)

    return drawn


def answer_key(exams: dict) -> pd.DataFrame:
    '''One column per version and type (all TF columns first, then MC), padded with blanks.'''
    columns = {f"{version}_{q_type}": pd.Series(list(exams[version][q_type].Answer), dtype=object)
               for q_type in QUESTION_TYPES for version in exams}
    return pd.DataFrame(columns).fillna("")


####################################################################################################
####################### Writing LaTeX ##############################################################
####################################################################################################

SECTION_INTRO = {
    "TF": r"\titledquestion{TF}[\totaltfscore] \textit{The following section contains statements, evaluate each "
          r"statement whether it is true or false. Each evaluation attempt is worth \tfscore point.}\\",
    "MC": r"\titledquestion{MC}[\totalmcscore] \textit{The following section contains multiple choice questions. "
          r"Please choose the correct (or the closest) choice per question. Each question is worth \mcscore  point.}\\",
}
CHOICE_ENV = {"TF": "oneparcheckboxes", "MC": "choices"}
CHOICE_COLUMNS = {"TF": ["A", "B"], "MC": ["A", "B", "C", "D"]}

FINAL_MESSAGE = [
    r"\vfill \begin{center} \textsc{\Large End of Exam} \end{center}",
    r"\setlength{\parindent}{0pt}",
    r"Congratulations on completing your final exam! I know how much effort and dedication you have put into your "
    r"studies, and I am proud of each of you for making it to this point. No matter how you feel about your "
    r"performance today, remember that \textit{learning is a journey, and every success and challenge alike helps "
    r"you grow}.\\",
    r"Thank you for your hard work, your curiosity, and your perseverance throughout the course. I wish you all the "
    r"best in your next endeavors. Keep learning, keep asking questions, and most importantly, believe in "
    r"yourself \dots \\",
    r"PS: \textit{Don't forget to fill out the form next page} :)",
]


def questions_tex(questions: dict) -> str:
    '''The body of the exam: the cover page followed by one titled question per question type.'''
    parts = [(RESOURCES_DIR / "beginning.tex").read_text(encoding="utf-8")]

    for q_type in QUESTION_TYPES:
        table = questions[q_type]
        if table.empty:
            continue
        parts.append(" " + SECTION_INTRO[q_type] + " \n\\begin{parts} \n")
        for q in table.itertuples(index=False):
            parts.append("\\filbreak \n\\part " + q.Question + "\n \n")
            parts.append(f"\\begin{{{CHOICE_ENV[q_type]}}}\n")
            for col in CHOICE_COLUMNS[q_type]:
                parts.append("\\choice " + getattr(q, col) + "\n")
            parts.append(f"% Key: {q.Answer}\n% Topic: {q.Topic}\n% Difficulty: {q.Difficulty}\n")
            parts.append(f"\\end{{{CHOICE_ENV[q_type]}}}\n \n")
        parts.append("\\end{parts} \n \\clearpage \n \n ")

    parts.append("\\end{questions} \n ")
    return "".join(parts)


def formula_files(chapters) -> list:
    '''Formula files of the selected chapters that exist and are not empty.'''
    files = [FORMULAS_DIR / f"ch{chapter}.tex" for chapter in sorted(chapters)]
    return [f for f in files if f.is_file() and f.stat().st_size > 0]


def build_document(config: ExamConfig, version: str, questions: dict) -> pl.Document:
    doc = pl.Document(documentclass='exam', document_options='addpoints, 12pt', fontenc=None, inputenc=None)

    for package in PACKAGES:
        doc.packages.append(Package(package))
    doc.packages.append(Package("background", options=["pages = some", "placement = center"]))

    ############## Setting Macros (the trailing space keeps a space after the macro in the text)
    total_points = {t: config.total(t) * config.points[t] for t in QUESTION_TYPES}
    doc.set_variable("smstr", config.semester + " ")
    doc.set_variable("course", config.course + " ")
    doc.set_variable("exam", config.exam_type + " ")
    doc.set_variable("duration", f"{config.duration} ")
    doc.set_variable("tfscore", format_points(config.points["TF"]) + " ")
    doc.set_variable("mcscore", format_points(config.points["MC"]) + " ")
    doc.set_variable("examdate", NoEscape(escape_latex(config.exam_date) if config.exam_date.strip() else r"\today"))
    doc.set_variable("totalexampoints", NoEscape(r'\numpoints\ '))
    doc.set_variable("totaltfscore", NoEscape(exam_points(total_points["TF"]) + " "))
    doc.set_variable("totalmcscore", NoEscape(exam_points(total_points["MC"]) + " "))
    doc.set_variable("version", version)

    ########### Page Configuration
    doc.variables.append(NoEscape(LINE))
    doc.variables.append(NoEscape(r"% Page Configuration "))
    doc.variables.append(NoEscape(LINE))
    # A package for designing the box in the cover page
    doc.variables.append(Command('usetikzlibrary', "calc"))
    # Setting the margins
    doc.variables.append(Command('extrawidth', "0.5in"))
    doc.variables.append(Command('extraheadheight', "-0.25in"))
    doc.variables.append(Command('extrafootheight', "-0.25in"))

    ## Header and footer config
    doc.variables.append(NoEscape(r"% Have a header and footer "))
    doc.variables.append(Command('pagestyle', "headandfoot"))
    doc.variables.append(NoEscape(r"% change the ruler in the header "))
    doc.variables.append(Command(command=NoEscape(r"newcommand\HRule"), arguments=NoEscape(r"\rule{\textwidth}{1pt}")))
    doc.variables.append(NoEscape(r"% Set the design for header and footer "))
    doc.variables.append(Command(command='header', arguments=NoEscape(r'\course'),
                                 extra_arguments=[NoEscape(r"Version: \version"), NoEscape(r"\exam (Continued)")]))
    doc.variables.append(Command(command='headrule'))
    doc.variables.append(Command(command='footer', arguments="",
                                 extra_arguments=[NoEscape(r'\iflastpage{End of exam}{Page \thepage\ of \numpages}'), ""]))
    doc.variables.append(Command(command='footrule'))

    ############# Question Numbering Format
    doc.variables.append(NoEscape(LINE))
    doc.variables.append(NoEscape(r"% Set the label and format for questions, sub-question "))
    doc.variables.append(NoEscape(LINE))
    doc.variables.append(NoEscape(r"% How question labels appear in the exam "))
    doc.variables.append(Command(command='renewcommand', arguments=NoEscape(r'\thequestion'), extra_arguments=NoEscape(r"\Roman{question}")))
    doc.variables.append(Command(command='renewcommand', arguments=NoEscape(r'\questionlabel'), extra_arguments=NoEscape(r"\textbf{\thequestion)}")))
    doc.variables.append(Command(command=r'renewcommand\partlabel', arguments=NoEscape(r"\arabic{partno}.")))
    doc.variables.append(NoEscape(r"% How question labels appear in the grading table "))
    doc.variables.append(Command('hqword', "Part"))
    doc.variables.append(Command('hpword', "Grade"))
    doc.variables.append(Command('hsword', "Score"))
    doc.variables.append(Command('htword', "Total"))

    ########### Begin writing the doc
    doc.append(NoEscape("\n" + LINE + "\n% Exam Cover \n" + LINE))
    doc.append(NoEscape(questions_tex(questions)))

    ##### Formula sheet. The formula files hold display math ($$...$$), which cannot sit inside table
    ##### cells, so they are placed on their own page(s) under a heading.
    formulas = formula_files(config.chapters)
    if formulas:
        doc.append(NoEscape(r"\newpage"))
        doc.append(NoEscape(r"\begin{center} \LARGE \textsc{\ul{Formulas}} \end{center}"))
        for file in formulas:
            doc.append(Command('input', NoEscape(file.relative_to(DOC_DIR).as_posix())))

    # if this is a final exam, add the eval form at the end
    if config.exam_type == 'Final':
        for line in FINAL_MESSAGE:
            doc.append(NoEscape(line))
        doc.append(Command('clearpage'))
        doc.append(Command('includepdf', options=Options(NoEscape(r"pages={-}"), NoEscape(r"pagecommand={}")),
                           arguments=NoEscape(r"resources/eval_form.pdf")))
    else:
        doc.append(Command('clearpage'))

    return doc


####################################################################################################
####################### Compiling ##################################################################
####################################################################################################

def first_latex_errors(log_file: Path, limit: int = 3) -> str:
    '''The first few "! ..." error lines of a LaTeX log, with the source line that caused them.'''
    if not log_file.is_file():
        return ""
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    errors = []
    for i, line in enumerate(lines):
        if line.startswith("! "):
            source = next((l for l in lines[i + 1:i + 6] if l.startswith("l.")), "")
            errors.append(f"{line[2:]}  {source}".strip())
            if len(errors) == limit:
                break
    return "\n".join(errors)


def compile_pdf(tex_file: Path) -> str:
    '''Compile a .tex file into a PDF next to it. latexmk reruns LaTeX as many times as needed for the
    grading table and page numbers; without it pdflatex is run three times.
    Returns a warning message ("" if none). Raises RuntimeError if no PDF could be produced.'''
    folder, stem = tex_file.parent, tex_file.stem
    pdf_file = folder / f"{stem}.pdf"
    started = pdf_file.stat().st_mtime if pdf_file.exists() else None

    if shutil.which("latexmk"):
        commands = [["latexmk", "-pdf", "-interaction=nonstopmode", tex_file.name]]
    elif shutil.which("pdflatex"):
        commands = [["pdflatex", "-interaction=nonstopmode", tex_file.name]] * 3
    else:
        raise RuntimeError("Could not find latexmk or pdflatex. Install a LaTeX distribution (TeX Live or MiKTeX).")

    failed = False
    for command in commands:
        result = subprocess.run(command, cwd=folder, capture_output=True, creationflags=NO_WINDOW)
        failed = failed or result.returncode != 0

    produced = pdf_file.exists() and pdf_file.stat().st_mtime != started
    if not produced:
        raise RuntimeError(f"LaTeX could not produce {pdf_file.name}. See {stem}.log.\n"
                           + first_latex_errors(folder / f"{stem}.log"))
    if failed:
        # LaTeX recovered from the errors and still made a PDF; keep the log so they can be fixed
        return (f"{pdf_file.name} was created, but LaTeX reported errors (details in {stem}.log):\n"
                + first_latex_errors(folder / f"{stem}.log"))

    for ext in AUX_EXTENSIONS:
        (folder / f"{stem}{ext}").unlink(missing_ok=True)
    return ""


####################################################################################################
####################### Whole process ##############################################################
####################################################################################################

@dataclass
class GenerationResult:
    pdf_files: list
    answer_key_file: Path
    warnings: list


def generate_exams(config: ExamConfig, bank: pd.DataFrame, log=print, seed=None) -> GenerationResult:
    '''Draw the questions, then write and compile every version and the answer key.
    `log` receives progress messages. Raises ValueError for an invalid configuration.'''
    errors = validate(config, bank)
    if errors:
        raise ValueError("\n".join(errors))

    rng = np.random.default_rng(seed)
    warnings = []

    log("Fetching questions...")
    exams = {version: draw_version(config, bank, rng) for version in config.version_letters}

    missing = [c for c in sorted(config.chapters) if not (FORMULAS_DIR / f"ch{c}.tex").is_file()]
    if missing:
        warnings.append(f"No formula file for chapter(s) {', '.join(map(str, missing))} "
                        f"(expected resources/formulas/ch<N>.tex); they are left out of the formula sheet.")

    # list of sections, one per line
    with open(DOC_DIR / "sections.csv", "w", newline="") as csv_file:
        csv.writer(csv_file).writerows([section] for section in config.sections)

    key_file = DOC_DIR / config.answer_key_name
    answer_key(exams).to_excel(key_file, index=False)
    log(f"Answer key saved: {key_file.name}")

    log("Writing documents...")
    tex_files = []
    for version, questions in exams.items():
        tex_file = DOC_DIR / f"{config.file_stem(version)}.tex"
        tex_file.write_text(build_document(config, version, questions).dumps(), encoding="utf-8")
        tex_files.append(tex_file)

    # Compiling is by far the slowest step, so the versions are compiled side by side
    log(f"Compiling {len(tex_files)} PDF(s) with LaTeX. This can take a little while...")
    pdf_files = []
    with ThreadPoolExecutor(max_workers=min(len(tex_files), os.cpu_count() or 2, 4)) as pool:
        jobs = {pool.submit(compile_pdf, tex_file): tex_file for tex_file in tex_files}
        for job in as_completed(jobs):
            tex_file = jobs[job]
            warning = job.result()
            if warning:
                warnings.append(warning)
            pdf_files.append(tex_file.with_suffix(".pdf"))
            log(f"Created {tex_file.stem}.pdf")

    for warning in warnings:
        log("Warning: " + warning)
    log("Done!")
    return GenerationResult(sorted(pdf_files), key_file, warnings)
