import pandas as pd, numpy as np

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

