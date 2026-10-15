
print("This mini-program will generate exam documents using LaTex. Exam questions are based on a dataset of candidate questions that is fed to the program. The user is required to have the question bank in an excel file form, and saved in the same directory where this program lives. The excel file should have the following columns: Question, A, B, C, D, Answer, Type, Chapter, Topic, and Difficulty. The text used for all questions and answers (i.e., columns: Question, A, B, C, and D) should be written in Tex code. It is advised to use the (Exmple_Ques_Bank.xlsx) file as a template for building your question bank.\n\n Version: 3.0 \n Author: Dr. Eyad Alhudhaif\n King Saud University")
print("Tip: run exam_maker_gui.py for a window where you can fill in all of these settings at once.\n")

print("Loading necessary packages...")
from pathlib import Path

import exam_core as core
print("Done loading packages!!!")


####################################################################################################
####################### Asking for input ###########################################################
####################################################################################################

def ask_number(prompt, convert=int, minimum=0, maximum=None):
    '''Keep asking until the answer is a number between minimum and maximum.'''
    while True:
        try:
            value = convert(input(prompt))
        except ValueError:
            print("That is not a valid number! Please try again")
            continue
        if value < minimum or (maximum is not None and value > maximum):
            print(f"Please enter a number between {minimum} and {maximum}." if maximum is not None
                  else f"Please enter a number of at least {minimum}.")
            continue
        return value


def input_database():
    while True:
        name = input("Enter the Excel file name for the question bank (without the file extension) ").strip()
        path = Path(name if name.lower().endswith((".xlsx", ".xls")) else name + ".xlsx")
        if not path.is_absolute():
            path = core.PROJECT_DIR / path
        try:
            bank = core.load_question_bank(path)
            print('Question bank uploaded successfully!')
            return bank
        except FileNotFoundError:
            print("Could not find the file or the file name is misspelled. Please try again")
        except ValueError as error:
            print(f"Issue uploading the question bank file. {error}")


def input_question_counts(config, q_type, name):
    total = ask_number(f"Enter the number of {name} questions ({q_type}) to draw for each version of this exam: ")
    hard = ask_number("How many of these questions will be of difficulty level = High? ", maximum=total)
    medium = ask_number("How many of these questions will be of difficulty level = Medium? ", maximum=total - hard)
    easy = total - hard - medium
    print(f"Thus, the number of easy {q_type} questions to draw for this exam will be {easy} questions. ")
    config.counts[q_type] = {"Difficult": hard, "Medium": medium, "Easy": easy}
    config.points[q_type] = ask_number(f"How many points to assign for each correct {q_type} question? ", float)


def input_exam_type():
    aliases = {"m1": "Midterm 1", "midterm1": "Midterm 1", "m2": "Midterm 2", "midterm2": "Midterm 2",
               "m": "Midterm", "mid": "Midterm", "midterm": "Midterm", "f": "Final", "final": "Final"}
    while True:
        answer = input("Exam Type: Midterm[M], Midterm 1[M1], Midterm 2[M2] or Final[F]? ").replace(" ", "").lower()
        if answer in aliases:
            return aliases[answer]
        print("Choose either M, M1, M2 or F. Try again!")


def input_exam_specs(bank):
    config = core.ExamConfig()
    config.sections = list(dict.fromkeys(input("Enter sections for this exam (Separated by space): ").split()))
    config.versions = ask_number("Enter the number of versions to create for this exam: ", minimum=1, maximum=core.MAX_VERSIONS)

    available = sorted(bank.Chapter.unique().tolist())
    while True:
        try:
            chapters = [int(item) for item in input(f"Enter the chapter numbers to draw exam questions from (separated by space). Available: {' '.join(map(str, available))} ").split()]
        except ValueError:
            print("Issue entering the chapter numbers. Please try again!")
            continue
        if chapters:
            config.chapters = sorted(set(chapters))
            break
        print("Enter at least one chapter.")

    input_question_counts(config, "TF", "true/false")
    input_question_counts(config, "MC", "Multiple Choice")

    config.course = input("Course Number: (Ex. FINA363) ").strip()
    while True:
        semester = input(f"Semester? ({', '.join(core.SEMESTERS)}) ").strip().capitalize()
        if semester in core.SEMESTERS:
            config.semester = semester
            break
        print(f"Choose one of: {', '.join(core.SEMESTERS)}. Try again!")
    default_year = core.current_academic_year()
    year = input(f"First year of the academic year? (Ex., {default_year} for {default_year}-{default_year + 1}; press Enter for {default_year}) ").strip()
    while year and not (year.isdigit() and len(year) == 4):
        year = input("Please enter a 4-digit year (Ex., 2026) or press Enter: ").strip()
    config.academic_year = int(year) if year else default_year
    config.exam_type = input_exam_type()
    config.duration = ask_number("Exam duration: (in minutes)? ", minimum=1)
    date = input("Exam date? (Ex., September 22, 2019 or Today) ").strip()
    config.exam_date = "" if date.lower() in ("", "today") else date
    return config


####################################################################################################
####################### Program Steps ##############################################################
####################################################################################################

def make_exams(config, bank):
    '''Generate the exams. Returns False if the configuration has problems that need new input.'''
    errors = core.validate(config, bank)
    if errors:
        print("\nThe exams cannot be generated with these settings:")
        for error in errors:
            print(" - " + error)
        return False
    core.generate_exams(config, bank)
    return True


def main():
    bank = input_database()
    config = input_exam_specs(bank)
    ok = make_exams(config, bank)

    while True:
        if ok:
            answer = input("Do you wish to redo the process using the same configurations? [y] Yes or [n] No? ").strip().lower()
            if answer == 'y':
                ok = make_exams(config, bank)
                continue
        answer = input("Do you wish to start over with new configurations? [y] Yes or [n] No? ").strip().lower()
        if answer == 'y':
            config = input_exam_specs(bank)
            ok = make_exams(config, bank)
        else:
            print("This program is closing.")
            return


if __name__ == "__main__":
    main()
