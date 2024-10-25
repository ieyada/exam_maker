
import pandas as pd
import os
from pathlib import Path

# Set the directory path to the current working directory so it can be the reference point to use. ALWAYS USE '/' FOR THE DIRECTORY REGARDLESS OF THE OPERATING SYSTEM BEING USED. The Path package will take care of it. Note: for Mac users, if there is a space in a folder name, put it in a quote. Example: "Users/user/"+"Google Drive"+"/documents" '''
dir_path = os.path.dirname(os.path.realpath(__file__))
current_path = Path(dir_path).parent
parent_path = current_path.parent
resources_path = Path(current_path/"resources")



####################################################################################################
####################### Functions ##################################################################
####################################################################################################

# Pad any empty cells in a dictionary with a pre-specified value
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






