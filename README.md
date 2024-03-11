# retriever_app
Welcome to the retrieverApp! This is an open source tool used for publication progress reporting for large collaboration networks, consortia, and individual investigators alike.

This is a Python based application that will automatically gather data primarily from the [NCBI E-utilites](https://www.ncbi.nlm.nih.gov/books/NBK25497/#chapter2.Usage_Guidelines_and_Requiremen) and generate an html file that summarizes this data. This product exclusively queries publications in the PubMed database and gathers the associated data from GEO, SRA, dbGap, and Clinical Trials databases. 

## How to install:
Clone github files locally: `git clone
https://github.com/philippadoherty/retriever_app.git` and change
working directory: `cd retriever_app`.

Install dependencies using pip: `pip install .`

After installation, you should be able to access two command line
tools -- `retriever_get` and `retriever_refresh`.

Note: We recommend using a venv (current testing is with python version ~3.9)

## Additional setup:
In order to use this application you must have an NCBI API Key, which you can get by creating a FREE NCBI account.

To get a key, go to [NCBI](https://account.ncbi.nlm.nih.gov) to create an account or log in.

Go to [account settings](https://account.ncbi.nlm.nih.gov/settings/),
scroll down to API Key Management to get your key.

Run the following commands to store your variables:
```
$ export NCBI_API_EMAIL=your_email@example.com
$ export NCBI_API_KEY=your_api_key_here
```

## Usage:
1. Go to your working directory, and create a text file with your list of grants (or edit the sample file: `example_grants.txt`)

2. Run the following command to retrieve your data by simply specifying the text file that contains your grant list.

```
$ retriever_get -grants example_grants.txt
```

3. Navigate to the html file, `retriever_app.html`, in a browser to see the data summaries and tables.

### To edit your data:

1. Edit the excel files: Navigate to the `sheets_for_editing` folder, edit the excel sheet corresponding to the tabs on the html page. If you would like to change what data is displayed, change the value in the last column, `display`, from `y` to `n`. Save the excel sheet.

2. To apply these changes run the following command: 

`retriever_refresh -f file_name` to update the file that has been modified.

`-f` options are 
* `data_catalog`, 
* `pub_cite`, 
* `clinical_trials`, 
* `software_catalog`, or 
* `dbgap_data`. 

Specify the file name without the file extension: 
```
$ retriever_refresh -f data_catalog
```


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




