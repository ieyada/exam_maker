
from .basic import *

from pylatex.base_classes import Environment, Arguments, Command, Options
from pylatex.package import Package
from pylatex.utils import NoEscape, italic, bold
import pylatex as pl

# Define a custom environment for the raw TeX content
class RawTexEnvironment(Environment):
    def __init__(self, raw_tex):
        super().__init__(arguments=Arguments())
        self.raw_tex = raw_tex

    def dumps(self):
        return self.raw_tex
    

class tex_writer:
    
    '''This class is responsible for writing the exams using LaTex'''


    # initialize the object
    def __init__(self, the_inputs, fetched_ques):

        print("Writing documents...")

        self.config_list = ['smstr', 'course', 'exam', 'duration', 'tfscore', 'mcscore']
        self.line = r"%" * 70
        self.the_inputs_var_name = f'{the_inputs=}'.partition('=')[0]

        for version in fetched_ques:

            doc = pl.Document(documentclass='exam', document_options='addpoints, 12pt', fontenc=None, inputenc = None)

            package_list = ['graphicx', 'soul', 'tikz', 'booktabs', 'color', 'pdfpages','lastpage', 'textcomp', 'lmodern', 'newpxtext', 'newpxmath']

            for package in package_list:
                doc.packages.append(Package(package))

            doc.packages.append((Package("background", options=["pages = some", "placement = center"])))

            
            ############## Setting Macros

            for entry in self.config_list:
                doc.set_variable(entry, (str(eval(self.the_inputs_var_name + "."+ entry)) + " "))

            doc.set_variable("examdate" , NoEscape(the_inputs.examdate))
            doc.set_variable("totalexampoints" , NoEscape(r'\numpoints\ '))
            doc.set_variable("totaltfscore" , fetched_ques[version]['TTF_Score'])
            doc.set_variable("totalmcscore" , fetched_ques[version]['TMC_Score'])
            doc.set_variable("version", version)


            ########### Page Configuration
            doc.variables.append(NoEscape(self.line))
            doc.variables.append(NoEscape(r"% Page Configuration "))
            doc.variables.append(NoEscape(self.line))
            # A package for designing the box in the cover page
            doc.variables.append(Command('usetikzlibrary', "calc"))
            # Have a header and footer

            # Setting the margins
            doc.variables.append(Command('extrawidth', "0.5in"))
            doc.variables.append(Command('extraheadheight', "-0.25in"))
            doc.variables.append(Command('extrafootheight', "-0.25in"))

            ## Header and footer config
            doc.variables.append(NoEscape(r"% Have a header and footer "))
            doc.variables.append(Command('pagestyle', "headandfoot"))
            doc.variables.append(NoEscape(r"% change the ruler in the header "))
            doc.variables.append(Command(command = NoEscape(r"newcommand\HRule"), arguments = NoEscape(r"\rule{\textwidth}{1pt}")))
            doc.variables.append(NoEscape(r"% Set the design for header and footer "))
            doc.variables.append(Command(command = 'header', arguments = NoEscape(r'\course'), extra_arguments=  ["", NoEscape(r"\exam (Continued)")] ))
            doc.variables.append(Command(command = 'headrule'))
            doc.variables.append(Command(command = 'footer', arguments = "", extra_arguments=  [NoEscape(r'\iflastpage{End of exam}{Page \thepage\ of \numpages}'), ""] ))
            doc.variables.append(Command(command = 'footrule'))


            ############# Question Numbering Format
            doc.variables.append(NoEscape(self.line))
            doc.variables.append(NoEscape(r"% Set the label and format for questions, sub-question "))
            doc.variables.append(NoEscape(self.line))
            doc.variables.append(NoEscape(r"% How question labels appear in the exam "))
            doc.variables.append(Command(command = 'renewcommand', arguments = NoEscape(r'\thequestion'), extra_arguments=  NoEscape(r"\Roman{question}") ))
            doc.variables.append(Command(command = 'renewcommand', arguments = NoEscape(r'\questionlabel'), extra_arguments=  NoEscape(r"\textbf{\thequestion)}") ))
            doc.variables.append(Command(command = r'renewcommand\partlabel', arguments = NoEscape(r"\arabic{partno}.")))
            doc.variables.append(NoEscape(r"% How question labels appear in the grading table "))
            doc.variables.append(Command('hqword', "Part"))
            doc.variables.append(Command('hpword', "Grade"))
            doc.variables.append(Command('hsword', "Score"))
            doc.variables.append(Command('htword', "Total"))



            ########### Begin writing the doc
            doc.append(NoEscape("\n"))
            doc.append(NoEscape(self.line))
            doc.append(NoEscape(r"% Exam Cover "))
            doc.append(NoEscape(self.line))


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
            with open(resources_path/"beginning.tex", 'r', encoding="utf-8") as the_file:
                draft = the_file.read()


            # now write that information in the "output" file
            output.write(draft)


            # loop through each question type
            for q_type in fetched_ques[version]:
                # if the question type is either MC or TF start writing the prefex in the latex file to start the category questions 
                if q_type in ['TF', 'MC']:

                    if q_type == 'TF':
                        output.write("\\titledquestion{TF}[\\totaltfscore] \\textit{The following section contains statements, evaluate each statement whether it is true or false. Each evaluation attempt is worth \\tfscore point.}\\\ ")
                        output.write('\n')
                        output.write("\\begin{parts} \n")

                    elif q_type == 'MC':
                        output.write("\\titledquestion{MC}[\\totalmcscore] \\textit{The following section contains multiple choice questions. Please choose the correct (or the closest) choice per question. Each question is worth \\mcscore  point.}\\\ ")
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
                        output.write("\\vspace{0.65cm}\n \n \n")


                    output.write("\\end{parts} \n \\clearpage \n \n ")
                
            # End the question environment
            output.write("\\end{questions} \n ")

            # Add the formula sheet
            output.write("\\begin{center} \n \\LARGE \n \\textsc{\\ul{Formulas}} \n \\end{center} \n")

            
            # close the file
            output.close()


            # open the raw text file
            with open(current_path/file_name, "r") as content:
                raw_tex = content.read()

            # dump the raw tex file to the doc object
            with doc.create(RawTexEnvironment(raw_tex)):
                pass
            

            # Add the each chapter's formulas 
            for chapter in the_inputs.chapters:
                naming = "ch" + str(chapter)+".tex"
                file_location = r"resources/formulas/" + naming
                doc.append(Command('input', NoEscape(file_location)))


            doc.append(Command('clearpage'))

            # if this is a final exam, add the eval form at the end
            if the_inputs.exam == 'Final':
                doc.append(Command('includepdf',
                                   options=Options(NoEscape(r"pages={-}"), NoEscape(r"pagecommand={}")),
                                   arguments = NoEscape(r"resources/eval_form.pdf")))



            file_name = file_name.replace(".tex", "")

            doc.generate_pdf(filepath = current_path/file_name , clean_tex=False, clean= True)


        answer_key(fetched_ques).to_excel(current_path/"answer_key.xlsx", index = False)
        print('Done!!!')
