#!/usr/bin/env python3
"""
SEO Content Gap Analysis Tool
==============================
Advanced competitive intelligence system for identifying keyword opportunities
Author: Damilare Lekan Adekeye
Client: WhiteLabelResell
"""

import json
import os
import logging
import uuid
import boto3
import requests
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
import pandas as pd
from tabulate import tabulate

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DataForSEO API Configuration
API_USERNAME = "your_email"
API_PASSWORD = "your_password"
API_AUTH = "Basic Y2hyaXN***************************mE5ZjM3ODhlMTgyOGRlNDU="  # Redacted for security

# API Endpoints
DOMAIN_INTERSECTION_ENDPOINT = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_intersection/live"
RANKED_KEYWORDS_ENDPOINT = "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live"

# Headers for API requests
HEADERS = {
    "Authorization": API_AUTH,
    "Content-Type": "application/json"
}

# AWS DynamoDB Configuration (when deployed)
# dynamodb = boto3.resource('dynamodb')
# dynamodb_client = boto3.client('dynamodb')
# DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE')
# table = dynamodb.Table(DYNAMODB_TABLE)


def get_data_from_api(endpoint, payload, headers):
    """
    Make API request to DataForSEO and retrieve data.
    
    Args:
        endpoint: API endpoint URL
        payload: Request payload
        headers: Request headers including authentication
        
    Returns:
        List of items from API response
    """
    try:
        response = requests.post(endpoint, headers=headers, data=payload)
        
        if response.status_code == 200:
            result = response.json()
            items = result.get('tasks', [])[0].get('result', [])[0].get('items', [])
            return items
        else:
            print(f"Error: {response.status_code}, {response.text}")
            return []
            
    except Exception as e:
        print(f"Error fetching data from API: {e}")
        return []


def get_keywords(domain):
    """
    Retrieve ranked keywords for a specific domain.
    
    Args:
        domain: Target domain to analyze
        
    Returns:
        List of keyword data with metrics
    """
    url = RANKED_KEYWORDS_ENDPOINT
    
    payload = json.dumps([{
        "target": domain,
        "location_code": 2840,  # US location code
        "language_code": "en",
        "ignore_synonyms": False,
        "include_clickstream_data": False,
        "limit": 200
    }])
    
    headers = {
        'Authorization': API_AUTH,
        'Content-Type': 'application/json'
    }
    
    return get_data_from_api(url, payload, headers)


def extract_keyword_info(df, domain_list):
    """
    Extract and process keyword information from raw API data.
    
    Args:
        df: DataFrame with raw keyword data
        domain_list: List of domains to process
        
    Returns:
        Processed DataFrame with keyword metrics
    """
    if df.empty:
        print("Warning: Empty DataFrame passed to extract_keyword_info")
        return pd.DataFrame()
    
    # Extract core keyword metrics
    df['keyword'] = df['keyword_data'].apply(
        lambda x: x.get('keyword', "N/A") if isinstance(x, dict) else "N/A"
    )
    df['search_volume'] = df['keyword_data'].apply(
        lambda x: x.get('keyword_info', {}).get('search_volume', 0) if isinstance(x, dict) else 0
    )
    df['Keyword_Difficulty'] = df['keyword_data'].apply(
        lambda x: x.get('keyword_properties', {}).get('keyword_difficulty', 0) if isinstance(x, dict) else 0
    )
    df['CPC'] = df['keyword_data'].apply(
        lambda x: x.get('keyword_info', {}).get('cpc', 0) 
        if isinstance(x, dict) and x.get('keyword_info', {}).get('cpc') is not None else 0
    )
    df['last_updated_time'] = df['keyword_data'].apply(
        lambda x: x.get('keyword_info', {}).get('last_updated_time', "N/A") if isinstance(x, dict) else "N/A"
    )
    
    # Handle domain-specific values
    for domain in domain_list:
        df[f"{domain}_Position"] = df['keyword_data'].apply(
            lambda x: x.get('avg_backlinks_info', {}).get('rank', 0) 
            if isinstance(x, dict) and x.get('avg_backlinks_info') else 0
        )
        df[f"{domain}_Traffic"] = df['ranked_serp_element'].apply(
            lambda x: x.get('serp_item', {}).get('etv', 0) 
            if isinstance(x, dict) and x.get('serp_item') else 0
        )
    
    # Select relevant columns
    columns_to_keep = ['keyword', 'search_volume', 'Keyword_Difficulty', 'CPC', 'last_updated_time'] + \
                      [f"{domain}_Position" for domain in domain_list] + \
                      [f"{domain}_Traffic" for domain in domain_list]
    
    return df[columns_to_keep]


def content_gap_analysis(competitors, my_domain):
    """
    Perform comprehensive content gap analysis between your domain and competitors.
    
    Args:
        competitors: List of competitor domains to analyze
        my_domain: Your primary domain for comparison
        
    Returns:
        Dictionary containing analysis results, matrices, and DataFrames
    """
    # Get keywords for your domain
    print(f"Retrieving keywords for {my_domain}")
    my_keywords_df = pd.DataFrame(get_keywords(my_domain))
    
    if my_keywords_df.empty:
        print(f"Error: Could not retrieve keywords for {my_domain}")
        return None
    
    # Extract and process keyword data
    my_domain_list = [my_domain]
    my_keywords_df = extract_keyword_info(my_keywords_df, my_domain_list)
    my_keywords_df['keyword'] = my_keywords_df['keyword'].str.lower().str.strip()
    
    # Display results in tabular format
    columns = ['keyword', 'search_volume', 'Keyword_Difficulty', 'CPC', 
               'last_updated_time', f"{my_domain}_Position", f"{my_domain}_Traffic"]
    print(tabulate(my_keywords_df[columns], headers="keys", tablefmt="plain"))
    print("\n\n")
    
    # Store all keywords from the domain
    all_keywords = {my_domain: my_keywords_df}
    common_keywords = {}
    
    # Process each competitor
    for competitor in competitors:
        print(f"Retrieving keywords for competitor: {competitor}")
        competitor_df = pd.DataFrame(get_keywords(competitor))
        
        if not competitor_df.empty:
            competitor_df = extract_keyword_info(competitor_df, competitors)
            
            columns = ['keyword', 'search_volume', 'Keyword_Difficulty', 'CPC',
                      'last_updated_time', f"{competitor}_Position", f"{competitor}_Traffic"]
            print(tabulate(competitor_df[columns], headers="keys", tablefmt="plain"))
            print("\n\n")
            
            competitor_df['keyword'] = competitor_df['keyword'].str.lower().str.strip()
            all_keywords[competitor] = competitor_df
            
            # Find common keywords
            common_keywords[competitor] = my_keywords_df[
                my_keywords_df['keyword'].isin(competitor_df['keyword'])
            ]
        else:
            print(f"Warning: No keywords retrieved for competitor {competitor}")
    
    # Create common keywords matrix
    domain_names = [my_domain] + competitors
    common_keywords_matrix = pd.DataFrame(index=domain_names, columns=domain_names)
    
    # Calculate common keywords between each pair of domains
    for domain1 in domain_names:
        for domain2 in domain_names:
            if domain1 == domain2:
                common_count = len(all_keywords[domain1])
            else:
                common_keywords_set = set(all_keywords[domain1]['keyword']).intersection(
                    set(all_keywords[domain2]['keyword'])
                )
                common_count = len(common_keywords_set)
            
            common_keywords_matrix.at[domain1, domain2] = common_count
    
    # Display the matrix
    print("Common Keywords Matrix (Count of Common Keywords between Domains):")
    print(common_keywords_matrix)
    print("\n\n")
    
    # Prepare DataFrames
    all_keywords_df = pd.concat(all_keywords.values(), ignore_index=True)
    common_keywords_df = pd.concat(common_keywords.values(), ignore_index=True)
    
    # Display results
    print("All Keywords DataFrame:")
    print(tabulate(all_keywords_df.head(5), headers="keys", tablefmt="grid"))
    print("\n\n")
    
    print("Common Keywords DataFrame:")
    print(common_keywords_df.head())
    print("\n\n")
    
    # Return comprehensive results
    result = {
        'all_keywords_df': all_keywords_df,
        'common_keywords_df': common_keywords_df,
        'common_keywords_matrix': common_keywords_matrix
    }
    
    return result


def save_or_update_dynamo_db(data, targets1, targets2, id, userid, product):
    """
    Save or update analysis results in AWS DynamoDB.
    
    Args:
        data: Analysis results to store
        targets1: Primary domain
        targets2: Competitor domains
        id: Record ID
        userid: User ID
        product: Product identifier
        
    Returns:
        Audit ID or existing ID
    """
    audit_id = f"Competitor Audit_{targets1} & {targets2}_{uuid.uuid4()}"
    current_timestamp = datetime.utcnow().isoformat()
    
    try:
        # Check if the item exists
        response = table.get_item(Key={'id': id, 'UserId': userid})
        item_exists = 'Item' in response
        
        if item_exists:
            # Update existing item
            logger.info(f"Item with id {id} exists. Updating the specified attributes.")
            response = table.update_item(
                Key={'id': id, 'UserId': userid},
                UpdateExpression=(
                    "SET KPIData_content_gap = :content_gap, "
                    "Product = :product"
                ),
                ExpressionAttributeValues={
                    ':content_gap': json.dumps(data),
                    ':product': product,
                },
                ReturnValues="UPDATED_NEW"
            )
            logger.info(f"Item updated successfully: {id}")
            return id
        else:
            # Create new item
            logger.info(f"Item with id {id} does not exist. Creating a new item.")
            item = {
                'id': {'S': id},
                'UserId': {'S': userid},
                'Product': {'S': product},
                'AuditId': {'S': audit_id},
                'KPIData_keyword_trends': {'S': ""},
                'KPIData_content_gap': {'S': json.dumps(data)},
                'Your Domain': {'S': targets1},
                'Competitor Domains': {'S': targets2},
                'CreatedAt': {'S': current_timestamp}
            }
            dynamodb_client.put_item(TableName=DYNAMODB_TABLE, Item=item)
            logger.info(f"Item created successfully: {id}")
            return audit_id
            
    except Exception as e:
        logger.error(f"Error in save_or_update_dynamo_db: {e}")
        return None


# Example usage
if __name__ == "__main__":
    # Define your domain and competitors
    my_domain = "dataforseo.com"
    competitors = ["ahrefs.com", "seranking.com", "semrush.com"]
    
    print("Starting content gap analysis...")
    result = content_gap_analysis(competitors, my_domain)
    
    if result:
        print("Content Gap Analysis completed successfully!")
        print(f"Total keywords analyzed: {len(result['all_keywords_df'])}")
        print(f"Common keywords found: {len(result['common_keywords_df'])}")
