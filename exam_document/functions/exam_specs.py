from .basic import *

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

