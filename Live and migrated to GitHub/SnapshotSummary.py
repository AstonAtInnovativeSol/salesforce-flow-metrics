#!/usr/bin/env python3
"""
Pipeline Snapshot Summary Sync
Syncs data from Daily_Total_Pipeline__c to Pipeline_Snapshot_Summary__c

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
import sf_config  # ← your config file with credentials

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
# QUERY REPORTING SNAPSHOT DATA
# ==========================================================
def get_snapshot_data(sf, days_back=90):
    """Query existing snapshot records from Daily_Total_Pipeline__c"""
    print(f"Querying snapshot data from Daily_Total_Pipeline__c (last {days_back} days)...")
    
    start_date = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    query = f"""
        SELECT Id, Name, 
               Snapshot_Date__c, 
               Snapshot_Created_Date__c,
               Total_Open_Pipeline__c, 
               Opportunity_Count__c,
               Total_Number_of_Open_Opps__c,
               Average_Opp_Age__c,
               CreatedDate
        FROM Daily_Total_Pipeline__c
        WHERE Snapshot_Created_Date__c >= {start_date}
        ORDER BY Snapshot_Created_Date__c DESC
    """
    
    try:
        records = sf.query_all(query)["records"]
        print(f"✅ Found {len(records)} snapshot records")
        
        if not records:
            print("⚠️ No snapshot data found. Make sure your Reporting Snapshot is running.")
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        
        # Clean up the data
        df["Snapshot_Date__c"] = pd.to_datetime(df["Snapshot_Date__c"]).dt.date
        df["Total_Open_Pipeline__c"] = pd.to_numeric(df["Total_Open_Pipeline__c"], errors="coerce").fillna(0)
        df["Opportunity_Count__c"] = pd.to_numeric(df["Opportunity_Count__c"], errors="coerce").fillna(0)
        df["Average_Opp_Age__c"] = pd.to_numeric(df["Average_Opp_Age__c"], errors="coerce").fillna(0)
        
        return df
        
    except Exception as e:
        print(f"❌ Error querying snapshot data: {e}")
        return pd.DataFrame()


# ==========================================================
# AGGREGATE DAILY TOTALS
# ==========================================================
def aggregate_daily_totals(df):
    """Aggregate snapshot data by date (in case there are multiple records per day)"""
    print("\nAggregating daily totals...")
    
    if df.empty:
        return pd.DataFrame()
    
    # Group by Snapshot_Date__c and aggregate
    daily_summary = df.groupby("Snapshot_Date__c").agg({
        "Total_Open_Pipeline__c": "sum",
        "Opportunity_Count__c": "sum",
        "Average_Opp_Age__c": "mean"
    }).reset_index()
    
    daily_summary = daily_summary.sort_values("Snapshot_Date__c", ascending=False)
    
    print(f"✅ Aggregated to {len(daily_summary)} unique dates")
    
    return daily_summary


# ==========================================================
# DISPLAY PREVIEW
# ==========================================================
def display_preview(df):
    """Display preview of snapshot data"""
    if df.empty:
        print("No data to preview")
        return
    
    print("\n======================================================================")
    print("SNAPSHOT DATA PREVIEW (Last 10 days)")
    print("======================================================================")
    
    for _, row in df.head(10).iterrows():
        date_str = row["Snapshot_Date__c"]
        total_str = f"${row['Total_Open_Pipeline__c']:,.2f}"
        count = int(row['Opportunity_Count__c'])
        avg_age = row['Average_Opp_Age__c']
        print(f"{date_str}: {total_str} ({count} opps, avg age: {avg_age:.1f} days)")


# ==========================================================
# CHECK IF SUMMARY RECORD EXISTS
# ==========================================================
def check_existing_summary(sf, snapshot_date):
    """Check if a summary record already exists for this date"""
    query = f"""
        SELECT Id 
        FROM Pipeline_Snapshot_Summary__c
        WHERE Snapshot_Date__c = '{snapshot_date}'
        LIMIT 1
    """
    try:
        result = sf.query(query)
        if result["totalSize"] > 0:
            return result["records"][0]["Id"]
        return None
    except Exception as e:
        print(f"⚠️ Query failed for date {snapshot_date}: {e}")
        return None


# ==========================================================
# WRITE TO SUMMARY OBJECT
# ==========================================================
def write_to_summary_object(sf, summary_df):
    """Write aggregated data to Pipeline_Snapshot_Summary__c"""
    print("\n======================================================================")
    print("WRITING TO PIPELINE_SNAPSHOT_SUMMARY__C")
    print("======================================================================")
    
    if summary_df.empty:
        print("⚠️ No data to write")
        return 0, 0, 0
    
    created, updated, skipped = 0, 0, 0
    
    for _, row in summary_df.iterrows():
        snapshot_date = str(row["Snapshot_Date__c"])
        
        # Check if record already exists
        existing_id = check_existing_summary(sf, snapshot_date)
        
        # Prepare record data
        record_data = {
            "Snapshot_Date__c": snapshot_date,
            "Total_Open_Pipeline__c": float(row["Total_Open_Pipeline__c"]),
            "Opportunity_Count__c": float(row["Opportunity_Count__c"]),
            "Average_Opp_Age__c": float(row["Average_Opp_Age__c"])
        }
        
        try:
            if existing_id:
                # Update existing record
                sf.Pipeline_Snapshot_Summary__c.update(existing_id, record_data)
                updated += 1
                print(f"   ✓ Updated {snapshot_date}")
            else:
                # Create new record
                result = sf.Pipeline_Snapshot_Summary__c.create(record_data)
                created += 1
                print(f"   ✓ Created {snapshot_date}")
                
        except Exception as e:
            print(f"   ✗ Error writing {snapshot_date}: {e}")
            skipped += 1
    
    print(f"\n📊 Summary: Created {created}, Updated {updated}, Skipped {skipped}")
    return created, updated, skipped


# ==========================================================
# MAIN
# ==========================================================
def main():
    print("\n======================================================================")
    print("PIPELINE SNAPSHOT SYNC")
    print("Daily_Total_Pipeline__c → Pipeline_Snapshot_Summary__c")
    print("======================================================================")

    # Connect to Salesforce
    sf = connect_to_salesforce()
    
    # Query snapshot data from Daily_Total_Pipeline__c
    snapshot_df = get_snapshot_data(sf, days_back=90)
    
    if snapshot_df.empty:
        print("\n⚠️ No snapshot data found. Exiting.")
        return
    
    # Aggregate by date
    daily_summary = aggregate_daily_totals(snapshot_df)
    
    # Display preview
    display_preview(daily_summary)
    
    # Write to Pipeline_Snapshot_Summary__c
    created, updated, skipped = write_to_summary_object(sf, daily_summary)
    
    print("\n======================================================================")
    print("✅ SYNC COMPLETE")
    print("======================================================================")
    print(f"\n📈 Next Step: Build a Salesforce report on Pipeline_Snapshot_Summary__c")
    print(f"   Report Type: Pipeline Snapshot Summaries")
    print(f"   Chart Type: Line Chart")
    print(f"   X-Axis: Snapshot Date")
    print(f"   Y-Axis: Total Open Pipeline")


if __name__ == "__main__":
    main()