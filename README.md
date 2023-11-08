# retriever_app
Welcome to the retrieverApp! This is an open source tool used for publication progress reporting for large collaboration networks, consortia, and individual investigators alike.

This is a Python based application that will automatically gather data primarily from the [NCBI E-utilites](https://www.ncbi.nlm.nih.gov/books/NBK25497/#chapter2.Usage_Guidelines_and_Requiremen) and generate an html file that summarizes this data. This product exclusively queries publications in the PubMed database and gathers the associated data from GEO, SRA, dbGap, and Clinical Trials databases. 

## How to install:
Clone github files locally: `git clone https://github.com/philippadoherty/retriever_app.git`

Install dependencies using pip: `pip install -r requirements.txt`

Note: We recommend using a venv (current testing is with python version ~3.9)

## Additional setup:
API key:

Using an API key may be necessary for your use case, depending on how many publications and how much data is associated with them. An API key will also speed up the data requests. 

To get a key, go to [NCBI](https://account.ncbi.nlm.nih.gov) to create an account or log in.

Go to [account settings](https://account.ncbi.nlm.nih.gov/settings/), scroll down to API Key Management, copy the key and your email into `constants.py` so `api_key = 'your api key'` and `email = 'your NCBI account email'`


## Usage:
Upload a text file with your list of grants (or edit the sample file: `example_grants.txt`)

Retrieve your data by specifying the text file which contains your grant list: 

`python get_data.py -grants example_grants.txt`

Navigate to the html file, `retriever_app.html`, in a browser.

To edit your data:

Navigate to the `sheets_for_editing` folder, open the excel sheet corresponding to the tabs on the html page. If you would like to change what data is displayed, change the last column, `display`, from `y` to `n`. Save the excel sheet.

To apply these changes run the following command: 

`python refresh_data.py -f file_name` to update the file that has been modified.

`-f` options are `data_catalog`, `pub_cite`, `clinical_trials`, `software_catalog`, or `dbgap_data`. Specify the file name without the extension: `python refresh.py -f data_catalog`


Detailed description and more usage/tips to come ...

tips: 
1. json files are not intended to be directly edited
2. you can edit/ fill in any other columns in the excel sheets and apply those changes.


Explanation of how we gather the data:
1. query PubMed by grant and pull all publications (PubMed IDs) associated with these grants
2. query Entrez elink to find PMID:GEO and PMID:SRA links, query GEO and SRA databases
3. query Entrez elink for PMID:PMCID, query PMC for available text
4. perform regex text searching for potential matches of clinical trials NCTID, dbGap accession number, and github repositories
5. based on potential matches, query clinical trials API, query github API, webscrape dbGap for study meta data




