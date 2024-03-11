# before pushing ... remove api key, email from this file, make sure library tagging script is most up-to-date ...
import requests
from importlib import resources
import pandas as pd
# from ast import keyword
from Bio import Entrez
from urllib.error import HTTPError
import time, contextlib
import re
import json
import os
import xmltodict
from datetime import datetime
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

DEFAULT_GROUP_SIZE = 20
MAX_ATTEMPTS = 3
DELAY_BETWEEN_ATTEMPTS = 5
TAG_RE = re.compile(r'<[^>]+>')
try:
    Entrez.email = os.environ['NCBI_API_EMAIL']
    Entrez.api_key = os.environ['NCBI_API_KEY']
except KeyError:
    raise Error("Please set environmental variables NCBI_API_EMAIL and NCBI_API_KEY")
dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class PublicationData(object):
    def __init__(self, pubMedID, title, abstract, formattedTitle, keywords, meshterms, authors, issue, volume, pub, pub_full, day, month, year, affiliations, clinical_trials, grant):
        self.pubMedID = pubMedID
        self.title, self.abstract, self.formattedTitle, self.authors = title, abstract, formattedTitle, authors
        self.issue, self.volume, self.pub, self.day, self.month, self.year = issue, volume, pub, day, month, year
        self.keywords = keywords
        self.meshterms = meshterms
        self.pub_full = pub_full
        self.affiliations = affiliations
        self.clinical_trials = clinical_trials
        self.grant = grant

    def __repr__(self):
        return u'{}(pubMedID={})'.format(self.__class__.__name__, self.pubMedID)

def strip_grant_type(grant):
    return grant[3:]
    
def removeHTML(text):
    return TAG_RE.sub('', text)

#function retrieves PubMed publications from grant number
def getPublicationsForGrant(grant, groupSize=DEFAULT_GROUP_SIZE):
    print(grant)
    pubs = []
    with contextlib.closing(Entrez.esearch(
        db='pubmed', usehistory='y', retmax='1', term='{}[Grant Number]'.format(grant)
    )) as handle:
        results = Entrez.read(handle)
    total, webEnv, queryKey = int(results['Count']), results['WebEnv'], results['QueryKey']
    for start in range(0, total, groupSize):
        attempt = 0
        while attempt < MAX_ATTEMPTS:
            attempt += 1
            try:
                with contextlib.closing(Entrez.efetch(
                    db='pubmed', rettype='xml', retstart=start, retmax=groupSize, webenv=webEnv, query_key=queryKey
                )) as handle:
                    records = Entrez.read(handle)
                    break
            except HTTPError as err:
                if 500 <= err.code <= 599:
                    print(u'Received error {} from server on attempt {} of {}'.format(err.code, attempt, MAX_ATTEMPTS))
                    time.sleep(DELAY_BETWEEN_ATTEMPTS)
                else:
                    raise
        else:
            print(u'Too many attempts and Entrez keeps giving 500s')
            return
        for p in records[u'PubmedArticle']:
            pubMedID = str(p[u'MedlineCitation'][u'PMID'])
            formattedTitle = str(p[u'MedlineCitation'][u'Article'][u'ArticleTitle'])
            title = removeHTML(formattedTitle)
            keywords = json.loads(json.dumps(p[u'MedlineCitation'][u'KeywordList']))
            if len(keywords) > 0:
                keywords = keywords[0]

            meshtermslist = p[u'MedlineCitation'].get(u'MeshHeadingList', [])
            meshterms = []
            for term in meshtermslist:
                meshterms.append(str(term[u'DescriptorName']))
            # print(meshterms)

            abst = p[u'MedlineCitation'][u'Article'].get(u'Abstract')
            if abst:
                paras = abst.get(u'AbstractText', [])
                abstract = u'\n'.join(paras)
            else:
                abstract = u''
            names = p[u'MedlineCitation'][u'Article'].get(u'AuthorList', [])
            authors = []
            affiliations = []
            for name in names:
                if name.get(u'AffiliationInfo', u''):
                    affil = name.get(u'AffiliationInfo', u'')[0].get(u'Affiliation', u'')
                else:
                    affil = 'none_listed'
                surname = name.get(u'LastName', None)
                if not surname:
                    initials = name.get(u'Initials', None)
                    if not initials: continue
                initials = name.get(u'Initials', None)
                name = u'{} {}'.format(surname, initials) if initials else surname
                authors.append(name)
                affiliations.append(affil)
            issue = str(p[u'MedlineCitation'][u'Article'][u'Journal'][u'JournalIssue'].get(u'Issue', u''))
            volume = str(p[u'MedlineCitation'][u'Article'][u'Journal'][u'JournalIssue'].get(u'Volume', u''))
            pub = str(p[u'MedlineCitation'][u'Article'][u'Journal'].get('ISOAbbreviation', u''))
            pub_full = str(p[u'MedlineCitation'][u'Article'][u'Journal'].get('Title', u''))
            pubDate = p[u'MedlineCitation'][u'Article'][u'Journal'][u'JournalIssue'][u'PubDate']
            year, month, day = str(pubDate.get(u'Year', u'')), str(pubDate.get(u'Month', u'')), str(pubDate.get(u'Day', u''))
            
            try:
                if p[u'MedlineCitation'][u'Article'][u'DataBankList']:
                    # print(p[u'MedlineCitation'][u'Article'][u'DataBankList'])
                    if p[u'MedlineCitation'][u'Article'][u'DataBankList'][0]['DataBankName'] == 'ClinicalTrials.gov':
                        clinical_trials = p[u'MedlineCitation'][u'Article'][u'DataBankList'][0].get(u'AccessionNumberList', u'')
                        clinical_trials = list(set(clinical_trials))
                    else:
                        clinical_trials = ''
                else:
                    clinical_trials = ''
            except:
                clinical_trials = ''


            pubs.append(PublicationData(pubMedID, title, abstract, formattedTitle, keywords, meshterms, authors, issue, volume, pub, pub_full, day, month, year, affiliations, clinical_trials, grant))
    return pubs

#function retrieves PubMed publications from PubMed ID
# need to adjust groupSize still ... PMID_ls is actually a string with comma separated PMIDs
def getPublicationsForPMID_ls(PMID_ls, groupSize=301):
# groupSize=DEFAULT_GROUP_SIZE
    max_val = 301
    pubs = []
    with contextlib.closing(Entrez.epost(
        db='pubmed', id=PMID_ls
    )) as handle:
        results = Entrez.read(handle)
    # print(results)
    webEnv, queryKey = results['WebEnv'], results['QueryKey']
    for start in range(0, max_val, groupSize):
        attempt = 0
        while attempt < MAX_ATTEMPTS:
            attempt += 1
            try:
                with contextlib.closing(Entrez.efetch(
                    db='pubmed', rettype='xml', retstart=start, retmax=groupSize, webenv=webEnv, query_key=queryKey
                )) as handle:
                    records = Entrez.read(handle)
                    break
            except HTTPError as err:
                if 500 <= err.code <= 599:
                    print(u'Received error {} from server on attempt {} of {}'.format(err.code, attempt, MAX_ATTEMPTS))
                    time.sleep(DELAY_BETWEEN_ATTEMPTS)
                else:
                    raise
        else:
            print(u'Too many attempts and Entrez keeps giving 500s')
            return
    for p in records[u'PubmedArticle']:
        pubMedID = str(p[u'MedlineCitation'][u'PMID'])
        formattedTitle = str(p[u'MedlineCitation'][u'Article'][u'ArticleTitle'])
        title = removeHTML(formattedTitle)
        keywords = json.loads(json.dumps(p[u'MedlineCitation'][u'KeywordList']))
        if len(keywords) > 0:
            keywords = keywords[0]

        meshtermslist = p[u'MedlineCitation'].get(u'MeshHeadingList', [])
        meshterms = []
        for term in meshtermslist:
            meshterms.append(str(term[u'DescriptorName']))

        abst = p[u'MedlineCitation'][u'Article'].get(u'Abstract')
        if abst:
            paras = abst.get(u'AbstractText', [])
            abstract = u'\n'.join(paras)
        else:
            abstract = u''
        names = p[u'MedlineCitation'][u'Article'].get(u'AuthorList', [])
        authors = []
        affiliations = []
        for name in names:
            if name.get(u'AffiliationInfo', u''):
                affil = name.get(u'AffiliationInfo', u'')[0].get(u'Affiliation', u'')
            else:
                affil = 'none_listed'
            surname = name.get(u'LastName', None)
            if not surname:
                initials = name.get(u'Initials', None)
                if not initials: continue
            initials = name.get(u'Initials', None)
            name = u'{} {}'.format(surname, initials) if initials else surname
            authors.append(name)
            affiliations.append(affil)
        issue = str(p[u'MedlineCitation'][u'Article'][u'Journal'][u'JournalIssue'].get(u'Issue', u''))
        volume = str(p[u'MedlineCitation'][u'Article'][u'Journal'][u'JournalIssue'].get(u'Volume', u''))
        pub = str(p[u'MedlineCitation'][u'Article'][u'Journal'].get('ISOAbbreviation', u''))
        pub_full = str(p[u'MedlineCitation'][u'Article'][u'Journal'].get('Title', u''))
        pubDate = p[u'MedlineCitation'][u'Article'][u'Journal'][u'JournalIssue'][u'PubDate']
        year, month, day = str(pubDate.get(u'Year', u'')), str(pubDate.get(u'Month', u'')), str(pubDate.get(u'Day', u''))

        try:
            if p[u'MedlineCitation'][u'Article'][u'DataBankList']:
                if p[u'MedlineCitation'][u'Article'][u'DataBankList'][0]['DataBankName'] == 'ClinicalTrials.gov':
                    clinical_trials = p[u'MedlineCitation'][u'Article'][u'DataBankList'][0].get(u'AccessionNumberList', u'')
                    clinical_trials = list(set(clinical_trials))
                else:
                    clinical_trials = ''
            else:
                clinical_trials = ''
        except:
            clinical_trials = ''


        pubs.append(PublicationData(pubMedID, title, abstract, formattedTitle, keywords, meshterms, authors, issue, volume, pub, pub_full, day, month, year, affiliations, clinical_trials, ''))
    return pubs


# grant_list = ["grant1", "grant2"]
def grant_list_to_pubs_df(grant_list):
    pubs_out = []
    for grant in grant_list:
        pubs = getPublicationsForGrant(strip_grant_type(grant))
        for pub in pubs:
            pubs_out.append(pub.__dict__)
    pubmed_df = pd.DataFrame.from_dict(pubs_out)
    pubmed_df = pubmed_df.groupby('pubMedID', as_index=False, dropna=False).agg({'grant': list, 'title': 'first', 'abstract':'first', 'formattedTitle': 'first', 'keywords': 'first', 'meshterms': 'first', 'authors': 'first', 'issue': 'first', 'volume': 'first', 'pub': 'first', 'pub_full': 'first', 'day':'first', 'month':'first', 'year': 'first', 'affiliations': 'first', 'clinical_trials':'first'})
    pubmed_df['grant'] = [';'.join(map(str, x)) for x in pubmed_df['grant']]
    pmid_string = ",".join(list(pubmed_df['pubMedID'].astype(str)))
    pmid_ls = list(pubmed_df['pubMedID'].astype(str))
    return pmid_string, pubmed_df, pmid_ls

# pmid_string = '12345678,12345678,12345678'
def pmid_string_to_pubs_df(pmid_string):
    pubs_out = []
    pubs = getPublicationsForPMID_ls(pmid_string)
    for pub in pubs:
        pubs_out.append(pub.__dict__)
    pubmed_df = pd.DataFrame.from_dict(pubs_out)
    pubmed_df = pubmed_df.drop_duplicates('pubMedID', keep='first')
    return pubmed_df

def icite_request(pmid_string):
    response = requests.get(
        "".join([
            "https://icite.od.nih.gov/api/pubs?pmids=", pmid_string
        ]),
    )
    pub = response.json()
    icite_df = pd.DataFrame.from_dict(pub['data'])[['pmid', 'year', 'cited_by', 'references', 'doi', 'journal', 'is_research_article', 'citation_count', 'relative_citation_ratio']] #journal is shortened
    icite_df['pmid'] = icite_df['pmid'].astype(str)
    return icite_df

def merge_icite_pubmed(pubmed_df, icite_df):
    pm_icite_df = pd.merge(pubmed_df, icite_df, left_on='pubMedID', right_on='pmid', how='left')
    return pm_icite_df

def grant_method(grant_list):
    pmid_string, pubmed_df, pmid_ls = grant_list_to_pubs_df(grant_list)
    icite_df = icite_request(pmid_string)
    pm_icite_df = merge_icite_pubmed(pubmed_df=pubmed_df, icite_df=icite_df)
    return pm_icite_df

#add loop to deal with large lists of PMIDS
def pmid_method(pmid_list, max_num): #max_num  should not be > 500, groupSize should be updated to variable!
    if len(pmid_list) > max_num:
        pmid_string_temp = ",".join(pmid_list[0:max_num])
        pubmed_df = pmid_string_to_pubs_df(pmid_string_temp)
        for batch in (pmid_list[pos:pos + max_num] for pos in range(max_num, len(pmid_list), max_num)):
            pmid_string_temp = ",".join(batch)
            pubmed_df_temp = pmid_string_to_pubs_df(pmid_string_temp)
            pubmed_df = pd.concat([pubmed_df, pubmed_df_temp], ignore_index=True)
        pmid_string = ",".join(pmid_list)
    else:
        pmid_string = ",".join(pmid_list)
        # print(pmid_string)
        pubmed_df = pmid_string_to_pubs_df(pmid_string)
        pubmed_df = pubmed_df.drop(columns=['year'])
    icite_df = icite_request(pmid_string)
    pm_icite_df = merge_icite_pubmed(pubmed_df=pubmed_df, icite_df=icite_df)
    return pm_icite_df


def count_citations_per_year(icite_df):
    max_num = 1000
    pmid_list = []
    for pub in icite_df['cited_by']:
        if len(pub) > 0:
            for id in pub:
                pmid_list.append(id)
    if len(list(set(pmid_list))) > max_num:
        pmid_string_temp = ",".join([str(item) for item in list(set(pmid_list[0:max_num]))])
        new_icite_df = icite_request(pmid_string_temp)
        for batch in (pmid_list[pos:pos + max_num] for pos in range(max_num, len(pmid_list), max_num)):
            pmid_string_temp = ",".join([str(item) for item in list(set(batch))])
            icite_df_temp = icite_request(pmid_string_temp)
            new_icite_df = pd.concat([new_icite_df, icite_df_temp], ignore_index=True)
    else:
        new_pmid_string = ",".join([str(item) for item in list(set(pmid_list))])
        new_icite_df = icite_request(new_pmid_string)
    count = pd.DataFrame(new_icite_df['year'].value_counts())
    count.reset_index(inplace=True)
    count = count.rename(columns = {'index':'year','year':'Citations'})
    count = count.sort_values(by=['year'])
    return count

#inputting one pmid at a time, return list of sra_ids 
def getSRAIdFromPMID(PMID_ls):
    # max_val = 200
    with contextlib.closing(Entrez.elink(
        dbfrom='pubmed', db='sra', id=PMID_ls
    )) as handle:
        results = Entrez.read(handle)
    sra_ids = []
    if len(results[0]['LinkSetDb']) > 0:
        for e in results[0]['LinkSetDb'][0]['Link']:
            sra_ids.append(e['Id'])
    return sra_ids

def safeget(dct, *keys):
    for key in keys:
        try:
            dct = dct[key]
        except KeyError:
            return '-'
    return dct

# gets info from SRA db for a single SRA id
def getInfoFromSRA(sra_id):
    handle = Entrez.efetch(db='sra', id=sra_id)
    string = handle.read().decode()
    parsed = xmltodict.parse(string)
    sra_info_df = pd.DataFrame(columns = ['sra_db_id', 'srp_accession', 'gse_refname', 'sample_srs', 'sample_gsm', 'sample_title', 'sample_taxon', 'library_strategy', 'library_source', 'library_selection', 'library_construction_protocol', 'study_title', 'study_abstract', 'sample_attributes', 'sra_link', 'sra_date'])
    srp_accession = str(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['EXPERIMENT']['STUDY_REF']['IDENTIFIERS']['PRIMARY_ID'])
    try:
        # gse_refname = str(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['EXPERIMENT']['STUDY_REF']['@refname'])
        gse_refname = str(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['STUDY']['DESCRIPTOR']['CENTER_PROJECT_NAME'])
    except:
        # gse_refname = str(parsed[])
        gse_refname = '@ref_name does not exist ... check for alternative xml keys'
    sample_srs = str(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['SAMPLE']['@accession'])
    sample_gsm = str(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['SAMPLE']['@alias']) #check that this is always gsm ?
    try:
       sample_title = str(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['SAMPLE']['TITLE'])
    except:
        sample_title = ''
    sample_taxon = str(safeget(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['SAMPLE']['SAMPLE_NAME'], 'SCIENTIFIC_NAME'))
    library_strategy = str(safeget(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['EXPERIMENT']['DESIGN']['LIBRARY_DESCRIPTOR'], 'LIBRARY_STRATEGY'))
    library_source = str(safeget(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['EXPERIMENT']['DESIGN']['LIBRARY_DESCRIPTOR'], 'LIBRARY_SOURCE'))
    library_selection = str(safeget(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['EXPERIMENT']['DESIGN']['LIBRARY_DESCRIPTOR'], 'LIBRARY_SELECTION'))
    study_title = str(safeget(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['STUDY']['DESCRIPTOR'], 'STUDY_TITLE'))
    study_abstract = str(safeget(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['STUDY']['DESCRIPTOR'], 'STUDY_ABSTRACT'))
    sample_attributes = ''
    # sample_attributes = []
    try:
        for att in parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['SAMPLE']['SAMPLE_ATTRIBUTES']['SAMPLE_ATTRIBUTE']:
            # sample_attributes.append(f"{att['TAG']}: {att['VALUE']}")
            sample_attributes = str(sample_attributes+f"{att['TAG']}:{att['VALUE']};")
        sample_attributes = str(sample_attributes)
    except:
        sample_attributes = 'attributes: none;'   

    sra_link = 'no_https_link'
    try:
        for file in parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['RUN_SET']['RUN']['SRAFiles']['SRAFile']:
            try:
                sra_link = file['@url']
            except:
                if sra_link == 'no_https_link':
                    sra_link = 'no_https_link'
    except:
        sra_link = 'no_https_link'
    
    try:
        library_construction_protocol = str(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['EXPERIMENT']['DESIGN']['LIBRARY_DESCRIPTOR']['LIBRARY_CONSTRUCTION_PROTOCOL'])
    except KeyError:
        library_construction_protocol = 'no_protocol'
    except:
        pass
    
    try:
        sra_date = datetime.strptime(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['RUN_SET']['RUN']['SRAFiles']['SRAFile'][0]['@date'], '%Y-%m-%d %H:%M:%S').date()
    except:
        try:
            sra_date = str(parsed['EXPERIMENT_PACKAGE_SET']['EXPERIMENT_PACKAGE']['RUN_SET']['RUN']['SRAFiles']['SRAFile'][0]['@date'])
        except:
            sra_date = 'no date available'
    new_row = {'sra_db_id': sra_id, 'srp_accession': srp_accession, 'gse_refname': gse_refname, 'sample_srs': sample_srs, 'sample_gsm':sample_gsm, 'sample_title': sample_title, 'sample_taxon': sample_taxon, 'library_strategy': library_strategy, 'library_source': library_source, 'library_selection': library_selection, 'library_construction_protocol': library_construction_protocol, 'study_title': study_title, 'study_abstract': study_abstract, 'sample_attributes': sample_attributes, 'sra_link': sra_link, 'sra_date': sra_date}
    sra_info_df = pd.concat([sra_info_df, pd.DataFrame(new_row, columns=sra_info_df.columns, index=[0])], ignore_index=True)

    return sra_info_df

# takes one pmid and returns SRA information in a dataframe
def pmid_to_sra_info_df(pmid):
    sra_ids = getSRAIdFromPMID(pmid)
    sra_df = pd.DataFrame(columns=['pmid', 'sra_db_id', 'srp_accession', 'gse_refname', 'sample_srs', 'sample_gsm', 'sample_title', 'sample_taxon', 'library_strategy', 'library_source', 'library_selection', 'library_construction_protocol', 'study_title', 'study_abstract', 'sample_attributes', 'sra_link', 'sra_date'])
    if len(sra_ids) > 0:
        for sra_id in sra_ids:
            # print(sra_id)
            temp_sra_df = getInfoFromSRA(sra_id)
            new_row = {'pmid': pmid, 'sra_db_id': temp_sra_df['sra_db_id'][0] ,'srp_accession': temp_sra_df['srp_accession'][0], 'gse_refname': temp_sra_df['gse_refname'][0], 'sample_srs': temp_sra_df['sample_srs'][0], 'sample_gsm':temp_sra_df['sample_gsm'][0], 'sample_title': temp_sra_df['sample_title'][0], 'sample_taxon': temp_sra_df['sample_taxon'][0], 'library_strategy': temp_sra_df['library_strategy'][0], 'library_source': temp_sra_df['library_source'][0], 'library_selection': temp_sra_df['library_selection'][0], 'library_construction_protocol': temp_sra_df['library_construction_protocol'][0], 'study_title': temp_sra_df['study_title'][0], 'study_abstract': temp_sra_df['study_abstract'][0], 'sample_attributes': temp_sra_df['sample_attributes'][0], 'sra_link': temp_sra_df['sra_link'][0], 'sra_date': temp_sra_df['sra_date'][0]}
            sra_df = pd.concat([sra_df, pd.DataFrame(new_row, columns=sra_df.columns, index=[0])], ignore_index=True)
    return sra_df

# starts from list of grants > list of pmids > list of SRA ids > builds dataframe of SRA info .. kind of slow
def grant_ls_to_sra_info_df(grant_ls):
    pmid_str, pubmed_df, pmid_ls = grant_list_to_pubs_df(grant_ls)
    sra_df = pd.DataFrame(columns=['pmid', 'sra_db_id', 'srp_accession', 'gse_refname', 'sample_srs', 'sample_gsm', 'sample_title', 'sample_taxon', 'library_strategy', 'library_source', 'library_selection', 'library_construction_protocol', 'study_title', 'study_abstract', 'sample_attributes', 'sra_link', 'sra_date'])
    for i in pmid_ls:
        temp_sra_df = pmid_to_sra_info_df(i)
        sra_df = pd.concat([sra_df, temp_sra_df], ignore_index=True)
    return sra_df

def pmid_ls_to_sra_info_df(pmid_ls):
    sra_df = pd.DataFrame(columns=['pmid', 'sra_db_id', 'srp_accession', 'gse_refname', 'sample_srs', 'sample_gsm', 'sample_title', 'sample_taxon', 'library_strategy', 'library_source', 'library_selection', 'library_construction_protocol', 'study_title', 'study_abstract', 'sample_attributes', 'sra_link', 'sra_date'])
    for i in pmid_ls:
        temp_sra_df = pmid_to_sra_info_df(i)
        sra_df = pd.concat([sra_df, temp_sra_df], ignore_index=True)
    return sra_df


def getGEOIdFromPMID(pmid_ls):
    pmid_geo_linker = pd.DataFrame(columns=['pmid', 'geo_db_id'])
    geo_ids = []
    for pmid in pmid_ls:
        with contextlib.closing(Entrez.elink(
            dbfrom='pubmed', db='gds', id= pmid
        )) as handle:
            results = Entrez.read(handle)
        try:
            for e in results[0]['LinkSetDb'][0]['Link']:
                # print(e)
                geo_ids.append(e['Id'])
                new_row = {'pmid': pmid, 'geo_db_id':e['Id']}
                pmid_geo_linker = pd.concat([pmid_geo_linker, pd.DataFrame(new_row, columns=pmid_geo_linker.columns, index=[0])], ignore_index=True)
        except:
            pass
    return geo_ids, pmid_geo_linker

def getInfoFromGEO(string_of_geo_ids):
    handle = Entrez.esummary(db = "gds", id = ",".join(string_of_geo_ids))
    records = Entrez.parse(handle)
    geo_df = pd.DataFrame(columns = ['geo_id', 'geo_accession', 'geo_title', 'geo_summary', 'geo_taxon', 'geo_gdsType', 'geo_n_samples', 'geo_date'])
    for r in records:
        pmids = safeget(r, 'PubMedIds')
        pmid_ls = []
        for i in pmids:
            pmid_ls.append(str(i.real))
        geoID = str(safeget(r, 'Id'))
        accession = str(safeget(r, 'Accession'))
        title = str(safeget(r, 'title'))
        summary = str(safeget(r, 'summary'))
        # print(summary)
        taxon = str(safeget(r, 'taxon'))
        gdsType = str(safeget(r, 'gdsType'))
        n_samples = str(r['n_samples'].real)
        geo_date = datetime.strptime(r['PDAT'], '%Y/%m/%d').date()
        new_row = {'geo_id': geoID, 'geo_accession': accession, 'geo_title': title, 'geo_summary': summary, 'geo_taxon': taxon, 'geo_gdsType': gdsType, 'geo_n_samples': n_samples, 'geo_date': geo_date}
        geo_df = pd.concat([geo_df, pd.DataFrame(new_row, columns=geo_df.columns, index=[0])], ignore_index=True)
        # geo_df = geo_df.append({'pmid': pmid_ls, 'geo_id': geoID, 'geo_accession': accession, 'geo_title': title, 'geo_summary': summary, 'geo_taxon': taxon, 'geo_gdsType': gdsType, 'geo_n_samples': n_samples}, ignore_index=True)
    return geo_df

def grant_ls_to_geo_info_df(grant_ls):
    pmid_str, pubmed_df, pmid_ls = grant_list_to_pubs_df(grant_ls)
    # pmid_ls = list(pubmed_df['pubMedID'].astype(str))
    geo_ids, pmid_geo_linker = getGEOIdFromPMID(pmid_ls)
    # print(geo_ids)
    geo_df = pd.DataFrame(columns = ['geo_id', 'geo_accession', 'geo_title', 'geo_summary', 'geo_taxon', 'geo_gdsType', 'geo_n_samples', 'geo_date'])
    for i in geo_ids:
        temp_geo_df = getInfoFromGEO([str(i)])
        geo_df = pd.concat([geo_df, temp_geo_df], ignore_index=True)
    geo_df = pd.merge(pmid_geo_linker, geo_df, left_on='geo_db_id', right_on='geo_id', how='left')
    geo_df = geo_df.drop(columns = ['geo_db_id'])
    return geo_df

# pmid_ls from grant_list_to_pubs_df
def pmid_ls_to_geo_info_df(pmid_ls):
    geo_ids, pmid_geo_linker = getGEOIdFromPMID(pmid_ls)
    # print(geo_ids)
    geo_df = pd.DataFrame(columns = ['geo_id', 'geo_accession', 'geo_title', 'geo_summary', 'geo_taxon', 'geo_gdsType', 'geo_n_samples', 'geo_date'])
    for i in geo_ids:
        temp_geo_df = getInfoFromGEO([str(i)])
        geo_df = pd.concat([geo_df, temp_geo_df], ignore_index=True)
    geo_df = pd.merge(pmid_geo_linker, geo_df, left_on='geo_db_id', right_on='geo_id', how='left')
    geo_df = geo_df.drop(columns = ['geo_db_id'])
    return geo_df


def get_grant_linker(linker, pmid):
    # print("PMID:" + pmid)
    if pmid in linker:
        # print("LINKED:" + linker[pmid])
        return linker[pmid]
    return ""

## input = grant list, output = excel sheet/ dataframes
# example usage:
# print(grant_to_output(['ABCD1234567']))

def grant_to_output(id_ls, output_file='grant_output', write=False, id_type='grant_list', dbgap_filename=False):
# def grant_to_output(grant_ls, output_file='grant_output', write=False, id_type = 'grant_list'):
    # get pubMed data from list of grants
    if id_type == 'grant_list':
        pmid_str, pubmed_df, pmid_ls = grant_list_to_pubs_df(id_ls)
        pubmed_df = pubmed_df.drop(columns=['year'])
        # pubmed_df.to_csv('pub_data.txt', sep='\t') # what is this used for?
        pub_grant_linker = pubmed_df[['pubMedID', 'grant']]
        pub_grant_linker = dict(zip(pubmed_df.pubMedID, pubmed_df.grant))
        geo_df = pmid_ls_to_geo_info_df(pmid_ls)
        sra_sample_df = pmid_ls_to_sra_info_df(pmid_ls)

        # get icite data and merge on pmid
        icite_df = icite_request(pmid_str)
        pm_icite_df = merge_icite_pubmed(pubmed_df, icite_df)
        pm_icite_df = pm_icite_df.drop(columns= ['pmid']) #keep year from icite bc always consistent
    elif id_type == 'pmid_list':
        pm_icite_df = pmid_method(id_ls, 200)
        pm_icite_df = pm_icite_df.drop(columns= ['pmid', 'pub']) 
        geo_df = pmid_ls_to_geo_info_df(id_ls)
        sra_sample_df = pmid_ls_to_sra_info_df(id_ls) 

    # sra_df = sra_sample_df.drop_duplicates(subset = ['pmid', 'srp_accession', 'gse_refname'], keep='first')[['pmid', 'srp_accession', 'gse_refname', 'library_strategy', 'library_source', 'library_selection', 'study_title', 'study_abstract', 'sample_taxon', 'sample_attributes', 'sra_date']]
    sra_df = sra_sample_df.groupby(['pmid', 'srp_accession', 'gse_refname'], as_index=False, dropna=False).agg({'sample_srs': 'count', 'library_strategy': 'first', 'library_source': 'first', 'library_selection': 'first', 'study_title': 'first', 'study_abstract': 'first', 'sample_taxon': 'first', 'sample_attributes': 'first', 'sra_date': 'first'})
    geo_df = geo_df.drop_duplicates(keep='first', ignore_index=True)
    data_table = pd.merge(geo_df, sra_df, left_on = 'geo_accession', right_on = 'gse_refname', how = 'outer') #outer join to include SRA records without GEO ids
    # print(data_table.columns)
    data_table = data_table.drop_duplicates(keep='first', ignore_index=True)
    data_table['pmid'] = data_table['pmid_x'].fillna(data_table['pmid_y'])
    #add condition for dbgap file
    if dbgap_filename:
        dbgap_df = pd.read_excel(dbgap_filename, dtype=str)
        dbgap_df = dbgap_df.rename(columns={'pmid_d': 'pmid', 'dbgap_data_type': 'library_strategy'})
        # this merge actually needs to be a concat ... will have lots of blank rows 
        data_table = pd.concat([data_table, dbgap_df], join='outer', ignore_index=True)
        data_table['pad_dbgap_title'] = data_table['dbgap_title'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
        data_table['pad_dbgap_title'] = ' ' + data_table['pad_dbgap_title'] + ' '
        data_table['pad_dbgap_desc'] = data_table['dbgap_desc'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
        data_table['pad_dbgap_desc'] = ' ' + data_table['pad_dbgap_desc'] + ' '
        data_table['pad_dbgap_cancer_type'] = data_table['dbgap_cancer_type'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
        data_table['pad_dbgap_cancer_type'] = ' ' + data_table['pad_dbgap_cancer_type'] + ' '

    # perform cancer tagging#########
    #add some padded cols to the data_table dataframe
    data_table['pad_geo_title'] = data_table['geo_title'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
    data_table['pad_geo_title'] = ' ' + data_table['pad_geo_title'] + ' '
    data_table['pad_geo_summary'] = data_table['geo_summary'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
    data_table['pad_geo_summary'] = ' ' + data_table['pad_geo_summary'] + ' '
    data_table['pad_study_title'] = data_table['study_title'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
    data_table['pad_study_title'] = ' ' + data_table['pad_study_title'] + ' '
    data_table['pad_study_abstract'] = data_table['study_abstract'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
    data_table['pad_study_abstract'] = ' ' + data_table['pad_study_abstract'] + ' '
    data_table['pad_sample_attributes'] = data_table['sample_attributes'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')

    #add some padded cols to the pub dataframe
    pm_icite_df['pad_abstract'] = pm_icite_df['abstract'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
    pm_icite_df['pad_abstract'] = ' ' + pm_icite_df['pad_abstract'] + ' '
    pm_icite_df['pad_title'] = pm_icite_df['title'].str.replace('[^\w\s]', ' ', regex = True).str.replace('  ', ' ')
    pm_icite_df['pad_title'] = ' ' + pm_icite_df['pad_title'] + ' '
    pm_icite_df['pad_mesh'] = pm_icite_df['meshterms'].str.replace("'", " ' ")
    pm_icite_df['pad_keyw'] = pm_icite_df['keywords'].str.replace("'", " ' ")

    with resources.path('retrieverapp.terms', 'NCItm_synonyms_granularparent_1228.csv') as datafile:
        cts_df = pd.read_csv(datafile, low_memory=False)

    cts_terms = list(cts_df[cts_df['Parent_name'] != 'Other']['padlower'])
    # cts_terms = list(cts_df[(cts_df['abbrev'] != True) & (cts_df['Parent_name'] != 'Other')]['padlower'])
    cts_terms.extend([' coronavirus ', ' covid 19 '])
    other_terms = list(cts_df[(cts_df['abbrev'] != True) | (cts_df['Parent_name'] == 'Other')]['padlower'])
    abbr_terms = list(cts_df[cts_df['abbrev'] == True]['padded'])

    tag_ls = []
    parent_ls = []
    tagged_from_ls = []
    # print('tagging publications ------------------------------------------ ')

    for index, row in pm_icite_df.iterrows():
        tags = [term for term in cts_terms if str(row['pad_mesh']).lower().find(term) > -1 or str(row['pad_keyw']).lower().find(term) > -1 or str(row['pad_title']).lower().find(term) > -1]
        if len(tags) > 0:
            tagged_from = '1: mesh, keyw, title'
        if len(tags) == 0:
            tags = [term for term in cts_terms if str(row['pad_abstract']).lower().find(term) > -1]
            if len(tags) > 0:
                tagged_from = '2: abstract'
        # if len(tags) == 0: # check meshterms, title for less descriptive terms ..
        #     tags = [term for term in other_terms if str(row['pad_mesh']).lower().find(term) > -1 or str(row['pad_keyw']).lower().find(term) > -1 or str(row['pad_title']).lower().find(term) > -1]
        #     if len(tags) > 0:
        #         tagged_from = '3: mesh, keyw, title - other terms'
        # if len(tags) == 0:
        #     tags = [term for term in other_terms if str(row['pad_abstract']).lower().find(term) > -1]
        #     if len(tags) > 0:
        #         tagged_from = '4: abstract - other terms'
        # if len(tags) == 0: # check meshterms, title for less descriptive terms ..
        #     tags = [term for term in abbr_terms if str(row['pad_mesh']).find(term) > -1 or str(row['pad_keyw']).find(term) > -1 or str(row['pad_title']).find(term) > -1]
        #     if len(tags) > 0:
        #         tagged_from = '5: mesh, keyw, title - abbrev'

        if len(tags) == 0:
            tags = ''
            tagged_from = ''

        tag_ls.append(list(set(tags)))

        parent_tags = []
        for x in list(set(tags)):
            try:
                parent_tags.append(cts_df[cts_df['padlower'] == x]['Parent_name'].values[0])
            except:
                if x == ' coronavirus ' or x == ' covid 19 ':
                    parent_tags.append('Covid-19')
                else:
                    parent_tags.append('N/A')

        tagged_from_ls.append(tagged_from)
        parent_ls.append(list(set(parent_tags)))

    # print('tagging data -------------------------------------------------- ')
    data_tag_ls = []
    data_parent_ls = []
    for index, row in data_table.iterrows():
        if dbgap_filename:
            tags = [term for term in cts_terms if str(row['pad_geo_title']).lower().find(term) > -1 or str(row['pad_geo_summary']).lower().find(term) > -1 or str(row['pad_study_title']).lower().find(term) > -1 or str(row['pad_study_abstract']).lower().find(term) > -1 or str(row['pad_dbgap_title']).lower().find(term) > -1 or str(row['pad_dbgap_desc']).lower().find(term) > -1 or str(row['pad_dbgap_cancer_type']).lower().find(term) > -1]
        else:
            tags = [term for term in cts_terms if str(row['pad_geo_title']).lower().find(term) > -1 or str(row['pad_geo_summary']).lower().find(term) > -1 or str(row['pad_study_title']).lower().find(term) > -1 or str(row['pad_study_abstract']).lower().find(term) > -1]

        if len(tags) == 0:
            tags = [term for term in cts_terms if str(row['pad_sample_attributes']).lower().find(term) > -1]
        data_tag_ls.append(list(set(tags)))

        data_parent_tags = []
        for x in list(set(tags)):
            try:
                data_parent_tags.append(cts_df[cts_df['padlower'] == x]['Parent_name'].values[0])
            except:
                if x == ' coronavirus ' or x == ' covid 19 ':
                    parent_tags.append('Covid-19')
                else:
                    data_parent_tags.append('N/A')

        data_parent_ls.append(list(set(data_parent_tags)))

    pm_icite_df = pm_icite_df.assign(all_tags_pub = tag_ls)
    pm_icite_df = pm_icite_df.assign(parent_tag_pub = parent_ls)
    pm_icite_df = pm_icite_df.assign(tagged_from = tagged_from_ls)

    data_table = data_table.assign(all_tags_data = data_tag_ls)
    data_table = data_table.assign(parent_tag_data = data_parent_ls)
    #########################################
    # library strategy tagging if 'nan' or 'Other' ... can we pull a tag from the GEO or SRA title?
    #########################################
    with resources.path('retrieverapp.terms', 'library_strategy_tag.csv') as datafile:    
        strategy_df = pd.read_csv(datafile)
    
    strategy_terms = list(strategy_df['tagged_terms_lower'])
    sc_tags = ['single-cell', 'single cell', 'singlecell']
    # just grab all tags from the titles ... (summary gives too many false positives) .. only overwrite them if the original was nan or other or if scRNA or scATAC
    for index, row in data_table.iterrows():
        row = row.copy()
        tags = [term for term in strategy_terms if str(row['pad_geo_title']).lower().find(term) > -1 or str(row['pad_study_title']).lower().find(term) > -1]
        sctags = [term for term in sc_tags if str(row['geo_title']).lower().find(term) > -1 or str(row['study_title']).lower().find(term) > -1]
        if len(tags) > 0 or len(sctags) > 0:
            strategy_parent_tags_ls = []
            for x in list(set(tags)):
                strategy_parent_tags_ls.append(strategy_df[strategy_df['tagged_terms_lower'] == x]['parent_term'].values[0])
            
            strategy_parent_tags_ls_longest = strategy_parent_tags_ls.copy()
            for item in strategy_parent_tags_ls:
                for other_item in strategy_parent_tags_ls:
                    if item != other_item and item in other_item:
                        strategy_parent_tags_ls_longest.remove(item)
                        break  # break out of the inner loop if item is removed
            
            strategy_parent_tags = ";".join(list(set(strategy_parent_tags_ls_longest)))
            
            #covers the case where there was no previous label but we picked up tags
            if str(row['library_strategy']) == 'nan' or row['library_strategy'].lower() == 'other':
                if 'RNA-Seq' in strategy_parent_tags_ls_longest and ('scRNA-Seq' in strategy_parent_tags_ls_longest or len(sctags) > 0):
                    data_table.at[index, 'library_strategy'] = 'scRNA-Seq'
                elif 'ATAC-Seq' in strategy_parent_tags_ls_longest and ('scATAC-Seq' in strategy_parent_tags_ls_longest or len(sctags) > 0):
                    data_table.at[index, 'library_strategy'] = 'scATAC-Seq'
                else:
                    data_table.at[index, 'library_strategy'] = strategy_parent_tags
            #covers the case where previous label was RNA-seq and also picked up sc in tag
            elif str(row['library_strategy']) == 'RNA-Seq' and ('scRNA-Seq' in strategy_parent_tags_ls_longest or len(sctags) > 0):
                data_table.at[index, 'library_strategy'] = 'scRNA-Seq'
            #covers the case where previous label was ATAC-seq and also picked up sc in tag list
            elif str(row['library_strategy']) == 'ATAC-Seq' and ('scATAC-Seq' in strategy_parent_tags_ls_longest or len(sctags) > 0):
                data_table.at[index, 'library_strategy'] = 'scATAC-Seq'
            else: # if there are tags picked up but doesnt fit any other cases ... use new tags?
                data_table.at[index, 'library_strategy'] = strategy_parent_tags
        if len(tags) == 0: #assume if we dont pick up a tag, will not need to overwrite a previously assigned label 
            if str(row['library_strategy']) == 'nan' or row['library_strategy'].lower() == 'other':
                data_table.at[index, 'library_strategy'] = 'Other'           
    #########################################

    # print(data_table.head())
    if id_type == 'grant_list':
        data_table['grant'] = data_table.apply(lambda x: get_grant_linker(pub_grant_linker, str(x['pmid'])), axis=1)
    data_table = pd.merge(data_table, pm_icite_df[['pubMedID', 'parent_tag_pub', 'all_tags_pub']], left_on = 'pmid', right_on = 'pubMedID', how = 'left') #include the tag from the publication

    data_table['cancer_tag'] = data_table['parent_tag_data'].where(data_table['parent_tag_data'].str.len() > 0, "['N/A']")

    data_table = data_table[data_table.geo_summary != 'This SuperSeries is composed of the SubSeries listed below.']

    if id_type == 'grant_list':
        new_df = data_table[['pmid', 'geo_accession', 'srp_accession', 'grant']]
    else:
        new_df = data_table[['pmid', 'geo_accession', 'srp_accession']]
    
    if dbgap_filename:
        new_df.loc[:, 'data_title'] = data_table['study_title'].fillna(data_table['geo_title']).fillna(data_table['dbgap_title'])
        new_df.loc[:, 'data_summary'] = data_table['study_abstract'].fillna(data_table['geo_summary']).fillna(data_table['dbgap_desc'])
        new_df.loc[:, 'dbgap_id'] = data_table['dbgap_id']
    else:
        new_df.loc[:, 'data_title'] = data_table['study_title'].fillna(data_table['geo_title'])
        new_df.loc[:, 'data_summary'] = data_table['study_abstract'].fillna(data_table['geo_summary'])
    new_df.loc[:, 'taxon'] = data_table['geo_taxon'].fillna(data_table['sample_taxon']).fillna('-')
    new_df.loc[:, 'library_strategy'] = data_table['library_strategy']
    new_df.loc[:, 'n_samples'] = data_table['geo_n_samples'].fillna(data_table['sample_srs'])
    # new_df.loc[:, 'cancer_type'] = data_table['cancer_tag']
    new_df['cancer_type'] = data_table['cancer_tag']

    # drop duplicate records by grouping by geoID and sraID, keep all pmids in list and sort so we can order py pmid
    if id_type == 'grant_list':
        if dbgap_filename:
            new_df = new_df.groupby(['geo_accession', 'srp_accession', 'dbgap_id'], as_index=False, dropna=False).agg({'data_title': 'first', 'data_summary': 'first', 'taxon': 'first', 'n_samples': 'first', 'library_strategy': 'first', 'cancer_type': 'first', 'pmid': list, 'grant': list})
        else:
            new_df = new_df.groupby(['geo_accession', 'srp_accession'], as_index=False, dropna=False).agg({'data_title': 'first', 'data_summary': 'first', 'taxon': 'first', 'n_samples': 'first', 'library_strategy': 'first', 'cancer_type': 'first', 'pmid': list, 'grant': list})
    else:
        if dbgap_filename:
            new_df = new_df.groupby(['geo_accession', 'srp_accession', 'dbgap_id'], as_index=False, dropna=False).agg({'data_title': 'first', 'data_summary': 'first', 'taxon': 'first', 'n_samples': 'first', 'library_strategy': 'first', 'cancer_type': 'first', 'pmid': list})
        else:    
            new_df = new_df.groupby(['geo_accession', 'srp_accession'], as_index=False, dropna=False).agg({'data_title': 'first', 'data_summary': 'first', 'taxon': 'first', 'n_samples': 'first', 'library_strategy': 'first', 'cancer_type': 'first', 'pmid': list})

    new_df['pmid'] = new_df['pmid'].apply(lambda x: list(set(x)))
    new_df['grant'] = new_df['grant'].apply(lambda x: list(set(x)))
    new_df['grant'] = [';'.join(map(str, x)) for x in new_df['grant']]
    new_df['earliest_pmid'] = [min(x) for x in new_df['pmid']] 
    new_df['pmid_link'] = 'https://pubmed.ncbi.nlm.nih.gov/?term=' + new_df['pmid'].apply(lambda x: '+'.join(x))
    new_df = new_df.sort_values(by = ['earliest_pmid'])
    if write:
        writer = pd.ExcelWriter(f'{output_file}.xlsx', engine='xlsxwriter')
        pm_icite_df.to_excel(writer, sheet_name='Publication_Citation_table')
        new_df.to_excel(writer, sheet_name= 'Data_table')
        sra_df.to_excel(writer, sheet_name='RAW_SRA_Summary_table')
        sra_sample_df.to_excel(writer, sheet_name='RAW_SRA_Sample_table')
        geo_df.to_excel(writer, sheet_name='RAW_GEO_table')
        data_table.to_excel(writer, sheet_name='RAW_Data_table')
        writer.save()
    pub_json = pm_icite_df.to_json(orient='index')
    data_json = new_df.to_json(orient='index')
    pub_json_dict = json.loads(pub_json)
    data_json_dict = json.loads(data_json)


    with open(f'{output_file}/pub_cite.json', 'w', encoding='utf-8') as f:
        f.write('let pub_cite_data = ' + json.dumps(pub_json_dict) + ';')
        f.close()
    with open(f'{output_file}/data_catalog.json', 'w', encoding='utf-8') as f:
        f.write('let data_catalog_data = ' + json.dumps(data_json_dict) + ';')
        f.close()
    return pm_icite_df, new_df

### functions for clinical trials / dbGap tagging:
# get PMC link from pubMedID
def getPMCIdFromPMID(PMID_ls):
    # max_val = 200
    with contextlib.closing(Entrez.elink(
        dbfrom='pubmed', db='pmc', id=PMID_ls
    )) as handle:
        results = Entrez.read(handle)
    pmc_ids = []
    if results:
        if len(results[0]['LinkSetDb']) > 0 and results[0]['LinkSetDb'][0]['LinkName'] == 'pubmed_pmc':
            for e in results[0]['LinkSetDb'][0]['Link']:
                pmc_ids.append(e['Id'])
    return pmc_ids


def getInfoFromPMC(pmc_id, groupSize=DEFAULT_GROUP_SIZE, max_val = 300):    
    handle = Entrez.efetch(db='pmc', id=pmc_id)
    string = handle.read().decode()
    root = ET.fromstring(string)

    full_txt = ''
    for element in root.iter():

        if element.text:
            element_text = element.text.strip()
            full_txt = full_txt + ' ' + element_text

    nct_ids = re.findall(r'NCT\d{8}', full_txt)
    gap_ids = re.findall(r'phs\d+\.v\d+\.p\d+', full_txt)
    git_ids = re.findall(r'\bhttps?://[^\s]*github[^\s]*\b', full_txt)
    nct_indices = [m.start() for m in re.finditer(r'NCT\d{8}', full_txt)]
    gap_indices = [m.start() for m in re.finditer(r'phs\d+\.v\d+\.p\d+', full_txt)]
    git_indices = [m.start() for m in re.finditer(r'\bhttps?://[^\s]*github[^\s]*\b', full_txt)]
    
    nct_pmc_df = pd.DataFrame(columns=['pmc_id', 'nct', 'full_txt', 'start_idx', 'partial_txt'])
    gap_pmc_df = pd.DataFrame(columns=['pmc_id', 'dbgap', 'full_txt', 'start_idx', 'partial_txt'])
    git_pmc_df = pd.DataFrame(columns=['pmc_id', 'github', 'full_txt', 'start_idx', 'partial_txt'])

    for i in range(len(nct_ids)):
        nct_id = nct_ids[i]
        ind = nct_indices[i]
        partial_txt = full_txt[ind-1000:ind+1000]
        nct_pmc_df.loc[i] = [pmc_id, nct_id, full_txt, ind, partial_txt]

    for i in range(len(gap_ids)):
        gap_id = gap_ids[i]
        ind = gap_indices[i]
        partial_txt = full_txt[ind-1000:ind+1000]
        gap_pmc_df.loc[i] = [pmc_id, gap_id, full_txt, ind, partial_txt]

    for i in range(len(git_ids)):
        git_id = git_ids[i]
        ind = git_indices[i]
        partial_txt = full_txt[ind-1000:ind+1000]
        git_pmc_df.loc[i] = [pmc_id, git_id, full_txt, ind, partial_txt]
        
    return nct_pmc_df, gap_pmc_df, git_pmc_df

# takes one pmid and returns PMC information in a dataframe
def pmid_to_pmc_info_df(pmid):
    pmc_ids = getPMCIdFromPMID(pmid)
    # pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'full_txt', 'partial_txt', 'nct', 'start_idx'])
    nct_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'nct', 'full_txt', 'start_idx', 'partial_txt'])
    gap_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'dbgap', 'full_txt', 'start_idx', 'partial_txt'])
    git_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'github', 'full_txt', 'start_idx', 'partial_txt'])
    if len(pmc_ids) > 0:
        for pmc_id in pmc_ids:
            # print(pmc_id)
            # temp_pmc_df = getInfoFromPMC(pmc_id) #this does not have pmid yet
            temp_nct_pmc_df, temp_gap_pmc_df, temp_git_pmc_df = getInfoFromPMC(pmc_id) #this does not have pmid yet
            temp_nct_pmc_df['pmid'] = pmid
            temp_gap_pmc_df['pmid'] = pmid
            temp_git_pmc_df['pmid'] = pmid

            nct_pmc_df = pd.concat([nct_pmc_df, temp_nct_pmc_df], ignore_index=True)
            gap_pmc_df = pd.concat([gap_pmc_df, temp_gap_pmc_df], ignore_index=True)
            git_pmc_df = pd.concat([git_pmc_df, temp_git_pmc_df], ignore_index=True)
            # time.sleep(3)
    return nct_pmc_df, gap_pmc_df, git_pmc_df


def pmid_ls_to_pmc_info_df(pmid_ls, max_num = 100):
    if len(pmid_ls) > max_num:
        pmid_ls_temp = pmid_ls[0:max_num]
        # pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'full_txt', 'partial_txt', 'nct', 'start_idx'])
        nct_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'nct', 'full_txt', 'start_idx', 'partial_txt'])
        gap_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'dbgap', 'full_txt', 'start_idx', 'partial_txt'])
        git_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'github', 'full_txt', 'start_idx', 'partial_txt'])
        for batch in (pmid_ls[pos:pos + max_num] for pos in range(0, len(pmid_ls), max_num)):
            for i in batch:
                # temp_pmc_df = pmid_to_pmc_info_df(i)
                temp_nct_pmc_df, temp_gap_pmc_df, temp_git_pmc_df = pmid_to_pmc_info_df(i)
                # pmc_df = pd.concat([pmc_df, temp_pmc_df], ignore_index=True)
                nct_pmc_df = pd.concat([nct_pmc_df, temp_nct_pmc_df], ignore_index=True)
                gap_pmc_df = pd.concat([gap_pmc_df, temp_gap_pmc_df], ignore_index=True)
                git_pmc_df = pd.concat([git_pmc_df, temp_git_pmc_df], ignore_index=True)
    else:
        # pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'full_txt','partial_txt', 'nct', 'start_idx'])
        nct_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'nct', 'full_txt', 'start_idx', 'partial_txt'])
        gap_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'dbgap', 'full_txt', 'start_idx', 'partial_txt'])
        git_pmc_df = pd.DataFrame(columns=['pmid', 'pmc_id', 'github', 'full_txt', 'start_idx', 'partial_txt'])
        for i in pmid_ls:
            temp_nct_pmc_df, temp_gap_pmc_df, temp_git_pmc_df = pmid_to_pmc_info_df(i)
            # pmc_df = pd.concat([pmc_df, temp_pmc_df], ignore_index=True)
            nct_pmc_df = pd.concat([nct_pmc_df, temp_nct_pmc_df], ignore_index=True)
            gap_pmc_df = pd.concat([gap_pmc_df, temp_gap_pmc_df], ignore_index=True)
            git_pmc_df = pd.concat([git_pmc_df, temp_git_pmc_df], ignore_index=True)

    git_pmc_df['pmc_link'] = "https://www.ncbi.nlm.nih.gov/pmc/articles/" + git_pmc_df['pmc_id'] +'/'
    git_pmc_df['pubmed_link'] = "https://pubmed.ncbi.nlm.nih.gov/" + git_pmc_df['pmid'] +'/'
    gap_pmc_df['pmc_link'] = "https://www.ncbi.nlm.nih.gov/pmc/articles/" + gap_pmc_df['pmc_id'] +'/'
    gap_pmc_df['pubmed_link'] = "https://pubmed.ncbi.nlm.nih.gov/" + gap_pmc_df['pmid'] +'/'
    gap_pmc_df['dbgap_link'] = "https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id=" + gap_pmc_df['dbgap']
    nct_pmc_df['pmc_link'] = "https://www.ncbi.nlm.nih.gov/pmc/articles/" + nct_pmc_df['pmc_id'] +'/'
    nct_pmc_df['pubmed_link'] = "https://pubmed.ncbi.nlm.nih.gov/" + nct_pmc_df['pmid'] +'/'
    nct_pmc_df['ct_link'] = "https://www.clinicaltrials.gov/study/" + nct_pmc_df['nct'] +'/'
    
    git_pmc_df = git_pmc_df.drop_duplicates(subset=['pmid', 'github'], keep='first')
    gap_pmc_df = gap_pmc_df.drop_duplicates(subset=['pmid', 'dbgap'], keep='first')
    nct_pmc_df = nct_pmc_df.drop_duplicates(subset=['pmid', 'nct'], keep='first')
    return nct_pmc_df, gap_pmc_df, git_pmc_df


# takes one NCT ID and returns 
def get_clinical_trials_info(nct_id, pmid):
    response = requests.get(
            "".join([
                "https://clinicaltrials.gov/api/query/full_studies?expr=", nct_id ,"&fields=NCTId&fmt=JSON"
            ]),
        )
    response_json = response.json()
    # print(nct_id)
    returned_nct_id = response_json['FullStudiesResponse']['FullStudies'][0]['Study']['ProtocolSection']['IdentificationModule']['NCTId']
    ct_title = response_json['FullStudiesResponse']['FullStudies'][0]['Study']['ProtocolSection']['IdentificationModule']['OfficialTitle']
    ct_summary = response_json['FullStudiesResponse']['FullStudies'][0]['Study']['ProtocolSection']['DescriptionModule']['BriefSummary']
    
    ct_study_type = response_json['FullStudiesResponse']['FullStudies'][0]['Study']['ProtocolSection']['DesignModule']['StudyType'] #if observational/expanded access, doesnt have phase
    try:
    
        ct_phase = response_json['FullStudiesResponse']['FullStudies'][0]['Study']['ProtocolSection']['DesignModule']['PhaseList']['Phase']
    except:
        ct_phase = ct_study_type.split(',')
    ct_condition = response_json['FullStudiesResponse']['FullStudies'][0]['Study']['ProtocolSection']['ConditionsModule']['ConditionList']['Condition']
    ct_intervention_type = ''
    ct_intervention_name = ''
    ct_intervention = ''
    if ct_phase != ['Observational']:
        for i in response_json['FullStudiesResponse']['FullStudies'][0]['Study']['ProtocolSection']['ArmsInterventionsModule']['InterventionList']['Intervention']:
            ct_intervention_type = ct_intervention_type + i['InterventionType']+ ";"
            ct_intervention_name = ct_intervention_name + i['InterventionName'] + ";"
            ct_intervention = ct_intervention + f"{i['InterventionType']}: {i['InterventionName']};"
    else:
        ct_intervention_type = 'Observational'
        ct_intervention_name = 'Observational'
        ct_intervention = 'Observational'
    try:
        ct_keywords = response_json['FullStudiesResponse']['FullStudies'][0]['Study']['ProtocolSection']['ConditionsModule']['KeywordList']['Keyword']
    except:
        ct_keywords = ''
    # ct_link = f"https://clinicaltrials.gov/ct2/show/{nct_id}"
    ct_link = f"https://clinicaltrials.gov/study/{nct_id}"
    return pmid, nct_id, returned_nct_id, ct_title, ct_summary, ct_study_type, ct_phase, ct_condition, ct_intervention, ct_intervention_type, ct_intervention_name, ct_keywords, ct_link

# takes list of NCT IDs and returns dataframe 
def nctid_ls_to_clinical_trials_df(nctid_pmid_df):
    clinical_trials_df = pd.DataFrame(columns = ['pmid', 'nct_id', 'returned_nct_id', 'ct_title', 'ct_summary', 'ct_study_type', 'ct_phase', 'ct_condition', 'ct_intervention', 'ct_intervention_type', 'ct_intervention_name', 'ct_keywords', 'ct_link'])
    # for nct in nctid_ls:
    for idx, row in nctid_pmid_df.iterrows():
        pmid, nct_id, returned_nct_id, ct_title, ct_summary, ct_study_type, ct_phase, ct_condition, ct_intervention, ct_intervention_type, ct_intervention_name, ct_keywords, ct_link = get_clinical_trials_info(nct_id=row.nct, pmid=row.pmid )
        temp_row = {'pmid': pmid, 'nct_id': nct_id, 'returned_nct_id': returned_nct_id, 'ct_title': ct_title, 'ct_summary': ct_summary, 'ct_study_type': ct_study_type,'ct_phase': ct_phase, 'ct_condition': ct_condition, 'ct_intervention': ct_intervention, 'ct_intervention_type': ct_intervention_type, 'ct_intervention_name': ct_intervention_name, 'ct_keywords': ct_keywords,  'ct_link': ct_link}
        # clinical_trials_df = pd.concat([clinical_trials_df, temp_row], ignore_index=True)
        clinical_trials_df = clinical_trials_df.append(temp_row, ignore_index = True)
    clinical_trials_df['ct_phase'] = [';'.join(map(str, x)) for x in clinical_trials_df['ct_phase']]
    clinical_trials_df['ct_condition'] = [';'.join(map(str, x)) for x in clinical_trials_df['ct_condition']]
    clinical_trials_df['ct_keywords'] = [';'.join(map(str, x)) for x in clinical_trials_df['ct_keywords']]

    with resources.path('retrieverapp.terms', 'NCItm_synonyms_granularparent_1228.csv') as datafile:
        cts_df = pd.read_csv(datafile, low_memory=False)
    cts_terms = list(cts_df[(cts_df['abbrev'] != True) & (cts_df['Parent_name'] != 'Other')]['padlower'])
    
    clinical_trials_df['pad_conditions'] = clinical_trials_df['ct_condition'].str.replace('[^\w\s]', ' ').str.replace('  ', ' ')
    clinical_trials_df['pad_conditions'] = ' ' + clinical_trials_df['pad_conditions'] + ' '
    clinical_trials_df['pad_title'] = clinical_trials_df['ct_title'].str.replace('[^\w\s]', ' ').str.replace('  ', ' ')
    clinical_trials_df['pad_title'] = ' ' + clinical_trials_df['pad_title'] + ' '
    clinical_trials_df['pad_keywords'] = clinical_trials_df['ct_keywords'].str.replace('[^\w\s]', ' ').str.replace('  ', ' ')
    clinical_trials_df['pad_keywords'] = ' ' + clinical_trials_df['pad_keywords'] + ' '
    parent_ls = []
    for index, row in clinical_trials_df.iterrows():
        tags = [term for term in cts_terms if str(row['pad_conditions']).lower().find(term) > -1 or str(row['pad_title']).lower().find(term) > -1 or str(row['pad_keywords']).lower().find(term) > -1]
        parent_tags = []
        for x in list(set(tags)):
            try:
                parent_tags.append(cts_df[cts_df['padlower'] == x]['Parent_name'].values[0])
            except:
                # print('no tag, ct_condition: ', row.ct_condition)
                parent_tags.append('-')
        # print(set(parent_tags))
        parent_ls.append(list(set(parent_tags)))

    clinical_trials_df = clinical_trials_df.assign(ct_cancer_types_tagged = parent_ls)
    clinical_trials_df = clinical_trials_df.drop(columns=['pad_conditions', 'pad_title', 'pad_keywords'])
    clinical_trials_df['ct_cancer_types_tagged'] = [';'.join(map(str, x)) for x in clinical_trials_df['ct_cancer_types_tagged']]
    return clinical_trials_df

## this is for scraping dbgap data 
def scrape_study_info(url):
    try:
        response = requests.get(url)

        if response.status_code == 200:
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            title = soup.find('span', {'name': 'study-name'}).get_text()

            study_description_dd = soup.find('dt', text='Study Description').find_next('dd')
            study_description_p_tags = study_description_dd.find_all('p')
            description = study_description_p_tags[1].get_text()

            molecular_data_dt = soup.find('dt', text='Molecular Data')
            molecular_data = ""

            if molecular_data_dt:
                table = molecular_data_dt.find_next('table')

                if table:
                    rows = table.find_all('tr')
                    for row in rows[1:]:  # Start from the second row to skip the header row
                        cells = row.find_all('td')
                        if cells:
                            first_column_text = cells[0].get_text()
                            molecular_data += first_column_text + "; "
            molecular_data = molecular_data.strip("; ")
            return {
                "title": title,
                "description": description,
                "molecular_data": molecular_data,
                "url":url
            }

        else:
            return {"error": "Failed to retrieve the web page. Status code: " + str(response.status_code)}

    except Exception as e:
        return {"error": str(e)}

def scrape_multiple_studies(urls):
    data = []

    for url in urls:
        study_info = scrape_study_info(url)
        if "error" not in study_info:
            data.append({
                "url": url,
                "data_title": study_info["title"],
                "data_summary": study_info["description"],
                "library_strategy": study_info["molecular_data"]
            })

    df = pd.DataFrame(data)
    return df


## github search:
def extract_username_and_repo(url):
    match = re.search(r'github\.com/([^/]+)/([^/]+)', url)
    if match:
        username = match.group(1)
        repository = match.group(2)
        return username, repository
    else:
        return None, None
def extract_github_info(dataframe):
    repo_info = []

    for index, row in dataframe.iterrows():
        time.sleep(2)
        github_url = row['github']
        username, repository = extract_username_and_repo(github_url)

        if username and repository:
            response = requests.get(f'https://api.github.com/repos/{username}/{repository}')
            if response.status_code == 403:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                wait_time = reset_time - int(time.time()) + 1  # Add 1 second to be safe

                print(f'Received 403 error. Waiting for {wait_time} seconds until rate limit reset.')
                time.sleep(wait_time)
                
                response = requests.get(f'https://api.github.com/repos/{username}/{repository}')

            if response.status_code == 200:
                data = response.json()

                repo_name = data['name']
                description = data.get('description', 'N/A')

                try:
                    license_name = data['license']['name']
                except (KeyError, TypeError):
                    license_name = 'N/A'

                releases_response = requests.get(f'https://api.github.com/repos/{username}/{repository}/releases/latest')
                if releases_response.status_code == 403:
                    reset_time = int(releases_response.headers['X-RateLimit-Reset'])
                    wait_time = reset_time - int(time.time()) + 1  # Add 1 second to be safe

                    print(f'Received 403 error. Waiting for {wait_time} seconds until rate limit reset.')
                    time.sleep(wait_time)
                    releases_response = requests.get(f'https://api.github.com/repos/{username}/{repository}/releases/latest')
                    releases_data = releases_response.json()
                    version = releases_data['tag_name']

                if releases_response.status_code == 200:
                    releases_data = releases_response.json()
                    version = releases_data['tag_name']
                else:
                    version = 'N/A'

                repo_info.append([row['pmid'], row['github'], repo_name, description, license_name, version])
            else:
                print(f'Failed to retrieve repository information for {github_url}. Status code: {response.status_code}')
        else:
            print(f'Invalid GitHub URL: {github_url}, data for this URL not retrieved')

    columns = ['pmid', 'github_link', 'repo_name', 'description', 'license', 'version']
    result_df = pd.DataFrame(repo_info, columns=columns)
    return result_df


# example usage
if __name__ == "__main__":
    # pubs, data = grant_to_output(['32571799'], output_file='grant_output', write=True, id_type = 'pmid_list')
    pubs, data = grant_to_output(['U01DE029255'])
    print(pubs.head())
    print(data.head())
