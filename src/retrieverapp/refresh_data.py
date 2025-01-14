import argparse
import pandas as pd
import json

# logging functions
import retrieverapp.Logger

def main():
    parser = argparse.ArgumentParser(description='refresh_data.py will apply changes from the sheets_for_editing files to the corresponding JSON_data files')
    parser.add_argument( '-f', dest = "field", type=str, required=True,
                         choices=['data_catalog', 'pub_cite', 'clinical_trials', 'software_catalog', 'dbgap_data'],
                         help='Please provide one of the following options: data_catalog, pub_cite, clinical_trials, software_catalog, or dbgap_data.')
    
    args = parser.parse_args()
    f = args.field

    # logging functions
    logger = logging.getLogger(__name__)
    verbose = 2                           # set this to 3 to show debug info
    logger.setLevel((4-verbose)*10)
    error   = logger.critical        # function alias
    warn    = logger.warning
    debug   = logger.debug
    info    = logger.info

    def update_json_from_excel(file, var):
        df = pd.read_excel('sheets_for_editing/' + file + '.xlsx')
        df = df[df['display'].str.lower() == 'y']
        df = df.drop('display', axis=1)
        df_json = df.to_json(orient='index')
        df_json_dict = json.loads(df_json)
        with open('JSON_data/' + file + '.json', 'w', encoding='utf-8') as f:
            f.write(f'let {var} = ' + json.dumps(df_json_dict) + ';')
            f.close()
        info(f'{file}.json updated to reflect changes to {file}.xlsx')

    if f == 'data_catalog':
        update_json_from_excel(f, 'data_catalog_data')
    elif f == 'pub_cite':
        update_json_from_excel(f, 'pub_cite_data')
    elif f == 'clinical_trials':
        update_json_from_excel(f, 'trials_data')
    elif f == 'software_catalog':
        update_json_from_excel(f, 'github_data')
    elif f == 'dbgap_data':
        update_json_from_excel(f, 'dbgap_data')
    else:
        error('Please provide one of the following options: data_catalog, pub_cite, clinical_trials, software_catalog, or dbgap_data')

    info("All done!")

if __name__ == "__main__":
    main()

