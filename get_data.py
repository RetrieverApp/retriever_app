# get_data.py requires the following inputs:
# -grants filepath/to_your/grants.csv file
# make sure to update the apikey and email in the environment such as:
# export NCBI_API_EMAIL="abc@def.ghi"
# export NCBI_API_KEY="12345"

from main_functions import pmid_ls_to_pmc_info_df, nctid_ls_to_clinical_trials_df, grant_to_output, scrape_multiple_studies, extract_github_info

import argparse
import os
import pandas as pd
import json

parser = argparse.ArgumentParser(description='get_data.py will use your grantlist .txt file as input and will output several JSON and Excel files into the output folder. This will take a while.')
parser.add_argument('-grants', type=str, help='This should be the path and filename to your grant list: filepath/to_your/grants.txt')
args = parser.parse_args()
grants_file = args.grants

if not os.path.isfile(grants_file):
    print(f"Error: The file path '{grants_file}' is not valid or the file does not exist.")
    exit(1)  # Exit the script with a non-zero status code to indicate an error

grants = []
with open(grants_file, 'r') as file:
    for line in file:
        # Remove any leading/trailing white spaces and add the line to the list
        grants.append(line.strip())

print(grants)

current_directory = os.getcwd()
json_folder = 'JSON_data'
json_folder_path = os.path.join(current_directory, json_folder)
#consider dealing with case where someone wants to generate files for multiple projects
if not os.path.exists(json_folder_path):
    os.makedirs(json_folder_path)
    print(f"Folder 'JSON_data' created at {json_folder_path}")
else:
    print(f"Folder 'JSON_data' already exists at {json_folder_path}, consider renaming or moving this?")


# this will have the pub_cite.json and data_catalog.json as output
pub_cite_df, data_catalog_df = grant_to_output(grants, output_file=json_folder, write=False, id_type='grant_list', dbgap_filename=False)

excel_folder_path = os.path.join(current_directory, 'sheets_for_editing')
#consider dealing with case where someone wants to generate files for multiple projects
if not os.path.exists(excel_folder_path):
    os.makedirs(excel_folder_path)
    print(f"Folder 'sheets_for_editing' created at {excel_folder_path}")
else:
    print(f"Folder 'sheets_fro_editing' already exists at {excel_folder_path}, consider renaming or moving this?")



pub_cite_df['display'] = "y"
data_catalog_df['display'] = "y"
pub_cite_df.to_excel('sheets_for_editing/pub_cite.xlsx', index=False)
data_catalog_df.to_excel('sheets_for_editing/data_catalog.xlsx', index=False)

#print(z)
#this will create 3 data frames with potential clinical trials, dbgap, and github repos
nct_pmc_df, gap_pmc_df, git_pmc_df = pmid_ls_to_pmc_info_df(list(pub_cite_df[pub_cite_df['is_research_article'] == 'Yes']['pubMedID'].astype(str)))

# automatically scrape for dbgap based on potentials
dbgap_data = scrape_multiple_studies(gap_pmc_df['dbgap_link'])

# automatically gathers data from clinical trials API (combine NCTs from pubmed data and from text search)
ncts_pubmed = pub_cite_df[pub_cite_df['clinical_trials']!= ''][['pubMedID', 'clinical_trials']]
ncts_pubmed.columns = ['pmid', 'nct']
nct_df = pd.concat([nct_pmc_df[['pmid', 'nct']], ncts_pubmed], axis=0)
ct_data = nctid_ls_to_clinical_trials_df(nct_df)

# step wise approach for github/software data:
git_pmc_df = git_pmc_df.drop_duplicates(subset=['pmid', 'github'])

try:
    github_data = extract_github_info(git_pmc_df[['pmid', 'github']][0:10]) # try only a sample for show
    github_data['display'] = "y"
    github_data.to_excel('sheets_for_editing/software_catalog.xlsx', index=False)
    github_json = github_data.to_json(orient='index')
    github_json_dict = json.loads(github_json)
    with open(f'{json_folder}/software_catalog.json', 'w', encoding='utf-8') as f:
        f.write('let github_data = ' + json.dumps(github_json_dict) + ';')
        f.close()

except:
    print('github api query skipped, will need to do manual check and then run software_search.py')


all_dbgap = gap_pmc_df[['pmid', 'pmc_id', 'dbgap', 'pmc_link', 'pubmed_link', 'dbgap_link']].merge(dbgap_data, left_on = 'dbgap_link', right_on = 'url', how = 'left', indicator= True)
all_clinical_trials = nct_pmc_df[['pmid', 'pmc_id', 'nct', 'pmc_link', 'pubmed_link', 'ct_link']].merge(ct_data[['nct_id', 'ct_title', 'ct_summary','ct_study_type', 'ct_phase', 'ct_condition', 'ct_intervention', 'ct_intervention_type', 'ct_intervention_name', 'ct_keywords', 'ct_link', 'ct_cancer_types_tagged']], left_on = 'nct', right_on = 'nct_id', how = 'left', indicator= True)

trials_json = all_clinical_trials.to_json(orient='index')
trials_json_dict = json.loads(trials_json)
dbgap_json = all_dbgap.to_json(orient='index')
dbgap_json_dict = json.loads(dbgap_json)

with open(f'{json_folder}/clinical_trials.json', 'w', encoding='utf-8') as f:
    f.write('let trials_data = ' + json.dumps(trials_json_dict) + ';')
    f.close()
with open(f'{json_folder}/dbgap_data.json', 'w', encoding='utf-8') as f:
    f.write('let dbgap_data = ' + json.dumps(dbgap_json_dict) + ';')
    f.close()

# write all the files to excel 
all_clinical_trials['display'] = "y"
all_dbgap['display'] = "y"
git_pmc_df['display'] = "y"
all_clinical_trials.to_excel('sheets_for_editing/clinical_trials.xlsx', index=False)
all_dbgap.to_excel('sheets_for_editing/dbgap_data.xlsx', index=False)
git_pmc_df[['pmid', 'pmc_id', 'github', 'pmc_link', 'pubmed_link', 'display']].to_excel('sheets_for_editing/potential_softwares.xlsx', sheet_name='github')
