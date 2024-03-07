
print("This mini-program will generate exam documents using LaTex. Exam questions are based on a dataset of candidate questions that is fed to the program. The user is required to have the question bank in an excel file form, and saved in the same directory where this program lives. The excel file should have the following columns: Question, A, B, C, D, Answer, Type, Chapter, Topic, and Difficulty. The text used for all questions and answers (i.e., columns: Question, A, B, C, and D) should be written in Tex code. It is advised to use the (Exmple_Ques_Bank.xlsx) file as a template for building your question bank.\n\n Version: 2.0 \n Author: Dr. Eyad Alhudhaif\n King Saud University")

print("Loading necessary packages...")

# Loading necessary packages
import sys, subprocess

# Check pip and wheel is upgraded and ready to install packages:
#subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'wheel'])
#subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])

#subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'setuptools'])


import os, re, pickle, random, fnmatch, regex, numpy as np, pandas as pd, pylatex as pl, copy
from pathlib import Path
from glob import glob
from itertools import islice
from itertools import cycle
from pandas import DataFrame as df
from pylatex.base_classes import Environment, CommandBase, Arguments, latex_object, Command
from pylatex.package import Package
from pylatex.utils import NoEscape, italic, bold

# Set the current working directory (cwd) of the python file to be the folder where this script exist
#os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Set the directory path to the current working directory so it can be the reference point to use. ALWAYS USE '/' FOR THE DIRECTORY REGARDLESS OF THE OPERATING SYSTEM BEING USED. The Path package will take care of it. Note: for Mac users, if there is a space in a folder name, put it in a quote. Example: "Users/user/"+"Google Drive"+"/documents" '''
dir_path = os.path.dirname(os.path.realpath(__file__))
current_path = Path(dir_path)
parent_path = current_path.parent

print("Done loading packages!!!")

####################################################################################################
####################### Functions ##################################################################
####################################################################################################

# Pad any empty cells in dictionary with a specific value
def pad_dict_list(dict_list, padel):
    lmax = 0
    for lname in dict_list.keys():
        lmax = max(lmax, len(dict_list[lname]))
    for lname in dict_list.keys():
        ll = len(dict_list[lname])
        if  ll < lmax:
            dict_list[lname] += [padel] * (lmax - ll)
    return dict_list




# Print the answer key in an excel file
def answer_key(dictionary):

    answr_key_dict = {}
    for version in dictionary.keys():
        for element in dictionary[version].keys():
            if type(dictionary[version][element]) != str:
                column = version + "_" + element
                answr_key_dict[column] = []
                for ques in dictionary[version][element].keys():
                    answr_key_dict[column].append(dictionary[version][element][ques]['Answer'])


    answr_key_dict = pad_dict_list(answr_key_dict, '')
    df = pd.DataFrame.from_dict(answr_key_dict)

    cols = df.columns.tolist()

    set1 = []
    set2 = []
    for column in cols:
        if column[-2:] == 'TF':
            set1.append(column)
        else:
            set2.append(column)
        
    cols = set1 + set2

    df = df[cols]

    return df


def end():
    print("This program is closing.")
    exit()


####################################################################################################
####################### Classes ####################################################################
####################################################################################################


# Define a custom environment for the raw TeX content
class RawTexEnvironment(Environment):
    def __init__(self, raw_tex):
        super().__init__(arguments=Arguments())
        self.raw_tex = raw_tex

    def dumps(self):
        return self.raw_tex




class exam_designer:
    '''This class is responsible for gather and storing all the information related to designing the exam'''

    # initialize the object
    def __init__(self):
        self.versions_letters_list = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K']

    # function to upload the dataset
    def input_database(self):
        while True:
            try:
                excel_name = (input("Enter the Excel file name for the question bank (without the file extension)") + ".xlsx").replace(" ", "")
                self.question_bank = pd.read_excel(Path(parent_path/excel_name), usecols="A:J")
                print('Question bank uploaded successfully!')
                break;
            
            except FileNotFoundError:
                print("Could not find the file or the file name is misspelled. Please try again")

            except ValueError:
                print("Issue uploading the question bank file. Make sure the structure of the Excel file follows the example template.")  

    # function to add all the attributes for making the exam file
    def input_exam_specs(self):

        # Obtain the number of versions from the user
        while True:
            try:
                self.version_no = abs(int(input("Enter the number of versions to create for this exam: ")))
                break;
            except ValueError:
                print("That is not an integer! Please try again")

        # Choosing the chapters to draw from
        while True:
            try:
                chapters = [int(item) for item in input("Enter the chapter numbers to draw exam questions from (separated by space): ").split()]
                self.chapters = [*set(chapters)]
                break;
            except ValueError:
                print("Issue entering the chapter numbers. Please try again!")


        ########################### TF ###############################
        # How many true/false questions
        while True:
            try:
                self.tf = abs(int(input("Enter the number of true/false questions (TF) to draw for each version of this exam: ")))
                break;
            except ValueError:
                print("That is not an integer! Try again")

        # How many of the true/false questions are difficult questions
        while True:
            try:
                self.tf_h = abs(int(input("How many of these questions will be of difficulty level = High? ")))
                if self.tf_h <= self.tf:
                    break;
                else:
                    print("The number of high level TF questions cannot be more than the total number of TF questions. ") 

            except ValueError:
                print("That is not an integer! Try again")

        # How many of the true/false questions are medium level questions
        while True:
            try:
                self.tf_m = abs(int(input("How many of these questions will be of difficulty level = Medium? ")))
                if (self.tf_m + self.tf_h) <= self.tf :
                    break;
                else:
                    print("Number of (Medium + Difficult) questions to draw cannot exceed the total number of TF questions to draw. ") 
            except ValueError:
                print("That is not an integer! Try again")

        # so the number of easy questions are:
        self.tf_e = self.tf - (self.tf_h + self.tf_m)
        print(f"Thus, the number of easy TF questions to draw for this exam will be {self.tf_e} questions. ") 

        # True/false point per question
        while True:
            try:
                self.tfscore = abs(float(input("How many points to assign for each correct TF question? ")))
                break;
            except ValueError:
                print("Points have to be a real number! Try again")


        ########################### MC ###############################
        # How many multiple choice questions
        while True:
            try:
                self.mc = abs(int(input("Enter the total number of Multiple Choice (MC) questions to draw for each version of this exam: ")))
                break;
            except ValueError:
                print("That is not an integer! Please try again")

        # How many of the multiple choice questions are high difficult questions
        while True:
            try:
                self.mc_h = abs(int(input("How many of these questions will be of difficulty level = High? ")))
                if self.mc_h <= self.mc :
                    break;
                else:
                    print("The number of high level MC questions cannot be more than the total number of MC questions. ")    

            except ValueError:
                print("That is not an integer! Try again")

        # How many of the multiple choice questions are medium difficult questions
        while True:
            try:
                self.mc_m = abs(int(input("How many of these questions will be of difficulty level = Medium? ")))
                if (self.mc_m + self.mc_h) <= self.mc :
                    break;
                else:
                    print("Number of (Medium + Difficult) questions to draw cannot exceed the total number of MC questions to draw. ")      
            except ValueError:
                print("That is not an integer! Try Again")

        # So the number of easy questions are:
        self.mc_e = self.mc - (self.mc_h + self.mc_m)
        print(f"Thus, the number of easy MC questions to draw for this exam will be {self.mc_e} questions. ") 

        # mc point per question
        while True:
            try:
                self.mcscore = abs(float(input("How many points to assign for each correct MC question? ")))
                break;
            except ValueError:
                print("Points have to be a real number! Try again")

        # course number
        self.course = input("Course Number: (Ex. FINA363) ")

        # academic year
        self.smstr = input("Academic Year? (Ex., Fall 2022) ")

        # Exam type
        while True:
            input_exam = input("Exam Type: Midterm[M] or Final[F]? ")
            if input_exam in ['M1', 'Midterm1', 'Midterm 1', 'm1', 'm 1', 'M 1', 'midterm1', 'midterm 1']:
                self.exam = 'Midterm 1'
                break;
            elif input_exam in ['M2', 'Midterm2', 'Midterm 2', 'm2', 'm 2', 'M 2', 'midterm2', 'midterm 2']:
                self.exam = 'Midterm 2'
                break;
            elif input_exam in ['M', 'Midterm', 'm', 'midterm', 'Mid', 'mid']:
                self.exam = 'Midterm'
                break;
            elif input_exam in ['F', 'Final', 'f', 'final']:
                self.exam = 'Final'
                break;
            else:
                print("Choose either M or F. Try again!")

        # duration in minutes
        while True:
            try:
                self.duration = abs(int(input("Exam duration: (in minutes)? ")))
                break;
            except ValueError:
                print("The value has to be an integer! Try again!")

        # exam date
        input_date = input("Exam date? (Ex., September 22, 2019 or Today) ")
        if input_date.lower() == 'today':
            self.examdate = r"\today"
        else:
            self.examdate = input_date




class exam_maker:
    '''This class is responsible for fetching the questions from the dataset'''

    def __init__(self, the_inputs):
        error = "I cannot generate the exam because there is no data input. Please make sure you have uploaded the question bank and set the configurations correctly."
        # Check wether the uploaded object has the attributes nessecery to run this class
        if hasattr(the_inputs, "question_bank") == True and sum([hasattr(the_inputs, x) for x in ["chapters", 'tf', 'mc', 'course']]) == 4:
            pass
            
        else:
            raise AttributeError(error)
        

    def fetch_questions(self, the_inputs):
        print("Fetching questions...")
        # create an empty dictionary to gether all the fetched questions
        self.question_dir = {}

        # mapping the type and number of questions to draw from main dataset
        mapping = { "TF" : {"h": [the_inputs.tf_h, 'Difficult'], "m": [the_inputs.tf_m, 'Medium'], "e": [the_inputs.tf_e, 'Easy']}, "MC" : {"h": [the_inputs.mc_h, 'Difficult'], "m": [the_inputs.mc_m, 'Medium'],"e": [the_inputs.mc_e, 'Easy']}}

        # run a loop to fetch questions for each version, and each question type, and then dump them in the dictionary
        for the_version in the_inputs.versions_letters_list[:the_inputs.version_no]: 
            # Create a sub-dictionary under each version
            self.question_dir[the_version] = {}

            # loop through each question type in the mapping dictionary
            for ques_type in mapping:
                # Create an empty dataset for each question type and name it to use it for compiling the fetched questions
                fetched_ques =  pd.DataFrame(['Empty Entry'], index=[0], columns = ['Topic'], dtype='string')

                for difficulty in mapping[ques_type]:
                    # store the text for the difficulty level 
                    d = mapping[ques_type][difficulty][1]
                    # create a list of all the fetched topics from previous iterations within the same question type
                    f_topics = list(fetched_ques.Topic)

                    # create the question pool to work with in this iteration:
                    ques_pool = the_inputs.question_bank[ (the_inputs.question_bank.Chapter.isin(the_inputs.chapters)) & (the_inputs.question_bank.Difficulty == d) & (the_inputs.question_bank.Type == ques_type) & (~the_inputs.question_bank.Topic.isin(f_topics))]


                    # generate a list of unique topics from this question pool
                    u_topics = ques_pool.dropna(axis = 0, thresh= 4).Topic.unique()

                    # Make sure the conditions are met; the number of unique topics exceeds the number of requested questions, and the number of topics do not equal 0 
                    if len(list(u_topics)) >= mapping[ques_type][difficulty][0] and len(list(u_topics)) != 0 and mapping[ques_type][difficulty][0] > 0:
                        # empty list too add each question entry
                        sample = []
                        # choose a subset of random topics (or questions) to fetch
                        chosen_topics= list(np.random.choice(u_topics, mapping[ques_type][difficulty][0], replace=False))
                        # now loop through each chosen topic and pick a random version of the question
                        for subject in chosen_topics:
                            temp = the_inputs.question_bank[ (the_inputs.question_bank.Chapter.isin(the_inputs.chapters)) & (the_inputs.question_bank.Difficulty == d) & (the_inputs.question_bank.Type == ques_type) & (the_inputs.question_bank.Topic == subject)].sample(n=1)
                            sample.append(temp)
                        
                        # create a dataframe using these chosen questions
                        this_iteration = pd.concat(sample, ignore_index=True)

                        # now dump this dataframe to the main dataframe that collects all the fetched questions of the same type
                        fetched_ques = pd.concat([fetched_ques, this_iteration], ignore_index = True)


                    # If the conditions above are not met, print to the user that the fetching process for the type/difficulty configuration was not successful
                    else:
                        print(f"Did not fetch {str(ques_type)} {d} level questions.")

                #############################################################################
                # dumping the aggregated questions (and total score per type) to the main directory for each version
                
                self.question_dir[the_version][ques_type] = (fetched_ques.reset_index(drop=True)).dropna(axis = 0, thresh= 4).to_dict('index')
                total_score = len(list(self.question_dir[the_version][ques_type].keys()))
                
                self.question_dir[the_version]["T"+ str(ques_type) + "_Score"] = str(int(eval("the_inputs."+ ques_type.lower() + "score") * total_score )) + " "
                
                
            print("Finished fetching questions for version {}.".format(the_version))
     
        print('Done Fetching!!!')
        # Now return the compiled dictionary 
        return self.question_dir




class tex_writer:
    
    '''This class is responsible for writing the exams using LaTex'''


    # initialize the object
    def __init__(self, the_inputs, fetched_ques):

        print("Writing documents...")

        self.config_list = ['smstr', 'course', 'exam', 'duration', 'tfscore', 'mcscore']
        self.line = r"%" * 70
        self.the_inputs_var_name = f'{the_inputs=}'.partition('=')[0]

        for version in fetched_ques:

            doc = pl.Document(documentclass='exam', document_options='addpoints, 11pt', fontenc=None, inputenc = None)

            package_list = ['graphicx', 'soul', 'tikz', 'booktabs', 'color', 'pdfpages','lastpage', 'textcomp', 'lmodern', 'palatino']

            for package in package_list:
                doc.packages.append(Package(package))


            # Replace some text in the tex file with the information about this exam from (the_inputs) object 
            for entry in self.config_list:
                doc.set_variable(entry, (str(eval(self.the_inputs_var_name + "."+ entry)) + " "))

            # Additional Exam Configurations
            doc.set_variable("examdate" , NoEscape(the_inputs.examdate))
            doc.set_variable("totalexampoints" , NoEscape(r'\numpoints\ '))
            doc.set_variable("totaltfscore" , fetched_ques[version]['TTF_Score'])
            doc.set_variable("totalmcscore" , fetched_ques[version]['TMC_Score'])
            doc.set_variable("version", version)


            # Page Configuration
            doc.variables.append(NoEscape(self.line))
            doc.variables.append(NoEscape(r"% Page Configuration"))
            doc.variables.append(Command(command = NoEscape(r"newcommand\HRule"), arguments = NoEscape(r"\rule{\textwidth}{1pt}")))
            doc.variables.append(Command('usetikzlibrary', "calc"))
            doc.variables.append(Command('pagestyle', "headandfoot"))

            # Question Numbering Format
            doc.variables.append(NoEscape(self.line))
            doc.variables.append(NoEscape(r"% Set the format for question and sub-question numbering"))
            doc.variables.append(Command(command = 'renewcommand', arguments = NoEscape(r'\questionlabel'), extra_arguments=  NoEscape(r"\Alph{question}.") ))
            doc.variables.append(Command(command = r'renewcommand\partlabel', arguments = NoEscape(r"\arabic{partno}.")))



            # Exam header and footer configurations
            doc.append(NoEscape(self.line))
            doc.append(NoEscape(r"% Set header and footer"))
            doc.append(Command(command = 'header', arguments = NoEscape(r'\course'), extra_arguments=  ["", NoEscape(r"\exam (Continued)")] ))
            doc.append(Command(command = 'headrule'))
            doc.append(Command(command = 'footer', arguments = "", extra_arguments=  [NoEscape(r'\iflastpage{End of exam}{Page \thepage\ of \numpages}'), ""] ))
            doc.append(Command(command = 'footrule'))

            doc.append(NoEscape("\n"))
            doc.append(NoEscape(self.line))
            doc.append(NoEscape(r"% Exam Cover"))


            # Initiate the tex file for each version
            if the_inputs.exam == 'Midterm 1':
                naming = 'M1'
            elif the_inputs.exam == 'Midterm 2':
                naming = 'M2'
            elif the_inputs.exam == 'Midterm':
                naming = 'M'
            else:
                naming = 'F'

            file_name = the_inputs.course.replace(" ", "") + "_" + naming + "_" + version + ".tex"

            # open a variable so we can add contents to the tex file
            output =  open(current_path/file_name, 'w', encoding="utf-8") 


            # add the content from the tex file named beginning and edit it
            with open(current_path/"tex_parts"/"beginning.tex", 'r', encoding="utf-8") as the_file:
                draft = the_file.read()


            # now write that information in the "output" file
            output.write(draft)


            # loop through each question type
            for q_type in fetched_ques[version]:
                # if the question type is either MC or TF start writing the prefex in the latex file to start the category questions 
                if q_type in ['TF', 'MC']:

                    if q_type == 'TF':
                        output.write("\\question[\\totaltfscore] The following section contains statements, evaluate each statement whether it is true or false. Each evaluation attempt is worth \\tfscore point.\\\ ")
                        output.write('\n')
                        output.write("\\begin{parts} \n")

                    elif q_type == 'MC':
                        output.write("\\question[\\totalmcscore] The following section contains multiple choice questions. Please choose the correct (or the closest) choice per question. Each question is worth \\mcscore  point.\\\ ")
                        output.write('\n')
                        output.write("\\begin{parts} \n \n \n ")

                    for question in fetched_ques[version][q_type]:
                        output.write("\\filbreak \n")
                        output.write("\\part ")
                        output.write(fetched_ques[version][q_type][question]['Question'])
                        output.write("\n \n")
                        if q_type == 'TF':
                            output.write("\\begin{oneparcheckboxes}\n")
                        elif q_type == 'MC':
                            output.write("\\begin{choices}\n")
                        output.write("\\choice ")
                        output.write(fetched_ques[version][q_type][question]['A']+"\n")
                        output.write("\\choice ")
                        output.write(fetched_ques[version][q_type][question]['B']+"\n")
                        if q_type == 'MC':
                            output.write("\\choice ")
                            output.write(fetched_ques[version][q_type][question]['C']+"\n")
                            output.write("\\choice ")
                            output.write(fetched_ques[version][q_type][question]['D']+"\n")
                        output.write('% Key: ')
                        output.write(fetched_ques[version][q_type][question]['Answer']+"\n")
                        output.write('% Topic: ')
                        output.write(fetched_ques[version][q_type][question]['Topic']+"\n")
                        output.write('% Difficulty: ')
                        output.write(fetched_ques[version][q_type][question]['Difficulty']+"\n")
                        if q_type == 'TF':
                            output.write("\\end{oneparcheckboxes}\n")
                        elif q_type == 'MC':
                            output.write("\\end{choices}\n")
                        output.write("\\vspace{0.5cm}\n \n \n")


                    output.write("\\end{parts} \n \\clearpage \n \n ")
                
            # End the question environment
            output.write("\\end{questions} \n ")

            # Add the formula sheet
            output.write("\\begin{center} \n \\LARGE \n \\textsc{\\ul{Formulas}} \n \\end{center}")

            # Add the formulas for each chapter
            for chapter in the_inputs.chapters:
                file = "ch" + str(chapter) +".tex"
                with open(current_path/"tex_parts"/"formulas"/file, 'r', encoding="utf-8") as formula:
                    output.write(formula.read())

            # Add the last part of the document
            output.write("\n \\vspace{1cm} \n \\begin{center} \n \\gradetable[h][questions] \n \\end{center}") 
            
            
            # close the file
            output.close()


            # open the file
            with open(current_path/file_name, "r") as content:
                raw_tex = content.read()


            with doc.create(RawTexEnvironment(raw_tex)):
                pass

            file_name = file_name.replace(".tex", "")

            doc.generate_pdf(filepath = current_path/file_name , clean_tex=False, clean= True)


        answer_key(fetched_ques).to_excel(current_path/"answer_key.xlsx", index = False)
        print('Done!!!')



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




