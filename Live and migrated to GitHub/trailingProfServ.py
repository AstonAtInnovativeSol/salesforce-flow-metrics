#!/usr/bin/env python3
"""
Weekly Pipeline Snapshot (YTD) - Professional Services Only
Syncs opportunities to Weekly_Pipeline_Summary__c

JWT Authentication Setup:
    This script uses JWT (JSON Web Token) Bearer authentication to connect to Salesforce.
    
    Required Configuration (in sf_config.py - NOT committed to GitHub):
    - SF_USERNAME: Your Salesforce username (e.g., 'user@example.com')
    - SF_CONSUMER_KEY: Connected App Consumer Key from Salesforce
    - SF_DOMAIN: 'login' for production, 'test' for sandbox
    - PRIVATE_KEY_FILE: Path to your RSA private key file (.pem)
    
    See sf_config.py.example for template and setup instructions.
    Security Note: sf_config.py is gitignored and will NOT be committed to GitHub
"""

import os
import time
import jwt
import requests
import pandas as pd
from datetime import datetime, timedelta
from simple_salesforce import Salesforce, SalesforceMalformedRequest
import sf_config

# ==========================================================
# AUTHENTICATION - JWT Bearer Token Flow
# ==========================================================
# This script uses JWT (JSON Web Token) Bearer authentication, which is more secure
# than username/password authentication and doesn't require interactive login.
#
# How JWT Authentication Works:
# 1. Generate a JWT token using your private key and credentials
# 2. Send the JWT token to Salesforce OAuth token endpoint
# 3. Salesforce validates the token and returns an access token
# 4. Use the access token for API calls (automatically handled by simple_salesforce)
#
# Required from sf_config.py:
# - SF_CONSUMER_KEY: Connected App Consumer Key (acts as "issuer")
# - SF_USERNAME: Salesforce username (acts as "subject")
# - SF_DOMAIN: 'login' for production or 'test' for sandbox
# - PRIVATE_KEY_FILE: Path to RSA private key that matches the certificate
#                     uploaded to your Connected App
#
def get_jwt_token():
    """
    Generate JWT token for Salesforce authentication using RS256 algorithm.
    
    Returns:
        dict: Token response containing 'access_token' and 'instance_url'
    
    Raises:
        Exception: If authentication fails (invalid credentials, expired token, etc.)
    
    Note:
        - Token expires in 300 seconds (5 minutes)
        - Private key is read from file specified in sf_config.PRIVATE_KEY_FILE
        - Ensure the private key matches the certificate in your Connected App
    """
    # Read the RSA private key file
    with open(sf_config.PRIVATE_KEY_FILE, "r") as key_file:
        private_key = key_file.read()

    # Build JWT claim (payload) with required Salesforce fields
    claim = {
        "iss": sf_config.SF_CONSUMER_KEY,  # Issuer: Your Connected App Consumer Key
        "sub": sf_config.SF_USERNAME,      # Subject: Your Salesforce username
        "aud": f"https://{sf_config.SF_DOMAIN}.salesforce.com",  # Audience: Salesforce login URL
        "exp": int(time.time()) + 300,      # Expiration: 5 minutes from now
    }

    # Encode the JWT token using RS256 algorithm (RSA signature)
    assertion = jwt.encode(claim, private_key, algorithm="RS256")

    # Exchange JWT assertion for access token
    token_url = f"https://{sf_config.SF_DOMAIN}.salesforce.com/services/oauth2/token"
    params = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",  # JWT Bearer grant type
        "assertion": assertion,  # The JWT token we just created
    }

    # Make the OAuth token request
    response = requests.post(token_url, data=params)

    if response.status_code == 200:
        return response.json()  # Returns {access_token, instance_url, etc.}
    else:
        raise Exception(f"❌ Authentication failed: {response.text}")


def connect_to_salesforce():
    """Authenticate and return a Salesforce connection"""
    print("\nAuthenticating with Salesforce via JWT...")
    token_data = get_jwt_token()
    access_token = token_data["access_token"]
    instance_url = token_data["instance_url"]

    sf = Salesforce(instance_url=instance_url, session_id=access_token)
    print("✅ Connected successfully!\n")
    return sf


# ==========================================================
# QUERY OPPORTUNITIES BY WEEK (PROFESSIONAL SERVICES ONLY)
# ==========================================================
def get_weekly_pipeline_data(sf):
    """Query opportunities and aggregate by week of creation (YTD) - Professional Services ONLY"""
    current_year = datetime.today().year
    start_date = f"{current_year}-01-01T00:00:00Z"
    
    print(f"Querying opportunities created YTD (since {start_date[:10]})...")
    print("📌 FILTERING: Professional_Services_Amount__c only (excluding ARR/Resold)")
    
    query = f"""
        SELECT Id, 
               CreatedDate,
               Professional_Services_Amount__c
        FROM Opportunity
        WHERE CreatedDate >= {start_date}
          AND Professional_Services_Amount__c != NULL
          AND Professional_Services_Amount__c > 0
        ORDER BY CreatedDate ASC
    """
    
    try:
        records = sf.query_all(query)["records"]
        print(f"✅ Found {len(records)} opportunities with Professional Services revenue")
        
        if not records:
            print("⚠️ No opportunity data found.")
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df = df[['Id', 'CreatedDate', 'Professional_Services_Amount__c']]
        
        # Rename for consistency
        df = df.rename(columns={'Professional_Services_Amount__c': 'Amount'})
        
        df['CreatedDate'] = pd.to_datetime(df['CreatedDate'])
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
        
        df['Week_Start'] = df['CreatedDate'].dt.to_period('W').dt.start_time
        df['Week_Number'] = df['CreatedDate'].dt.isocalendar().week
        df['Year'] = df['CreatedDate'].dt.year
        
        return df
        
    except Exception as e:
        print(f"❌ Error querying opportunities: {e}")
        return pd.DataFrame()


# ==========================================================
# AGGREGATE BY WEEK
# ==========================================================
def aggregate_by_week(df):
    """Aggregate opportunity amounts by week"""
    print("\nAggregating pipeline by week...")
    
    if df.empty:
        return pd.DataFrame()
    
    weekly_summary = df.groupby(['Week_Start', 'Week_Number', 'Year']).agg({
        'Amount': 'sum'
    }).reset_index()
    
    weekly_summary.columns = ['Week_Start_Date', 'Week_Number', 'Year', 'Total_Pipeline_Created']
    weekly_summary = weekly_summary.sort_values('Week_Start_Date', ascending=True)
    
    print(f"✅ Aggregated to {len(weekly_summary)} weeks")
    
    return weekly_summary


# ==========================================================
# CALCULATE 6-WEEK TRAILING AVERAGE
# ==========================================================
def calculate_trailing_average(df, window=6):
    """Calculate 6-week trailing average (current week + 5 prior weeks)"""
    print(f"\nCalculating {window}-week trailing average...")
    
    if df.empty:
        return df
    
    df['Six_Week_Trailing_Average'] = df['Total_Pipeline_Created'].rolling(
        window=window, 
        min_periods=1
    ).mean()
    
    print(f"✅ Trailing averages calculated")
    
    return df


# ==========================================================
# GET EXISTING RECORDS FROM SALESFORCE
# ==========================================================
def get_existing_records(sf):
    """Retrieve all existing Weekly_Pipeline_Summary__c records"""
    print("\nFetching existing records from Weekly_Pipeline_Summary__c...")
    
    query = """
        SELECT Id, Week_Start_Date__c, Week_Number__c, Year__c
        FROM Weekly_Pipeline_Summary__c
    """
    
    try:
        records = sf.query_all(query)["records"]
        print(f"✅ Found {len(records)} existing records")
        
        # Create a lookup dictionary: (year, week_number) -> record_id
        existing_lookup = {}
        for record in records:
            year = int(record['Year__c'])
            week_num = int(record['Week_Number__c'])
            existing_lookup[(year, week_num)] = record['Id']
        
        return existing_lookup
        
    except Exception as e:
        print(f"❌ Error fetching existing records: {e}")
        return {}


# ==========================================================
# UPSERT TO SUMMARY OBJECT
# ==========================================================
def upsert_to_summary_object(sf, summary_df, existing_lookup):
    """Upsert (update or create) aggregated data to Weekly_Pipeline_Summary__c"""
    print("\n======================================================================")
    print("UPSERTING TO WEEKLY_PIPELINE_SUMMARY__C")
    print("======================================================================")
    
    if summary_df.empty:
        print("⚠️ No data to write")
        return 0, 0
    
    created, updated = 0, 0
    
    for _, row in summary_df.iterrows():
        week_start_date = row['Week_Start_Date']
        year = int(row['Year'])
        week_number = int(row['Week_Number'])
        
        record_data = {
            "Week_Start_Date__c": week_start_date.strftime('%Y-%m-%d'),
            "Week_Number__c": float(week_number),
            "Year__c": float(year),
            "Total_Pipeline_Created__c": float(row['Total_Pipeline_Created']),
            "Six_Week_Trailing_Average__c": float(row['Six_Week_Trailing_Average'])
        }
        
        # Check if record exists
        record_key = (year, week_number)
        
        try:
            if record_key in existing_lookup:
                # UPDATE existing record
                record_id = existing_lookup[record_key]
                sf.Weekly_Pipeline_Summary__c.update(record_id, record_data)
                updated += 1
                print(f"   ↻ Updated {year}-W{week_number:02d}")
            else:
                # CREATE new record
                result = sf.Weekly_Pipeline_Summary__c.create(record_data)
                created += 1
                print(f"   ✓ Created {year}-W{week_number:02d}")
                
        except Exception as e:
            print(f"   ✗ Error upserting {year}-W{week_number:02d}: {e}")
    
    print(f"\n📊 Summary: Created {created}, Updated {updated}")
    return created, updated


# ==========================================================
# DISPLAY PREVIEW
# ==========================================================
def display_preview(df):
    """Display preview of weekly pipeline data"""
    if df.empty:
        print("No data to preview")
        return
    
    print("\n======================================================================")
    print("WEEKLY PIPELINE PREVIEW (Last 10 weeks)")
    print("======================================================================")
    
    for _, row in df.tail(10).iterrows():
        week_str = row['Week_Start_Date'].strftime('%Y-%m-%d')
        year = int(row['Year'])
        week_num = int(row['Week_Number'])
        pipeline_str = f"${row['Total_Pipeline_Created']:,.2f}"
        avg_str = f"${row['Six_Week_Trailing_Average']:,.2f}"
        print(f"{year}-W{week_num:02d} ({week_str}): {pipeline_str} | 6-wk avg: {avg_str}")


# ==========================================================
# MAIN
# ==========================================================
def main():
    print("\n======================================================================")
    print("WEEKLY PIPELINE SNAPSHOT (YTD) - PROFESSIONAL SERVICES ONLY")
    print("Opportunities → Weekly_Pipeline_Summary__c")
    print("======================================================================")

    # Connect to Salesforce
    sf = connect_to_salesforce()
    
    # Get existing records
    existing_lookup = get_existing_records(sf)
    
    # Query opportunity data (YTD) - Professional Services only
    opp_df = get_weekly_pipeline_data(sf)
    
    if opp_df.empty:
        print("\n⚠️ No opportunity data found. Exiting.")
        return
    
    # Aggregate by week
    weekly_summary = aggregate_by_week(opp_df)
    
    # Calculate 6-week trailing average
    weekly_summary = calculate_trailing_average(weekly_summary, window=6)
    
    # Display preview
    display_preview(weekly_summary)
    
    # Upsert to Weekly_Pipeline_Summary__c
    created, updated = upsert_to_summary_object(sf, weekly_summary, existing_lookup)
    
    print("\n======================================================================")
    print("✅ SYNC COMPLETE")
    print("======================================================================")
    print(f"\n📈 Records created: {created}")
    print(f"📈 Records updated: {updated}")


if __name__ == "__main__":
    main()
