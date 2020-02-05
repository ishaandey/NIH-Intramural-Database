#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 23 11:43:09 2020

@author: ishaandey
"""
#%%
import os
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup
import re

import pandas as pd
import numpy as np

import random
import time

#%%
verbose = input('>>Set verbosity [Y/N]: ').upper().strip()

#%%
# Open up the chrome webdriver locally and navigate to webpage
browser = webdriver.Chrome('/usr/local/bin/chromedriver')
browser.get('https://intramural.nih.gov/search/index.taf')

#%%
if verbose == 'Y': os.system("say Ready to read in content")
print('Navigate to selected year & institution via chromedriver and click "List"')
year = input('>>Enter year selected: ')
dept = input('>>Enter dept selected: ').upper().strip()
wait = input('>>Press enter to confirm page has loaded: ')
print()

#%%
# Read in html of current page w/ projects listed
html_pg = browser.page_source

# Extract all urls
regex_code = r'(https://intramural.nih.gov/search/searchview.taf\?ipid=[\d]{3,15})(?=</a>)'
urls = re.findall(regex_code, html_pg, re.I|re.M|re.S) 

#%%
def show_more(type_):
    """
    Helper function that clicks on any of the "show more" links 
    """
    global browser    
    xpath_ = '//*[@id="{}"]/div/div[3]/div/a/span'.format(type_)
    try:    
        browser.find_element_by_xpath(xpath_).click()
    except:
        print('Warning! Unable to click show more xpath')


def extract_content(url):
    """
    Function that mines the content of a webpage for a given url
    Returns a dictionary in the format {field:data}
    """    
    
    global browser
    browser.get(url)
    
    html = browser.page_source
    soup = BeautifulSoup(html, features='lxml')

    if 'class="morelist"' in html:
        # Find out what the sections the morelists are
        regex_ = r"(?<=href=\"#\" onclick=\"runthis\(')(.+?)(?=','searchview\.taf\?)"
        all_morelists =  re.findall(regex_, html)
        
        # Don't try to click on publications, those are already all there
        try:
            all_morelists.remove('publications')
        except ValueError:
            all_morelists
        
        # Open up each link for a given section of type_ = i 
        for i in all_morelists:
            show_more(type_=i)
    
        
    # Parse through rowdivs to get key and value pair (class = headings & data)
    content_heading = soup.find_all(class_ = 'headings')
    content_data    = soup.find_all(class_ = 'data')

    content_heading_t = [f.text.strip() for f in content_heading]
    content_data_t    = [f.text.strip() for f in content_data]
        
    content_dict = dict(zip(content_heading_t, content_data_t))
    
    # Append the project ID and URL to the dict
    regex_ = r'(?<=<div class=\"contentlabel\">)(.*?)(?=</div>)'
    content_dict['Project ID'] = re.search(regex_, html)[0]
    content_dict['Project URL'] = url
    
    return content_dict    


def standardize_project(project, dept='NCI'):
    """
    Function that standardizes the column names of each project
    It also fills in empty columns
    Input: Project as a dict
    Returns project as a better formatted dict
    """
    # Creates a dict that maps original to new col names
    regex_lookup = {'project_id':r'Project ID',
                    'fiscal_year':r'Fiscal Year',
                    'report_title':r'Report Title',
                    'principal_investigator':r'Investigator',
                    'supervisor':r'Supervisor',
                    'research_org':r'Research Organization',
                    'lab_staff_within_org':r'Lab Staff and Collaborators within',
                    'collab_other_NCI':r'Collaborators from other {}'.format(dept),
                    'collab_other_NIH':r'Collaborators from other NIH',
                    'extramural_collab':r'Extramural Collaborator',
                    'keywords':r'Keywords',
                    'goals_and_obj':r'Goals and Objectives',
                    'summary':r'Summary',
                    'publications':r'Publications Generated',
                    'url':r'Project URL',
                    }
    
    if len(project) > len(regex_lookup):
        print('\nWARNING: ',len(project.keys()))
        print(project['Project URL'])
    
    # Use regex to see if there is a key that matches the field
        # If it does, append it using field to the new_project dict
        # Otherwise, append that field name and set value to 'NULL'
    
    new_project = {}
    for field, regex_ in regex_lookup.items():
        for desc in project.keys():
            # matches = re.search(regex_, desc, re.IGNORECASE)
            if regex_.lower() in desc.lower():
                new_project[field] = project[desc]
#                regex_lookup.pop(field)
                # break out of current for loop and move to next field
                
        if field not in new_project.keys():
            new_project[field] = 'NULL'
            
    return new_project
        
#%%
content = [extract_content(u) for u in urls]
std_content = [standardize_project(p, dept) for p in content]
df_raw = pd.DataFrame.from_dict(std_content, orient='columns')
df_raw = df_raw[['project_id', 'fiscal_year', 'report_title', 
                 'principal_investigator', 'supervisor', 'research_org',
                 'lab_staff_within_org', 'extramural_collab', 
                 'collab_other_NCI', 'collab_other_NIH', 
                 'publications', 'url']]

path = '/Users/ishaandey/Documents/AmanRanaLab/NIDB'
df_raw.to_csv('{p}/raw_data_{yr}.csv'.format(p=path,yr=year))
browser.close()

#%%

def clean_publications(x, for_csv=False, delimiter='\n'):    
    # Check if there are no publications in the given entry (x)
    empty_pubs = ['There were no publications during this reporting period',
                  'There were no publications associated with this project',
                  'NULL']
        # To check if there are others missed here, use: 
        # df_raw.publications.apply(lambda x: x.split('\n')[0]).value_counts()
    # Return NULL for entries w/ no publications for the current reporting period
    if x.split('\n')[0] in empty_pubs:
        if for_csv:
            return 'NULL'
        else:
            return ['NULL']
    
    # Use regex to identify citations
    else:
        regex_ = r"^\d{1,2}\.\n.*?$"
        matches = re.findall(regex_, x, re.IGNORECASE|re.MULTILINE)
        # Return publications as newline seperated if data is for csv
        if for_csv:
            return delimiter.join([m.replace('\n',' ') for m in matches])
        # Otherwise the dtype of the series should remain as a object (lists) 
        else:
            return [m.replace('\n',' ') for m in matches]


def clean_collaborators(x, for_csv=False, delimiter='\n'):
    collaborators = [c.replace('\n',' ') for c in re.split(r'\n{2,}', x)]
    if for_csv:
        return delimiter.join(collaborators)
    else:
        return collaborators
    
#%%   
df = df_raw.copy(deep=True)
for_csv = True
delimiter = '|'

df['publications'] = df_raw.publications.apply(clean_publications, 
                                               args=(for_csv, delimiter))
collab_fields = ['lab_staff_within_org','collab_other_NCI', 'collab_other_NIH',
                 'extramural_collab', 'principal_investigator']
for field in collab_fields:
    df[field] = df_raw[field].apply(clean_collaborators, args=(for_csv, delimiter))
        
    
df = df[['project_id', 'fiscal_year', 'report_title', 'principal_investigator', 
         'supervisor', 'research_org', 'lab_staff_within_org', 'extramural_collab', 
         'collab_other_NCI', 'collab_other_NIH', 'publications', 'url']]

df.to_csv('{p}/cleaned_data_{yr}.csv'.format(p=path,yr=year))
    

#%%
if verbose != 'N': os.system("say kaam hoeguyah baanchode")