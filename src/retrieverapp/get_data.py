# get_data.py requires the following inputs:
# -ids filepath/to_your/ids.csv file
# make sure to update the apikey and email in the environment such as:
# export NCBI_API_EMAIL="abc@def.ghi"
# export NCBI_API_KEY="12345"

from retrieverapp.main_functions import pmid_ls_to_pmc_info_df, nctid_ls_to_clinical_trials_df, grant_to_output, scrape_multiple_studies, extract_github_info

import argparse
import os
import pandas as pd
import json

def main():
    parser = argparse.ArgumentParser(description='get_data.py will use your grantlist .txt file as input and will output several JSON and Excel files into the output folder. This will take a while.')
    parser.add_argument('-ids', type=str, help='This should be the path and filename to your ID list: filepath/to_your/ids.txt')
    parser.add_argument('-type', type=str, choices=['pmid', 'grant'], help='This is to specify the ID type, options are pmid or grant')
    parser.add_argument('-update-only', type=str, default=False, help='This option requires you to have output files from a previous run. The input for this will be the path to your sheets_for_editing folder.')
    args = parser.parse_args()
    ids_file = args.ids
    id_type = args.type
    update_only_path = args.update_only
    print(update_only_path)

    if not os.path.isfile(ids_file):
        print(f"Error: The file path '{ids_file}' is not valid or the file does not exist.")
        exit(1)  # Exit the script with a non-zero status code to indicate an error

    ids = []
    with open(ids_file, 'r') as file:
        for line in file:
            # Remove any leading/trailing white spaces
            ids.append(line.strip())

    print(ids)

    if update_only_path: # need to add a few methods here
        if not os.path.isfile(update_only_path+'/sheets_for_editing/pub_cite.xlsx'):
            print(f"Error: The file path '{update_only_path}' is not valid or the file does not exist. Make sure you are pointing to where a 'sheets_for_editing' folder that was generated from a previous 'get_data()' run.")
            exit(1)
        old_pub_cite = pd.read_excel(update_only_path+'/sheets_for_editing/pub_cite.xlsx')
        old_data_catalog = pd.read_excel(update_only_path+'/sheets_for_editing/data_catalog.xlsx')
        old_dbgap = pd.read_excel(update_only_path+'/sheets_for_editing/dbgap_data.xlsx')
        old_clinical_trials = pd.read_excel(update_only_path+'/sheets_for_editing/clinical_trials.xlsx')
        old_software_catalog = pd.read_excel(update_only_path+'/sheets_for_editing/software_catalog.xlsx')

        old_pmids = old_pub_cite['pubMedID']
        #also change options: project name, how can we copy the html file locally? 

    current_directory = os.getcwd()
    json_folder = 'JSON_data'
    json_folder_path = os.path.join(current_directory, json_folder)
    #consider dealing with case where someone wants to generate files for multiple projects
    if not os.path.exists(json_folder_path):
        os.makedirs(json_folder_path)
        print(f"Folder 'JSON_data' created at {json_folder_path}")
    else:
        print(f"Folder 'JSON_data' already exists at {json_folder_path}, consider renaming or moving this?")
    #---------------------------------------------------------------------------------------------------------------------------
    # pull pubmed, icite, SRA, GEO from Entrez
    #---------------------------------------------------------------------------------------------------------------------------
    if update_only_path:
        update_only = old_pmids
    else:
        update_only=False
    pub_cite_df, data_catalog_df = grant_to_output(ids, output_file=json_folder, write=False, id_type=id_type, dbgap_filename=False, update_only=update_only)
    pub_cite_df['display'] = "y"
    data_catalog_df['display'] = "y" 


    excel_folder_path = os.path.join(current_directory, 'sheets_for_editing')
    #consider dealing with case where someone wants to generate files for multiple projects
    if not os.path.exists(excel_folder_path):
        os.makedirs(excel_folder_path)
        print(f"Folder 'sheets_for_editing' created at {excel_folder_path}")
    else:
        print(f"Folder 'sheets_for_editing' already exists at {excel_folder_path}, consider renaming or moving this?")

    #---------------------------------------------------------------------------------------------------------------------------
    # Scrape PMC text for clinical trials IDs, dbgap IDs, github repositories
    #---------------------------------------------------------------------------------------------------------------------------
    #this will create 3 data frames with potential clinical trials, dbgap, and github repos
    nct_pmc_df, gap_pmc_df, git_pmc_df = pmid_ls_to_pmc_info_df(list(pub_cite_df[pub_cite_df['is_research_article'] == 'Yes']['pubMedID'].astype(str)))

    # automatically scrape for dbgap based on potentials
    if not gap_pmc_df.empty:
        dbgap_data = scrape_multiple_studies(gap_pmc_df['dbgap_link'])
        all_dbgap = gap_pmc_df[['pmid', 'pmc_id', 'dbgap', 'pmc_link', 'pubmed_link', 'dbgap_link']].merge(dbgap_data, left_on = 'dbgap_link', right_on = 'url', how = 'left', indicator= True)
        all_dbgap['display'] = "y"
    else: # create an empty dataframe 
        columns=['pmid', 'pmc_id', 'dbgap', 'pmc_link', 'pubmed_link', 'dbgap_link', 'url', 'data_title', 'data_summary', 'library_strategy', 'display']
        data = {column: [None] for column in columns}
        all_dbgap = pd.DataFrame(data, columns=columns)


    # automatically gathers data from clinical trials API (combine NCTs from pubmed data and from text search)
    ncts_pubmed = pub_cite_df[pub_cite_df['clinical_trials']!= ''][['pubMedID', 'clinical_trials']]
    ncts_pubmed.columns = ['pmid', 'nct']
    nct_df = pd.concat([nct_pmc_df[['pmid', 'nct']], ncts_pubmed], axis=0)
    if not nct_df.empty:
        nct_df = nct_df.explode('nct')
        nct_df = nct_df.drop_duplicates()
        try: 
            ct_data = nctid_ls_to_clinical_trials_df(nct_df)
            all_clinical_trials = nct_pmc_df[['pmid', 'pmc_id', 'nct', 'pmc_link', 'pubmed_link', 'ct_link']].merge(ct_data[['nct_id', 'ct_title', 'ct_summary','ct_study_type', 'ct_phase', 'ct_condition', 'ct_intervention', 'ct_intervention_type', 'ct_intervention_name', 'ct_keywords', 'ct_link', 'ct_cancer_types_tagged']], left_on = 'nct', right_on = 'nct_id', how = 'left', indicator= True)
            all_clinical_trials['display'] = "y"
        except:
            nct_df.to_excel('sheets_for_editing/clinical_trials_error.xlsx', index=False)

    else:
        columns=['pmid', 'pmc_id', 'nct', 'pmc_link', 'pubmed_link', 'nct_id', 'ct_title', 'ct_summary','ct_study_type', 'ct_phase', 'ct_condition', 'ct_intervention', 'ct_intervention_type', 'ct_intervention_name', 'ct_keywords', 'ct_link', 'ct_cancer_types_tagged', 'display']
        data = {column: [None] for column in columns}
        all_clinical_trials = pd.DataFrame(data, columns=columns)


    if not git_pmc_df.empty:
        # step wise approach for github/software data:
        git_pmc_df = git_pmc_df.drop_duplicates(subset=['pmid', 'github'])

        try:
            github_data = extract_github_info(git_pmc_df[['pmid', 'github']][0:10]) # try only a sample for show
            github_data['display'] = "y"

        except:
            print('github api query skipped, will need to do manual check and then run software_search.py')

        git_pmc_df['display'] = "y"
        git_pmc_df[['pmid', 'pmc_id', 'github', 'pmc_link', 'pubmed_link', 'display']].to_excel('sheets_for_editing/potential_softwares.xlsx', sheet_name='github', index=False)
    else:
        columns = ['pmid', 'pmc_id', 'github', 'pmc_link', 'pubmed_link','github_link', 'repo_name', 'description', 'license', 'version', 'display']
        data = {column: [None] for column in columns}
        github_data = pd.DataFrame(data, columns=columns)


    #---------------------------------------------------------------------------------------------------------------------------
    # if update-only, write new pub_cite file, but concat all other old and new files to preserve previous edits
    #---------------------------------------------------------------------------------------------------------------------------
    
    #if -update-only, want to preserve previous edits to files (if display was changed etc), but want to update pub_cite because citation counts will change
    if update_only_path:
        data_catalog_df = pd.concat([old_data_catalog, data_catalog_df], ignore_index=True)
        all_dbgap = pd.concat([old_dbgap, all_dbgap], ignore_index=True)
        all_clinical_trials = pd.concat([old_clinical_trials, all_clinical_trials], ignore_index=True)
        github_data = pd.concat([old_software_catalog, github_data], ignore_index=True)


    #---------------------------------------------------------------------------------------------------------------------------
    # Write output files
    #---------------------------------------------------------------------------------------------------------------------------

    # write all outputs to excel
    pub_cite_df.to_excel('sheets_for_editing/pub_cite.xlsx', index=False)
    data_catalog_df.to_excel('sheets_for_editing/data_catalog.xlsx', index=False)
    all_dbgap.to_excel('sheets_for_editing/dbgap_data.xlsx', index=False)
    all_clinical_trials.to_excel('sheets_for_editing/clinical_trials.xlsx', index=False)
    github_data.to_excel('sheets_for_editing/software_catalog.xlsx', index=False)

    # write all files to json
    pub_json = pub_cite_df.to_json(orient='index')
    pub_json_dict = json.loads(pub_json)
    with open(f'{json_folder}/pub_cite.json', 'w', encoding='utf-8') as f:
        f.write('let pub_cite_data = ' + json.dumps(pub_json_dict) + ';')
        f.close()

    data_json = data_catalog_df.to_json(orient='index')
    data_json_dict = json.loads(data_json)
    with open(f'{json_folder}/data_catalog.json', 'w', encoding='utf-8') as f:
        f.write('let data_catalog_data = ' + json.dumps(data_json_dict) + ';')
        f.close()

    dbgap_json = all_dbgap.to_json(orient='index')
    dbgap_json_dict = json.loads(dbgap_json)
    with open(f'{json_folder}/dbgap_data.json', 'w', encoding='utf-8') as f:
        f.write('let dbgap_data = ' + json.dumps(dbgap_json_dict) + ';')
        f.close()

    trials_json = all_clinical_trials.to_json(orient='index')
    trials_json_dict = json.loads(trials_json)
    with open(f'{json_folder}/clinical_trials.json', 'w', encoding='utf-8') as f:
        f.write('let trials_data = ' + json.dumps(trials_json_dict) + ';')
        f.close()

    github_json = github_data.to_json(orient='index')
    github_json_dict = json.loads(github_json)
    with open(f'{json_folder}/software_catalog.json', 'w', encoding='utf-8') as f:
        f.write('let github_data = ' + json.dumps(github_json_dict) + ';')
        f.close()

if __name__ == "__main__":
    main()        
