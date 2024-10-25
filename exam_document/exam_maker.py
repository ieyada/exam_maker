
print("This mini-program will generate exam documents using LaTex. Exam questions are based on a dataset of candidate questions that is fed to the program. The user is required to have the question bank in an excel file form, and saved in the same directory where this program lives. The excel file should have the following columns: Question, A, B, C, D, Answer, Type, Chapter, Topic, and Difficulty. The text used for all questions and answers (i.e., columns: Question, A, B, C, and D) should be written in Tex code. It is advised to use the (Exmple_Ques_Bank.xlsx) file as a template for building your question bank.\n\n Version: 2.0 \n Author: Dr. Eyad Alhudhaif\n King Saud University")

print("Loading necessary packages...")

# Loading packages and classes 
from functions.exam_specs import *
from functions.basic import *
from functions.exam_creater import *
from functions.tex_writer import *



####################################################################################################
####################### Program Steps ##############################################################
####################################################################################################

# Create and initialize the input object
data = exam_designer()

def start(data):
    # upload the dataset
    data.input_database()
    # Input Configurations
    data.input_exam_specs()
    # Initiate the output object
    output = exam_maker(data)
    # Compile the questions
    fetched = output.fetch_questions(data)
    # Write the questions and print document
    tex_writer(data, fetched)


start(data)

restart = str(input("Do you wish to redo the process using the same configurations? [y] Yes or [n] No? "))
if restart == 'y':
    # Initiate the output object
    output = exam_maker(data)
    # Compile the questions
    fetched = output.fetch_questions(data)
    # Write the questions and print document
    tex_writer(data, fetched)
elif restart == 'n':
    start_over = str(input("Do you wish to start over with new configurations? [y] Yes or [n] No? "))
    if start_over == 'y':
        start(data)
    elif start_over == 'n':
        end()
    else:
        print("I did not understand your answer. Terminating...")
        end()
else:
    print("I did not understand your answer. Terminating...")
    end()




