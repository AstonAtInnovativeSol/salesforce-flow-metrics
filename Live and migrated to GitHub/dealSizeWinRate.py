#!/usr/bin/env python3
"""
Deal Size and Win Rate Analysis
Analyzes deal size distribution and win rates from Salesforce data.

JWT Authentication Setup:
    This script uses JWT (JSON Web Token) Bearer authentication to connect to Salesforce.
    
    Required Configuration (in sf_config.py - NOT committed to GitHub):
    - SF_USERNAME: Your Salesforce username (e.g., 'user@example.com')
    - SF_CONSUMER_KEY: Connected App Consumer Key from Salesforce
    - SF_DOMAIN: 'login' for production, 'test' for sandbox
    - PRIVATE_KEY_FILE: Path to your RSA private key file (.pem)
    
    See sf_config.py.example for template and setup instructions.
    
    Security Note:
    - sf_config.py is gitignored and will NOT be committed to GitHub
    - Never commit private keys, consumer keys, or passwords
"""

import os
import time
import jwt
import requests
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from simple_salesforce import Salesforce, SalesforceMalformedRequest
import sf_config

# Visualization imports
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.offline as pyo
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("⚠️ Plotly not available - visualizations will be disabled. Install with: pip install plotly")

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
# EFFICIENT SOQL QUERY: DEAL SIZE (PROFESSIONAL SERVICES)
# ==========================================================
def get_deal_size_data(sf, months_back=24, validate_against_report=False, include_cycle_time=False):
    """
    Query closed won opportunities with Professional_Services_Amount__c
    Returns individual deals for distribution analysis
    
    If validate_against_report=True, matches Salesforce report filters:
    - Close Date: Calendar Year 2025 (Jan 1 - Dec 31, 2025)
    - Stage: 'Closed Won - Pending', 'Closed Won', 'Closed Won - Later Cancelled'
    - Excludes test accounts: 'Test Account1', 'ACME Corporation'
    
    If include_cycle_time=True, also gets CreatedDate for cycle time calculation
    """
    if validate_against_report:
        print("Querying Deal Size data - Matching Salesforce Report filters...")
        print("📌 Filters: Calendar Year 2025, Specific Closed Won stages, Excluding test accounts")
        
        # Calendar Year 2025: Jan 1, 2025 - Dec 31, 2025
        start_date = "2025-01-01"
        end_date = "2025-12-31"
        
        # Query matching the report exactly
        # Note: Handling Account.Name exclusion in Python for better reliability
        if include_cycle_time:
            query = f"""
                SELECT Id,
                       CloseDate,
                       CreatedDate,
                       Professional_Services_Amount__c,
                       Account.Name,
                       Account.Id
                FROM Opportunity
                WHERE CloseDate >= {start_date}
                  AND CloseDate <= {end_date}
                  AND IsClosed = true
                  AND StageName IN ('Closed Won - Pending', 'Closed Won', 'Closed Won - Later Cancelled')
                  AND Professional_Services_Amount__c != null
                  AND Professional_Services_Amount__c > 0
                ORDER BY CloseDate DESC
            """
        else:
            query = f"""
                SELECT Id,
                       CloseDate,
                       Professional_Services_Amount__c,
                       Account.Name,
                       Account.Id
                FROM Opportunity
                WHERE CloseDate >= {start_date}
                  AND CloseDate <= {end_date}
                  AND IsClosed = true
                  AND StageName IN ('Closed Won - Pending', 'Closed Won', 'Closed Won - Later Cancelled')
                  AND Professional_Services_Amount__c != null
                  AND Professional_Services_Amount__c > 0
                ORDER BY CloseDate DESC
            """
    else:
        print(f"Querying Deal Size data - Closed Won with Professional Services (last {months_back} months)...")
        
        # Calculate start date
        start_date = (datetime.today() - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")
        
        # Query individual opportunities with Professional Services Amount
        if include_cycle_time:
            query = f"""
                SELECT Id,
                       CloseDate,
                       CreatedDate,
                       Professional_Services_Amount__c
                FROM Opportunity
                WHERE CloseDate >= {start_date}
                  AND IsClosed = true
                  AND StageName LIKE '%Closed Won%'
                  AND Professional_Services_Amount__c != null
                  AND Professional_Services_Amount__c > 0
                ORDER BY CloseDate DESC
            """
        else:
            query = f"""
                SELECT Id,
                       CloseDate,
                       Professional_Services_Amount__c
                FROM Opportunity
                WHERE CloseDate >= {start_date}
                  AND IsClosed = true
                  AND StageName LIKE '%Closed Won%'
                  AND Professional_Services_Amount__c != null
                  AND Professional_Services_Amount__c > 0
                ORDER BY CloseDate DESC
            """
    
    try:
        records = sf.query_all(query)["records"]
        print(f"✅ Found {len(records)} closed won deals with Professional Services revenue")
        
        if not records:
            print("⚠️ No closed won opportunity data found.")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Remove attributes column if present
        if 'attributes' in df.columns:
            df = df.drop(columns=['attributes'])
        
        # Flatten Account.Name if present (when validating against report)
        if 'Account' in df.columns:
            if validate_against_report:
                df['Account_Name'] = df['Account'].apply(lambda x: x.get('Name', '') if isinstance(x, dict) else '')
                # Additional filter for test accounts in Python (more reliable than SOQL LIKE)
                df = df[
                    (~df['Account_Name'].str.contains('Test Account1', case=False, na=False)) &
                    (~df['Account_Name'].str.contains('ACME Corporation', case=False, na=False))
                ]
            df = df.drop(columns=['Account'])
        
        # Ensure proper data types
        df['CloseDate'] = pd.to_datetime(df['CloseDate'])
        df['Professional_Services_Amount__c'] = pd.to_numeric(df['Professional_Services_Amount__c'], errors='coerce')
        
        # Calculate cycle time if CreatedDate is available
        if 'CreatedDate' in df.columns:
            # Handle timezone-aware datetimes by converting to naive
            df['CreatedDate'] = pd.to_datetime(df['CreatedDate'])
            df['CloseDate'] = pd.to_datetime(df['CloseDate'])
            # Convert to naive (remove timezone info if present)
            try:
                if df['CreatedDate'].dt.tz is not None:
                    df['CreatedDate'] = df['CreatedDate'].dt.tz_convert(None)
            except:
                pass
            try:
                if df['CloseDate'].dt.tz is not None:
                    df['CloseDate'] = df['CloseDate'].dt.tz_convert(None)
            except:
                pass
            df['Cycle_Days'] = (df['CloseDate'] - df['CreatedDate']).dt.days
            df['Cycle_Days'] = pd.to_numeric(df['Cycle_Days'], errors='coerce')
            df['Cycle_Days'] = df['Cycle_Days'].clip(lower=0)  # Ensure non-negative
        
        # Extract Year, Month, Quarter from CloseDate
        df['Year'] = df['CloseDate'].dt.year
        df['Month'] = df['CloseDate'].dt.month
        df['Quarter'] = df['CloseDate'].dt.quarter
        
        # Filter out nulls
        df = df[df['Professional_Services_Amount__c'].notna() & (df['Professional_Services_Amount__c'] > 0)]
        
        # Validation summary if matching report
        if validate_against_report:
            total_deals = len(df)
            total_amount = df['Professional_Services_Amount__c'].sum()
            print(f"\n📊 VALIDATION SUMMARY (Matching Report Filters):")
            print(f"   Total Deals: {total_deals}")
            print(f"   Total Professional Services Amount: ${total_amount:,.2f}")
            print(f"   Report Expected: 711 deals, $20,730,051.50")
            
            if total_deals != 711:
                diff = total_deals - 711
                print(f"   ⚠️ Deal Count Difference: {diff:+d} deals")
            
            if abs(total_amount - 20730051.50) > 0.01:
                diff = total_amount - 20730051.50
                print(f"   ⚠️ Amount Difference: ${diff:+,.2f}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error querying deal size data: {e}")
        return pd.DataFrame()


# ==========================================================
# EFFICIENT SOQL QUERY: WIN RATE WITH OWNER INFO
# ==========================================================
def get_win_rate_data(sf, months_back=24, include_deal_size=False):
    """
    Query closed opportunities (Won/Lost) with Owner info for rep-level analysis
    EXCLUDES Disqualified opportunities
    
    If include_deal_size=True, also gets Professional_Services_Amount__c and CreatedDate for win rate by band
    """
    print(f"Querying Win Rate data - Closed Won/Lost (excluding Disqualified) (last {months_back} months)...")
    
    # Calculate start date
    start_date = (datetime.today() - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")
    
    # Query individual opportunities with Owner info
    # Exclude Disqualified explicitly
    if include_deal_size:
        query = f"""SELECT Id, CloseDate, CreatedDate, StageName, Professional_Services_Amount__c, Owner.Name, Owner.Id, Owner.IsActive FROM Opportunity WHERE CloseDate >= {start_date} AND IsClosed = true AND (StageName LIKE '%Closed Won%' OR StageName LIKE '%Closed Lost%') AND StageName != 'Disqualified' ORDER BY CloseDate DESC"""
    else:
        query = f"""SELECT Id, CloseDate, StageName, Owner.Name, Owner.Id, Owner.IsActive FROM Opportunity WHERE CloseDate >= {start_date} AND IsClosed = true AND (StageName LIKE '%Closed Won%' OR StageName LIKE '%Closed Lost%') AND StageName != 'Disqualified' ORDER BY CloseDate DESC"""
    
    try:
        records = sf.query_all(query)["records"]
        print(f"✅ Found {len(records)} closed opportunities (Won/Lost, excluding Disqualified)")
        
        if not records:
            print("⚠️ No closed opportunity data found.")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Remove attributes column if present
        if 'attributes' in df.columns:
            df = df.drop(columns=['attributes'])
        
        # Flatten Owner fields
        if 'Owner' in df.columns:
            df['Owner_Name'] = df['Owner'].apply(lambda x: x.get('Name', '') if isinstance(x, dict) else '')
            df['Owner_Id'] = df['Owner'].apply(lambda x: x.get('Id', '') if isinstance(x, dict) else '')
            df['Owner_IsActive'] = df['Owner'].apply(lambda x: x.get('IsActive', False) if isinstance(x, dict) else False)
            df = df.drop(columns=['Owner'])
        
        # Ensure proper data types
        df['CloseDate'] = pd.to_datetime(df['CloseDate'])
        
        # Extract Year, Month, Quarter from CloseDate
        df['Year'] = df['CloseDate'].dt.year
        df['Month'] = df['CloseDate'].dt.month
        df['Quarter'] = df['CloseDate'].dt.quarter
        
        # Mark Won/Lost
        df['IsWon'] = df['StageName'].str.contains('Won', case=False, na=False)
        df['IsLost'] = df['StageName'].str.contains('Lost', case=False, na=False)
        
        # Calculate cycle time if CreatedDate is available
        if 'CreatedDate' in df.columns:
            # Handle timezone-aware datetimes by converting to naive
            df['CreatedDate'] = pd.to_datetime(df['CreatedDate'])
            df['CloseDate'] = pd.to_datetime(df['CloseDate'])
            # Convert to naive (remove timezone info)
            try:
                if df['CreatedDate'].dt.tz is not None:
                    df['CreatedDate'] = df['CreatedDate'].dt.tz_convert(None)
            except:
                df['CreatedDate'] = pd.to_datetime(df['CreatedDate']).dt.tz_localize(None)
            try:
                if df['CloseDate'].dt.tz is not None:
                    df['CloseDate'] = df['CloseDate'].dt.tz_convert(None)
            except:
                df['CloseDate'] = pd.to_datetime(df['CloseDate']).dt.tz_localize(None)
            df['Cycle_Days'] = (df['CloseDate'] - df['CreatedDate']).dt.days
            df['Cycle_Days'] = pd.to_numeric(df['Cycle_Days'], errors='coerce')
            df['Cycle_Days'] = df['Cycle_Days'].clip(lower=0)
        
        # Assign deal size band if Professional_Services_Amount__c is available
        if 'Professional_Services_Amount__c' in df.columns:
            df['Professional_Services_Amount__c'] = pd.to_numeric(df['Professional_Services_Amount__c'], errors='coerce')
            df['Deal_Size_Band'] = df['Professional_Services_Amount__c'].apply(assign_deal_size_band)
        
        return df
        
    except Exception as e:
        print(f"❌ Error querying win rate data: {e}")
        return pd.DataFrame()


# ==========================================================
# DEAL SIZE BANDS (NEW TEMPLATE)
# ==========================================================
def assign_deal_size_band(amount):
    """Assign deal to size band - matching new template bands"""
    if pd.isna(amount) or amount <= 0:
        return 'Unknown'
    elif amount < 25000:
        return '<$25k'
    elif amount < 100000:
        return '$25k–$100k'
    elif amount < 500000:
        return '$100k–$500k'
    else:
        return '>$500k'


# ==========================================================
# CALCULATE DEAL SIZE DISTRIBUTION
# ==========================================================
def calculate_deal_size_distribution(df, period='YTD'):
    """
    Calculate deal size distribution with bands for different periods
    period: 'YTD', 'QoQ', 'YoY', or 'All'
    Returns a list of DataFrames for comparisons (YoY, QoQ) or single DataFrame for YTD
    """
    print(f"\nCalculating Deal Size Distribution ({period})...")
    
    if df.empty:
        return pd.DataFrame()
    
    current_date = datetime.today()
    current_year = current_date.year
    current_quarter = (current_date.month - 1) // 3 + 1
    
    # Filter by period
    if period == 'YTD':
        filtered_df = df[df['Year'] == current_year].copy()
        
        if filtered_df.empty:
            print(f"⚠️ No data for {period}")
            return pd.DataFrame()
        
        # Assign bands
        filtered_df['Deal_Size_Band'] = filtered_df['Professional_Services_Amount__c'].apply(assign_deal_size_band)
        
        # Calculate distribution
        distribution = filtered_df.groupby('Deal_Size_Band').agg({
            'Id': 'count',
            'Professional_Services_Amount__c': ['sum', 'mean', 'median', 'min', 'max']
        }).reset_index()
        
        distribution.columns = ['Deal_Size_Band', 'Deal_Count', 'Total_Amount', 'Avg_Amount', 'Median_Amount', 'Min_Amount', 'Max_Amount']
        
        # Calculate percentages
        total_deals = distribution['Deal_Count'].sum()
        distribution['Deal_Count_Pct'] = (distribution['Deal_Count'] / total_deals * 100).round(2)
        
        total_amount = distribution['Total_Amount'].sum()
        distribution['Amount_Pct'] = (distribution['Total_Amount'] / total_amount * 100).round(2)
        
        # Order bands
        band_order = ['0-10k', '10k-50k', '50k-100k', '100k+']
        distribution['Band_Order'] = distribution['Deal_Size_Band'].apply(lambda x: band_order.index(x) if x in band_order else 999)
        distribution = distribution.sort_values('Band_Order')
        distribution = distribution.drop(columns=['Band_Order'])
        
        distribution['Period'] = f"{current_year} YTD"
        distribution['Year'] = current_year
        
        print(f"✅ Calculated distribution for {len(distribution)} bands")
        return distribution
        
    elif period == 'QoQ':
        # Q4 2025 through today vs Q3 2025 SAME NUMBER OF DAYS
        # Calculate days from start of current quarter through today
        if current_quarter == 1:
            current_q_start = datetime(current_year, 1, 1)
        elif current_quarter == 2:
            current_q_start = datetime(current_year, 4, 1)
        elif current_quarter == 3:
            current_q_start = datetime(current_year, 7, 1)
        else:  # Q4
            current_q_start = datetime(current_year, 10, 1)
        
        days_elapsed = (current_date - current_q_start).days + 1  # +1 to include today
        
        # Current quarter through today
        current_q_df = df[
            (df['Year'] == current_year) & 
            (df['Quarter'] == current_quarter) &
            (df['CloseDate'] <= current_date)
        ].copy()
        
        # Previous quarter - same number of days
        if current_quarter > 1:
            prev_q = current_quarter - 1
            prev_year = current_year
        else:
            prev_q = 4
            prev_year = current_year - 1
        
        if prev_q == 1:
            prev_q_start = datetime(prev_year, 1, 1)
        elif prev_q == 2:
            prev_q_start = datetime(prev_year, 4, 1)
        elif prev_q == 3:
            prev_q_start = datetime(prev_year, 7, 1)
        else:  # Q4
            prev_q_start = datetime(prev_year, 10, 1)
        
        prev_q_end = prev_q_start + timedelta(days=days_elapsed - 1)
        
        prev_q_df = df[
            (df['Year'] == prev_year) & 
            (df['Quarter'] == prev_q) &
            (df['CloseDate'] >= prev_q_start) &
            (df['CloseDate'] <= prev_q_end)
        ].copy()
        
        results = []
        for q_df, q_num, year, label in [(current_q_df, current_quarter, current_year, f"Q{current_quarter} {current_year}"),
                                         (prev_q_df, prev_q, prev_year, f"Q{prev_q} {prev_year}")]:
            if q_df.empty:
                continue
            
            # Assign bands
            q_df['Deal_Size_Band'] = q_df['Professional_Services_Amount__c'].apply(assign_deal_size_band)
            
            # Calculate distribution
            distribution = q_df.groupby('Deal_Size_Band').agg({
                'Id': 'count',
                'Professional_Services_Amount__c': ['sum', 'mean', 'median', 'min', 'max']
            }).reset_index()
            
            distribution.columns = ['Deal_Size_Band', 'Deal_Count', 'Total_Amount', 'Avg_Amount', 'Median_Amount', 'Min_Amount', 'Max_Amount']
            
            # Calculate percentages
            total_deals = distribution['Deal_Count'].sum()
            distribution['Deal_Count_Pct'] = (distribution['Deal_Count'] / total_deals * 100).round(2)
            
            total_amount = distribution['Total_Amount'].sum()
            distribution['Amount_Pct'] = (distribution['Total_Amount'] / total_amount * 100).round(2)
            
            # Order bands
            band_order = ['0-10k', '10k-50k', '50k-100k', '100k+']
            distribution['Band_Order'] = distribution['Deal_Size_Band'].apply(lambda x: band_order.index(x) if x in band_order else 999)
            distribution = distribution.sort_values('Band_Order')
            distribution = distribution.drop(columns=['Band_Order'])
            
            # Update label for QoQ to show "through today" or "same number of days"
            if q_num == current_quarter:
                distribution['Period'] = f"{label} (through today)"
            else:
                distribution['Period'] = f"{label} (same {days_elapsed} days)"
            
            distribution['Year'] = year
            distribution['Quarter'] = q_num
            distribution['Days_Compared'] = days_elapsed
            
            results.append(distribution)
        
        if not results:
            print(f"⚠️ No data for {period}")
            return pd.DataFrame()
        
        print(f"✅ Calculated distribution for {sum(len(r) for r in results)} bands across {len(results)} periods ({days_elapsed} days)")
        return results
        
    elif period == 'YoY':
        # October 2024 vs October 2025 - return separate DataFrames
        # Use October instead of current month
        compare_month = 10  # October
        current_month_df = df[(df['Year'] == current_year) & (df['Month'] == compare_month)].copy()
        prev_year_df = df[(df['Year'] == current_year - 1) & (df['Month'] == compare_month)].copy()
        
        results = []
        month_name = "October"
        for month_df, year, label in [(current_month_df, current_year, f"{month_name} {current_year}"),
                                      (prev_year_df, current_year - 1, f"{month_name} {current_year - 1}")]:
            if month_df.empty:
                continue
            
            # Assign bands
            month_df['Deal_Size_Band'] = month_df['Professional_Services_Amount__c'].apply(assign_deal_size_band)
            
            # Calculate distribution
            distribution = month_df.groupby('Deal_Size_Band').agg({
                'Id': 'count',
                'Professional_Services_Amount__c': ['sum', 'mean', 'median', 'min', 'max']
            }).reset_index()
            
            distribution.columns = ['Deal_Size_Band', 'Deal_Count', 'Total_Amount', 'Avg_Amount', 'Median_Amount', 'Min_Amount', 'Max_Amount']
            
            # Calculate percentages
            total_deals = distribution['Deal_Count'].sum()
            distribution['Deal_Count_Pct'] = (distribution['Deal_Count'] / total_deals * 100).round(2)
            
            total_amount = distribution['Total_Amount'].sum()
            distribution['Amount_Pct'] = (distribution['Total_Amount'] / total_amount * 100).round(2)
            
            # Order bands
            band_order = ['0-10k', '10k-50k', '50k-100k', '100k+']
            distribution['Band_Order'] = distribution['Deal_Size_Band'].apply(lambda x: band_order.index(x) if x in band_order else 999)
            distribution = distribution.sort_values('Band_Order')
            distribution = distribution.drop(columns=['Band_Order'])
            
            distribution['Period'] = label
            distribution['Year'] = year
            
            results.append(distribution)
        
        if not results:
            print(f"⚠️ No data for {period}")
            return pd.DataFrame()
        
        print(f"✅ Calculated distribution for {sum(len(r) for r in results)} bands across {len(results)} periods")
        return results
        
    else:  # All
        filtered_df = df.copy()
        
        if filtered_df.empty:
            print(f"⚠️ No data for {period}")
            return pd.DataFrame()
        
        # Assign bands
        filtered_df['Deal_Size_Band'] = filtered_df['Professional_Services_Amount__c'].apply(assign_deal_size_band)
        
        # Calculate distribution
        distribution = filtered_df.groupby('Deal_Size_Band').agg({
            'Id': 'count',
            'Professional_Services_Amount__c': ['sum', 'mean', 'median', 'min', 'max']
        }).reset_index()
        
        distribution.columns = ['Deal_Size_Band', 'Deal_Count', 'Total_Amount', 'Avg_Amount', 'Median_Amount', 'Min_Amount', 'Max_Amount']
        
        # Calculate percentages
        total_deals = distribution['Deal_Count'].sum()
        distribution['Deal_Count_Pct'] = (distribution['Deal_Count'] / total_deals * 100).round(2)
        
        total_amount = distribution['Total_Amount'].sum()
        distribution['Amount_Pct'] = (distribution['Total_Amount'] / total_amount * 100).round(2)
        
        # Order bands
        band_order = ['0-10k', '10k-50k', '50k-100k', '100k+']
        distribution['Band_Order'] = distribution['Deal_Size_Band'].apply(lambda x: band_order.index(x) if x in band_order else 999)
        distribution = distribution.sort_values('Band_Order')
        distribution = distribution.drop(columns=['Band_Order'])
        
        distribution['Period'] = "All Time"
        
        print(f"✅ Calculated distribution for {len(distribution)} bands")
        return distribution


# ==========================================================
# CALCULATE WIN RATE BY REP
# ==========================================================
def calculate_win_rate_by_rep(df, period='YTD', yoy_mode=False):
    """
    Calculate win rate by Sales Rep
    period: 'YTD', 'QoQ', 'YoY'
    yoy_mode: For YoY, include all reps who had closed won deals, not just active ones
    """
    print(f"\nCalculating Win Rate by Rep ({period})...")
    
    if df.empty:
        return pd.DataFrame()
    
    current_date = datetime.today()
    current_year = current_date.year
    current_quarter = (current_date.month - 1) // 3 + 1
    current_month = current_date.month
    
    # Filter by period
    if period == 'YTD':
        filtered_df = df[df['Year'] == current_year].copy()
        period_label = f"{current_year} YTD"
        # For YTD, only active reps
        if not yoy_mode:
            filtered_df = filtered_df[filtered_df['Owner_IsActive'] == True]
    elif period == 'QoQ':
        filtered_df = df[
            ((df['Year'] == current_year) & (df['Quarter'] == current_quarter)) |
            ((df['Year'] == current_year) & (df['Quarter'] == current_quarter - 1)) |
            ((df['Year'] == current_year - 1) & (df['Quarter'] == 4) & (current_quarter == 1))
        ].copy()
        period_label = f"Q{current_quarter} {current_year} vs Q{current_quarter - 1}"
        # For QoQ, only active reps
        if not yoy_mode:
            filtered_df = filtered_df[filtered_df['Owner_IsActive'] == True]
    elif period == 'YoY':
        # Same month, previous year
        filtered_df = df[
            ((df['Year'] == current_year) & (df['Month'] == current_month)) |
            ((df['Year'] == current_year - 1) & (df['Month'] == current_month))
        ].copy()
        period_label = f"{current_date.strftime('%B')} {current_year} vs {current_year - 1}"
        # For YoY, if yoy_mode=True, include all reps who had closed won deals (not just active)
        # We'll filter this differently - include anyone with closed won in the period
        if yoy_mode:
            # Get all unique owners who had closed won deals in this period
            won_owners = set(filtered_df[filtered_df['IsWon'] == True]['Owner_Id'].unique())
            # Include those owners + active reps
            filtered_df = filtered_df[
                (filtered_df['Owner_Id'].isin(won_owners)) | 
                (filtered_df['Owner_IsActive'] == True)
            ]
    
    if filtered_df.empty:
        print(f"⚠️ No data for {period}")
        return pd.DataFrame()
    
    # Calculate by rep
    rep_stats = filtered_df.groupby(['Owner_Name', 'Owner_Id', 'Owner_IsActive']).agg({
        'Id': lambda x: len(x),  # Total closed
        'IsWon': 'sum',  # Won count
        'IsLost': 'sum'  # Lost count
    }).reset_index()
    
    rep_stats.columns = ['Rep_Name', 'Rep_Id', 'IsActive', 'Total_Closed', 'Won_Count', 'Lost_Count']
    
    # Calculate win rate
    rep_stats['Win_Rate_Pct'] = (rep_stats['Won_Count'] / rep_stats['Total_Closed'] * 100).round(2)
    
    # Filter out reps with no closed deals
    rep_stats = rep_stats[rep_stats['Total_Closed'] > 0]
    
    # Sort by win rate descending
    rep_stats = rep_stats.sort_values('Win_Rate_Pct', ascending=False)
    
    rep_stats['Period'] = period_label
    
    print(f"✅ Calculated win rate for {len(rep_stats)} reps")
    
    return rep_stats


# ==========================================================
# STAGE BREAKDOWN FOR WIN RATE VALIDATION
# ==========================================================
def show_stage_breakdown(df):
    """Show stage breakdown to validate win rate calculation (excluding Disqualified)"""
    print("\n" + "="*70)
    print("STAGE BREAKDOWN (Validating Win Rate Calculation)")
    print("="*70)
    print("\nWin Rate Formula: Won / (Won + Lost)")
    print("Excluded from calculation: Disqualified opportunities\n")
    
    if df.empty:
        print("⚠️ No data available")
        return
    
    stage_counts = df.groupby('StageName').agg({
        'Id': 'count',
        'IsWon': 'sum',
        'IsLost': 'sum'
    }).reset_index()
    
    stage_counts.columns = ['StageName', 'Count', 'Won', 'Lost']
    
    # Check for Disqualified
    disqualified = stage_counts[stage_counts['StageName'].str.contains('Disqualified', case=False, na=False)]
    if not disqualified.empty:
        print("⚠️ Found Disqualified stages (these are EXCLUDED from win rate):")
        for _, row in disqualified.iterrows():
            print(f"   - {row['StageName']}: {int(row['Count'])} opportunities")
        print()
    
    # Show included stages
    included = stage_counts[~stage_counts['StageName'].str.contains('Disqualified', case=False, na=False)]
    print("Stages INCLUDED in Win Rate calculation:")
    for _, row in included.iterrows():
        print(f"   - {row['StageName']}: {int(row['Count'])} opportunities (Won: {int(row['Won'])}, Lost: {int(row['Lost'])})")
    
    # Calculate overall win rate
    total_won = included['Won'].sum()
    total_lost = included['Lost'].sum()
    total_closed = total_won + total_lost
    
    if total_closed > 0:
        win_rate = (total_won / total_closed * 100)
        print(f"\nOverall Win Rate: {win_rate:.2f}% ({int(total_won)}/{int(total_closed)})")


# ==========================================================
# DISPLAY DEAL SIZE DISTRIBUTION
# ==========================================================
def display_deal_size_distribution(distributions):
    """Display deal size distribution with visualizations"""
    
    for period, dist_data in distributions.items():
        # Handle list of DataFrames for comparisons (QoQ, YoY)
        if isinstance(dist_data, list):
            if not dist_data or all(df.empty for df in dist_data):
                continue
            
            # Get period label from first DataFrame
            period_labels = [df.iloc[0]['Period'] for df in dist_data if not df.empty]
            comparison_label = " vs ".join(period_labels)
            
            print("\n" + "="*150)
            print(f"DEAL SIZE DISTRIBUTION - {comparison_label}")
            print("="*150)
            print("\nProfessional Services Amount Bands:\n")
            
            # Display side by side
            # First, get all bands across all periods
            all_bands = set()
            for df in dist_data:
                if not df.empty:
                    all_bands.update(df['Deal_Size_Band'].unique())
            
            band_order = ['0-10k', '10k-50k', '50k-100k', '100k+']
            sorted_bands = [b for b in band_order if b in all_bands] + [b for b in all_bands if b not in band_order]
            
            # Header for side-by-side display
            headers = ['Band']
            for df in dist_data:
                if not df.empty:
                    year = int(df.iloc[0].get('Year', 0))
                    if 'Quarter' in df.columns:
                        q = int(df.iloc[0].get('Quarter', 0))
                        headers.append(f"Q{q} {year}")
                    else:
                        headers.append(f"{year}")
            
            # Print header
            header_line = "  ".join([f"{h:<18}" for h in headers])
            print(header_line)
            print("-" * len(header_line))
            
            # Print data for each band
            for band in sorted_bands:
                row = [band]
                for df in dist_data:
                    if not df.empty:
                        band_data = df[df['Deal_Size_Band'] == band]
                        if not band_data.empty:
                            count = int(band_data.iloc[0]['Deal_Count'])
                            row.append(f"Deals: {count}")
                        else:
                            row.append("Deals: 0")
                print("  ".join([f"{r:<18}" for r in row]))
            
            # Show detailed breakdown for each period
            for df in dist_data:
                if df.empty:
                    continue
                
                year = int(df.iloc[0].get('Year', 0))
                period_label = df.iloc[0]['Period']
                
                print(f"\n{'='*150}")
                print(f"DETAILED BREAKDOWN - {period_label}")
                print(f"{'='*150}\n")
                
                print(f"{'Band':<12} {'Deals':<10} {'Deal %':<10} {'Total $':<18} {'Amount %':<10} {'Avg $':<15} {'Median $':<15}")
                print("-"*100)
                
                for _, row in df.iterrows():
                    band = row['Deal_Size_Band']
                    count = int(row['Deal_Count'])
                    count_pct = row['Deal_Count_Pct']
                    total = row['Total_Amount']
                    amount_pct = row['Amount_Pct']
                    avg = row['Avg_Amount']
                    median = row['Median_Amount']
                    
                    print(f"{band:<12} {count:<10} {count_pct:>6.2f}%{'':<2} ${total:>15,.2f}{'':<1} {amount_pct:>6.2f}%{'':<2} ${avg:>13,.2f}{'':<1} ${median:>13,.2f}")
                
                # Create simple text-based bar chart
                print("\nDeal Count Distribution (Bar Chart):")
                max_count = df['Deal_Count'].max() if not df.empty else 1
                for _, row in df.iterrows():
                    band = row['Deal_Size_Band']
                    count = int(row['Deal_Count'])
                    bar_length = int((count / max_count) * 50) if max_count > 0 else 0
                    bar = '█' * bar_length
                    print(f"{band:<12} {bar} {count}")
        
        else:
            # Single DataFrame (YTD, All)
            if dist_data.empty:
                continue
                
            print("\n" + "="*70)
            period_label = dist_data.iloc[0]['Period']
            year = int(dist_data.iloc[0].get('Year', 0)) if 'Year' in dist_data.columns else 0
            print(f"DEAL SIZE DISTRIBUTION - {period_label}")
            if year > 0:
                print(f"Year: {year}")
            print("="*70)
            print("\nProfessional Services Amount Bands:\n")
            
            print(f"{'Band':<12} {'Deals':<10} {'Deal %':<10} {'Total $':<18} {'Amount %':<10} {'Avg $':<15} {'Median $':<15}")
            print("-"*100)
            
            for _, row in dist_data.iterrows():
                band = row['Deal_Size_Band']
                count = int(row['Deal_Count'])
                count_pct = row['Deal_Count_Pct']
                total = row['Total_Amount']
                amount_pct = row['Amount_Pct']
                avg = row['Avg_Amount']
                median = row['Median_Amount']
                
                print(f"{band:<12} {count:<10} {count_pct:>6.2f}%{'':<2} ${total:>15,.2f}{'':<1} {amount_pct:>6.2f}%{'':<2} ${avg:>13,.2f}{'':<1} ${median:>13,.2f}")
            
            # Create simple text-based bar chart
            print("\nDeal Count Distribution (Bar Chart):")
            max_count = dist_data['Deal_Count'].max()
            for _, row in dist_data.iterrows():
                band = row['Deal_Size_Band']
                count = int(row['Deal_Count'])
                bar_length = int((count / max_count) * 50) if max_count > 0 else 0
                bar = '█' * bar_length
                print(f"{band:<12} {bar} {count}")


# ==========================================================
# DISPLAY WIN RATE BY REP
# ==========================================================
def display_win_rate_by_rep(rep_stats_dict):
    """Display win rate by Sales Rep"""
    
    for period, rep_df in rep_stats_dict.items():
        if rep_df.empty:
            continue
        
        print("\n" + "="*70)
        print(f"WIN RATE BY SALES REP - {rep_df.iloc[0]['Period']}")
        print("="*70)
        
        if period == 'YoY':
            print("(YoY mode: Includes all reps who had closed won deals, not just active)")
        else:
            print("(Active Sales Reps only: IsActive = True)")
        
        print(f"\n{'Rep Name':<30} {'Active':<8} {'Won':<8} {'Lost':<8} {'Total':<8} {'Win Rate %':<12}")
        print("-"*90)
        
        for _, row in rep_df.iterrows():
            rep_name = row['Rep_Name'][:28]  # Truncate if too long
            is_active = "✓" if row['IsActive'] else "✗"
            won = int(row['Won_Count'])
            lost = int(row['Lost_Count'])
            total = int(row['Total_Closed'])
            win_rate = row['Win_Rate_Pct']
            
            print(f"{rep_name:<30} {is_active:<8} {won:<8} {lost:<8} {total:<8} {win_rate:>8.2f}%")
        
        # Summary stats
        if not rep_df.empty:
            avg_win_rate = rep_df['Win_Rate_Pct'].mean()
            total_won = rep_df['Won_Count'].sum()
            total_lost = rep_df['Lost_Count'].sum()
            total_closed = rep_df['Total_Closed'].sum()
            overall_win_rate = (total_won / total_closed * 100) if total_closed > 0 else 0
            
            print("\n" + "-"*90)
            print(f"{'Overall':<30} {'':<8} {int(total_won):<8} {int(total_lost):<8} {int(total_closed):<8} {overall_win_rate:>8.2f}%")
            print(f"{'Average by Rep':<30} {'':<8} {'':<8} {'':<8} {'':<8} {avg_win_rate:>8.2f}%")


# ==========================================================
# EXPORT DATA
# ==========================================================
def export_data(deal_size_df, deal_distributions, win_rate_df, win_rate_by_rep):
    """Export all metrics to CSV files"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Export deal size raw data
    if not deal_size_df.empty:
        deal_file = f"deal_size_raw_{timestamp}.csv"
        deal_size_df.to_csv(deal_file, index=False)
        print(f"\n📁 Deal Size raw data exported to: {deal_file}")
    
    # Export deal size distributions
    for period, dist_data in deal_distributions.items():
        # Handle list of DataFrames for comparisons
        if isinstance(dist_data, list):
            for idx, dist_df in enumerate(dist_data):
                if not dist_df.empty:
                    period_label = dist_df.iloc[0]['Period'].replace(' ', '_')
                    dist_file = f"deal_size_distribution_{period}_{period_label}_{timestamp}.csv"
                    dist_df.to_csv(dist_file, index=False)
                    print(f"📁 Deal Size Distribution ({period} - {dist_df.iloc[0]['Period']}) exported to: {dist_file}")
        else:
            # Single DataFrame
            if not dist_data.empty:
                dist_file = f"deal_size_distribution_{period}_{timestamp}.csv"
                dist_data.to_csv(dist_file, index=False)
                print(f"📁 Deal Size Distribution ({period}) exported to: {dist_file}")
    
    # Export win rate raw data
    if not win_rate_df.empty:
        win_file = f"win_rate_raw_{timestamp}.csv"
        win_rate_df.to_csv(win_file, index=False)
        print(f"📁 Win Rate raw data exported to: {win_file}")
    
    # Export win rate by rep
    for period, rep_df in win_rate_by_rep.items():
        if not rep_df.empty:
            rep_file = f"win_rate_by_rep_{period}_{timestamp}.csv"
            rep_df.to_csv(rep_file, index=False)
            print(f"📁 Win Rate by Rep ({period}) exported to: {rep_file}")


# ==========================================================
# PREPARE DATA FOR NEW TEMPLATE
# ==========================================================
def prepare_template_data(deal_size_df, win_rate_df, deal_distributions):
    """
    Prepare all data structures needed for the new HTML template
    Returns a dict matching the DATA object structure expected by the template
    """
    print("\nPreparing data for new template structure...")
    
    current_date = datetime.today()
    current_year = current_date.year
    current_month = current_date.month
    current_quarter = (current_month - 1) // 3 + 1
    
    # Deal size bands (new template format)
    bands = ['<$25k', '$25k–$100k', '$100k–$500k', '>$500k']
    
    # Periods (matching template)
    periods = []
    
    # Calculate distributions for each period
    share_data = []  # share[period][band] - percentages that sum to 1.0
    
    # YTD
    deal_size_ytd = deal_distributions.get('YTD')
    if isinstance(deal_size_ytd, pd.DataFrame) and not deal_size_ytd.empty:
        periods.append(f"{current_year} YTD")
        # Convert old bands to new bands and calculate share
        ytd_share = convert_band_distribution_to_new_bands(deal_size_ytd)
        share_data.append(ytd_share)
    
    # Q4-to-date (current quarter through today)
    if current_quarter == 4:
        q4_df = deal_size_df[
            (deal_size_df['Year'] == current_year) & 
            (deal_size_df['Quarter'] == 4) &
            (deal_size_df['CloseDate'] <= current_date)
        ].copy()
        if not q4_df.empty:
            periods.append("Q4-to-date")
            q4_share = calculate_share_by_band(q4_df)
            share_data.append(q4_share)
    
    # Q3 (same number of days)
    qoq_data = deal_distributions.get('QoQ')
    if isinstance(qoq_data, list) and len(qoq_data) > 1:
        periods.append("Q3 (35 days)")  # Will be dynamic based on actual days
        q3_share = convert_band_distribution_to_new_bands(qoq_data[1])  # Previous quarter
        share_data.append(q3_share)
    
    # October 2025
    oct_df = deal_size_df[
        (deal_size_df['Year'] == current_year) & 
        (deal_size_df['Month'] == 10)
    ].copy()
    if not oct_df.empty:
        periods.append("Oct 2025")
        oct_share = calculate_share_by_band(oct_df)
        share_data.append(oct_share)
    
    # Calculate win rate by band
    winrate_by_band = calculate_win_rate_by_band(win_rate_df)
    
    # Calculate amounts by band (for Pareto)
    amounts_by_band = calculate_amounts_by_band(deal_size_df)
    
    # Calculate scatter data (deal size vs cycle time)
    scatter_data = calculate_scatter_data(deal_size_df)
    
    # Calculate table rows
    table_rows = calculate_table_rows(deal_size_df, win_rate_df)
    
    # Calculate KPIs with deltas
    kpis = calculate_kpis_with_deltas(deal_size_df, win_rate_df, deal_distributions)
    
    # Metadata
    metadata = {
        'generated': current_date.strftime("%Y-%m-%d %H:%M"),
        'filters': [f"{current_year} YTD", "Professional Services Revenue Analysis"]
    }
    
    return {
        'metadata': metadata,
        'kpis': kpis,
        'bands': bands,
        'periods': periods,
        'share': share_data,
        'winrate': winrate_by_band,
        'amount': amounts_by_band,
        'scatter': scatter_data,
        'table_rows': table_rows
    }


def convert_band_distribution_to_new_bands(dist_df):
    """Convert old band distribution to new band format"""
    if dist_df.empty:
        return [0.0, 0.0, 0.0, 0.0]
    
    # Map old bands to new bands
    band_mapping = {
        '0-10k': '<$25k',
        '10k-50k': '$25k–$100k',
        '50k-100k': '$25k–$100k',
        '100k+': '$100k–$500k'  # Will need to split this
    }
    
    # For now, approximate mapping
    total_deals = dist_df['Deal_Count'].sum()
    if total_deals == 0:
        return [0.0, 0.0, 0.0, 0.0]
    
    new_bands = {'<$25k': 0, '$25k–$100k': 0, '$100k–$500k': 0, '>$500k': 0}
    
    for _, row in dist_df.iterrows():
        old_band = row['Deal_Size_Band']
        count = row['Deal_Count']
        
        if old_band == '0-10k':
            new_bands['<$25k'] += count
        elif old_band == '10k-50k':
            new_bands['$25k–$100k'] += count
        elif old_band == '50k-100k':
            new_bands['$100k–$500k'] += count
        elif old_band == '100k+':
            # Split 100k+ between $100k–$500k and >$500k based on average
            avg_amount = row['Avg_Amount']
            if avg_amount < 500000:
                new_bands['$100k–$500k'] += count
            else:
                new_bands['>$500k'] += count
    
    # Convert to percentages
    return [
        new_bands['<$25k'] / total_deals,
        new_bands['$25k–$100k'] / total_deals,
        new_bands['$100k–$500k'] / total_deals,
        new_bands['>$500k'] / total_deals
    ]


def calculate_share_by_band(df):
    """Calculate share percentages by new bands"""
    if df.empty:
        return [0.0, 0.0, 0.0, 0.0]
    
    # Assign new bands
    df['Deal_Size_Band'] = df['Professional_Services_Amount__c'].apply(assign_deal_size_band)
    
    # Count by band
    band_counts = df['Deal_Size_Band'].value_counts()
    total = len(df)
    
    if total == 0:
        return [0.0, 0.0, 0.0, 0.0]
    
    return [
        band_counts.get('<$25k', 0) / total,
        band_counts.get('$25k–$100k', 0) / total,
        band_counts.get('$100k–$500k', 0) / total,
        band_counts.get('>$500k', 0) / total
    ]


def calculate_win_rate_by_band(win_rate_df):
    """Calculate win rate for each deal size band"""
    if win_rate_df.empty or 'Deal_Size_Band' not in win_rate_df.columns:
        return [0.26, 0.41, 0.54, 0.38]  # Default values
    
    bands = ['<$25k', '$25k–$100k', '$100k–$500k', '>$500k']
    winrates = []
    
    for band in bands:
        band_data = win_rate_df[win_rate_df['Deal_Size_Band'] == band]
        if not band_data.empty:
            total_won = band_data['IsWon'].sum()
            total_closed = len(band_data)
            win_rate = (total_won / total_closed) if total_closed > 0 else 0
        else:
            win_rate = 0
        winrates.append(win_rate)
    
    return winrates


def calculate_amounts_by_band(deal_size_df):
    """Calculate total amounts by band for Pareto chart"""
    if deal_size_df.empty:
        return [0, 0, 0, 0]
    
    # Assign new bands
    deal_size_df['Deal_Size_Band'] = deal_size_df['Professional_Services_Amount__c'].apply(assign_deal_size_band)
    
    bands = ['<$25k', '$25k–$100k', '$100k–$500k', '>$500k']
    amounts = []
    
    for band in bands:
        band_amount = deal_size_df[deal_size_df['Deal_Size_Band'] == band]['Professional_Services_Amount__c'].sum()
        amounts.append(int(band_amount))
    
    return amounts


def calculate_scatter_data(deal_size_df):
    """Calculate scatter plot data (deal size vs cycle time)"""
    if deal_size_df.empty or 'Cycle_Days' not in deal_size_df.columns:
        return []
    
    # Sample deals for scatter plot (limit to reasonable number)
    scatter_df = deal_size_df[deal_size_df['Cycle_Days'].notna()].copy()
    
    # Limit to reasonable sample size
    if len(scatter_df) > 500:
        scatter_df = scatter_df.sample(n=500, random_state=42)
    
    scatter_data = []
    for _, row in scatter_df.iterrows():
        deal_size = float(row['Professional_Services_Amount__c'])
        cycle_days = int(row['Cycle_Days'])
        outcome = "Won"  # All deals in deal_size_df are won
        scatter_data.append([deal_size, cycle_days, outcome])
    
    return scatter_data


def calculate_table_rows(deal_size_df, win_rate_df):
    """Calculate executive breakdown table rows"""
    if deal_size_df.empty:
        return []
    
    # Assign new bands
    deal_size_df['Deal_Size_Band'] = deal_size_df['Professional_Services_Amount__c'].apply(assign_deal_size_band)
    
    bands = ['<$25k', '$25k–$100k', '$100k–$500k', '>$500k']
    table_rows = []
    
    for band in bands:
        band_deals = deal_size_df[deal_size_df['Deal_Size_Band'] == band]
        
        if band_deals.empty:
            continue
        
        deals = len(band_deals)
        amount = band_deals['Professional_Services_Amount__c'].sum()
        median_cycle = band_deals['Cycle_Days'].median() if 'Cycle_Days' in band_deals.columns else 0
        
        # Calculate win rate for this band
        if not win_rate_df.empty and 'Deal_Size_Band' in win_rate_df.columns:
            band_wr = win_rate_df[win_rate_df['Deal_Size_Band'] == band]
            if not band_wr.empty:
                won = band_wr['IsWon'].sum()
                closed = len(band_wr)
                win_rate = (won / closed) if closed > 0 else 0
            else:
                win_rate = 0
        else:
            win_rate = 0  # All deals in deal_size_df are won, so 1.0
        
        table_rows.append({
            'band': band,
            'deals': int(deals),
            'amount': int(amount),
            'winrate': win_rate,
            'median_cycle': int(median_cycle) if not pd.isna(median_cycle) else 0
        })
    
    return table_rows


def calculate_kpis_with_deltas(deal_size_df, win_rate_df, deal_distributions):
    """Calculate KPIs with month-over-month deltas"""
    current_date = datetime.today()
    current_year = current_date.year
    current_month = current_date.month
    
    # YTD totals
    ytd_df = deal_size_df[deal_size_df['Year'] == current_year].copy()
    total_deals_ytd = len(ytd_df)
    total_amount_ytd = ytd_df['Professional_Services_Amount__c'].sum() if not ytd_df.empty else 0
    avg_deal_ytd = (total_amount_ytd / total_deals_ytd) if total_deals_ytd > 0 else 0
    
    # Previous month for comparison
    if current_month > 1:
        prev_month = current_month - 1
        prev_month_df = deal_size_df[
            (deal_size_df['Year'] == current_year) & 
            (deal_size_df['Month'] == prev_month)
        ].copy()
        prev_deals = len(prev_month_df)
        prev_amount = prev_month_df['Professional_Services_Amount__c'].sum() if not prev_month_df.empty else 0
        prev_avg = (prev_amount / prev_deals) if prev_deals > 0 else 0
    else:
        # Compare to December of previous year
        prev_month_df = deal_size_df[
            (deal_size_df['Year'] == current_year - 1) & 
            (deal_size_df['Month'] == 12)
        ].copy()
        prev_deals = len(prev_month_df)
        prev_amount = prev_month_df['Professional_Services_Amount__c'].sum() if not prev_month_df.empty else 0
        prev_avg = (prev_amount / prev_deals) if prev_deals > 0 else 0
    
    # Current month
    current_month_df = deal_size_df[
        (deal_size_df['Year'] == current_year) & 
        (deal_size_df['Month'] == current_month)
    ].copy()
    current_deals = len(current_month_df)
    current_amount = current_month_df['Professional_Services_Amount__c'].sum() if not current_month_df.empty else 0
    current_avg = (current_amount / current_deals) if current_deals > 0 else 0
    
    # Calculate deltas
    deals_delta_pct = ((current_deals - prev_deals) / prev_deals * 100) if prev_deals > 0 else 0
    amount_delta_pct = ((current_amount - prev_amount) / prev_amount * 100) if prev_amount > 0 else 0
    avg_delta_pct = ((current_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0
    
    # Win rate
    win_rate = 0
    win_rate_delta_str = "N/A"
    
    if not win_rate_df.empty and 'Year' in win_rate_df.columns:
        win_rate_ytd_df = win_rate_df[win_rate_df['Year'] == current_year].copy()
        if not win_rate_ytd_df.empty:
            total_won = win_rate_ytd_df['IsWon'].sum()
            total_closed = len(win_rate_ytd_df)
            win_rate = (total_won / total_closed) if total_closed > 0 else 0
            
            # Previous month win rate
            if current_month > 1:
                prev_month_wr = win_rate_df[
                    (win_rate_df['Year'] == current_year) & 
                    (win_rate_df['Month'] == prev_month)
                ]
            else:
                prev_month_wr = win_rate_df[
                    (win_rate_df['Year'] == current_year - 1) & 
                    (win_rate_df['Month'] == 12)
                ]
            
            if not prev_month_wr.empty:
                prev_won = prev_month_wr['IsWon'].sum()
                prev_closed = len(prev_month_wr)
                prev_win_rate = (prev_won / prev_closed) if prev_closed > 0 else 0
                win_rate_delta = (win_rate - prev_win_rate) * 100
                win_rate_delta_str = f"{win_rate_delta:+.1f} pts vs last month"
            else:
                win_rate_delta_str = "N/A"
    
    return {
        'total_deals': int(total_deals_ytd),
        'total_deals_delta': f"{deals_delta_pct:+.1f}% vs last month",
        'total_amount': int(total_amount_ytd),
        'total_amount_delta': f"{amount_delta_pct:+.1f}% vs last month",
        'avg_deal': int(avg_deal_ytd),
        'avg_deal_delta': f"{avg_delta_pct:+.1f}% vs last month",
        'winrate': win_rate,
        'winrate_delta': win_rate_delta_str
    }


# ==========================================================
# CREATE HTML DASHBOARD VISUALIZATIONS (OLD - TO BE REPLACED)
# ==========================================================
def create_deal_size_donut_chart(dist_df, period_label=""):
    """Create donut chart for deal size distribution"""
    if not PLOTLY_AVAILABLE or dist_df.empty:
        return None
    
    # Ensure Deal_Count is numeric
    deal_counts = pd.to_numeric(dist_df['Deal_Count'], errors='coerce').fillna(0).astype(int)
    labels = dist_df['Deal_Size_Band'].astype(str).tolist()
    values = deal_counts.tolist()
    
    # Define colors for bands
    band_colors = {
        '0-10k': '#3498db',  # Blue
        '10k-50k': '#9b59b6',  # Purple
        '50k-100k': '#f39c12',  # Orange
        '100k+': '#e74c3c'  # Red
    }
    
    colors = [band_colors.get(band, '#95a5a6') for band in labels]
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.5,
        marker=dict(colors=colors),
        textinfo='label+percent',
        textposition='outside',
        hovertemplate='<b>%{label}</b><br>' +
                      'Deals: %{value}<br>' +
                      'Percentage: %{percent}<br>' +
                      '<extra></extra>'
    )])
    
    fig.update_layout(
        title=dict(
            text=f"Deal Size Distribution<br><sub>{period_label}</sub>",
            x=0.5,
            font=dict(size=16, color='#2c3e50'),
            pad=dict(t=10, b=5)
        ),
        font=dict(family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", size=11, color='#2c3e50'),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5,
            font=dict(size=10),
            itemwidth=30
        ),
        margin=dict(l=20, r=20, t=50, b=70, pad=5),
        height=None,  # Let container control height
        autosize=True,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='closest'
    )
    
    return fig


def create_win_rate_heatmap(win_rate_by_rep):
    """Create heatmap for win rate by rep"""
    if not PLOTLY_AVAILABLE:
        return None
    
    # Combine all periods for heatmap
    all_reps = []
    for period, rep_df in win_rate_by_rep.items():
        if not rep_df.empty:
            rep_df_copy = rep_df.copy()
            rep_df_copy['Period'] = period
            all_reps.append(rep_df_copy)
    
    if not all_reps:
        return None
    
    combined_df = pd.concat(all_reps, ignore_index=True)
    
    # Pivot for heatmap
    heatmap_data = combined_df.pivot_table(
        values='Win_Rate_Pct',
        index='Rep_Name',
        columns='Period',
        aggfunc='mean'
    ).fillna(0)
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=heatmap_data.index,
        colorscale='RdYlGn',
        colorbar=dict(title="Win Rate %"),
        hovertemplate='Rep: %{y}<br>Period: %{x}<br>Win Rate: %{z:.2f}%<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(
            text="Win Rate Heatmap by Sales Rep",
            x=0.5,
            font=dict(size=16, color='#2c3e50'),
            pad=dict(t=10, b=5)
        ),
        xaxis_title="Period",
        yaxis_title="Sales Rep",
        font=dict(family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", size=11, color='#2c3e50'),
        height=None,  # Let container control height
        autosize=True,
        margin=dict(l=120, r=20, t=50, b=50, pad=5),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig


def create_deal_size_bubble_chart(distributions):
    """Create bubble chart comparing deal size distributions across periods"""
    if not PLOTLY_AVAILABLE:
        return None
    
    # Prepare data for bubble chart
    bubble_data = []
    for period, dist_data in distributions.items():
        if isinstance(dist_data, list):
            for dist_df in dist_data:
                if not dist_df.empty:
                    for _, row in dist_df.iterrows():
                        bubble_data.append({
                            'Period': dist_df.iloc[0]['Period'],
                            'Band': row['Deal_Size_Band'],
                            'Deal_Count': int(row['Deal_Count']),
                            'Avg_Amount': row['Avg_Amount'],
                            'Total_Amount': row['Total_Amount'],
                            'Year': int(dist_df.iloc[0].get('Year', 0))
                        })
        else:
            if not dist_data.empty:
                for _, row in dist_data.iterrows():
                    bubble_data.append({
                        'Period': dist_data.iloc[0]['Period'],
                        'Band': row['Deal_Size_Band'],
                        'Deal_Count': int(row['Deal_Count']),
                        'Avg_Amount': row['Avg_Amount'],
                        'Total_Amount': row['Total_Amount'],
                        'Year': int(dist_data.iloc[0].get('Year', 0))
                    })
    
    if not bubble_data:
        return None
    
    bubble_df = pd.DataFrame(bubble_data)
    
    fig = go.Figure()
    
    band_colors = {
        '0-10k': '#3498db',
        '10k-50k': '#9b59b6',
        '50k-100k': '#f39c12',
        '100k+': '#e74c3c'
    }
    
    for band in bubble_df['Band'].unique():
        band_data = bubble_df[bubble_df['Band'] == band]
        fig.add_trace(go.Scatter(
            x=band_data['Year'],
            y=band_data['Total_Amount'],
            mode='markers',
            name=band,
            marker=dict(
                size=band_data['Deal_Count'] * 2,
                color=band_colors.get(band, '#95a5a6'),
                sizemode='diameter',
                sizeref=2.*max(bubble_df['Deal_Count'])/(40.**2),
                sizemin=4,
                line=dict(width=1, color='white')
            ),
            text=[f"{band}<br>Deals: {c}<br>Total: ${t:,.0f}" 
                  for c, t in zip(band_data['Deal_Count'], band_data['Total_Amount'])],
            hovertemplate='%{text}<extra></extra>'
        ))
    
    fig.update_layout(
        title=dict(
            text="Deal Size Distribution Bubble Chart<br><sub>Size = Deal Count, Y-axis = Total Amount</sub>",
            x=0.5,
            font=dict(size=16, color='#2c3e50'),
            pad=dict(t=10, b=5)
        ),
        xaxis_title="Year",
        yaxis_title="Total Amount ($)",
        font=dict(family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", size=11, color='#2c3e50'),
        height=None,  # Let container control height
        autosize=True,
        hovermode='closest',
        margin=dict(l=60, r=20, t=60, b=50, pad=5),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig


def create_html_dashboard(deal_size_df, deal_distributions, win_rate_df, win_rate_by_rep):
    """Create Forrester-grade HTML dashboard using new facelift template"""
    if not PLOTLY_AVAILABLE:
        print("⚠️ Plotly not available - skipping HTML dashboard creation")
        return None
    
    print("\n" + "="*70)
    print("Generating HTML Dashboard (New Template)...")
    
    # Prepare all data for the new template
    template_data = prepare_template_data(deal_size_df, win_rate_df, deal_distributions)
    
    # Convert to JSON for JavaScript injection
    import json
    data_json = json.dumps(template_data, default=str, ensure_ascii=False)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"deal_size_win_rate_dashboard_{timestamp}.html"
    
    # Load the new template HTML structure
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Deal Size & Win Rate — Executive View</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root{{
      --bg: 255 255 255;
      --card: 248 250 252;
      --ink: 17 24 39;
      --muted: 100 116 139;
      --accent: 59 130 246;
      --accent-2: 99 102 241;
      --ring: 226 232 240;
    }}
    .dark{{
      --bg: 10 10 12;
      --card: 20 20 24;
      --ink: 229 231 235;
      --muted: 148 163 184;
      --accent: 96 165 250;
      --accent-2: 129 140 248;
      --ring: 38 38 45;
    }}
    body{{ font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
    .card{{
      background-color: rgb(var(--card));
      border: 1px solid rgb(var(--ring));
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 1px 2px rgb(0 0 0 / 0.05);
    }}
    .kpi{{
      border-radius: 14px;
      padding: 14px 16px;
      background: linear-gradient(180deg, rgb(var(--card)) 0%, rgba(0,0,0,0) 100%);
      border: 1px solid rgb(var(--ring));
    }}
    .title-gradient{{
      background: linear-gradient(90deg, rgb(var(--accent)) 0%, rgb(var(--accent-2)) 100%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }}
    .chip{{ 
      border: 1px solid rgb(var(--ring));
      border-radius: 9999px;
      padding: 2px 10px;
      font-size: 12px;
      color: rgb(var(--muted));
    }}
  </style>
</head>
<body class="bg-[rgb(var(--bg))] text-[rgb(var(--ink))]">
  <div class="max-w-7xl mx-auto p-6">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl sm:text-3xl font-semibold tracking-tight">
          <span class="title-gradient">Deal Size & Win Rate</span>
        </h1>
        <p class="text-sm text-[rgb(var(--muted))] mt-1">
          Executive view • optimized for clarity and decision velocity
        </p>
        <div id="metaChips" class="flex items-center gap-2 mt-2"></div>
      </div>
      <!-- Toggle -->
      <label class="inline-flex items-center cursor-pointer select-none">
        <span class="mr-3 text-sm text-[rgb(var(--muted))]">Light</span>
        <input type="checkbox" id="themeToggle" class="hidden" />
        <span class="relative w-14 h-7 bg-gray-300 dark:bg-gray-700 rounded-full transition">
          <span class="absolute left-1 top-1 w-5 h-5 bg-white rounded-full transition translate-x-0 dark:translate-x-7"></span>
        </span>
        <span class="ml-3 text-sm text-[rgb(var(--muted))]">Dark</span>
      </label>
    </div>

    <!-- KPI Row -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
      <div class="kpi">
        <div class="text-xs text-[rgb(var(--muted))]">Total Deals (YTD)</div>
        <div id="kpi_total_deals" class="text-2xl font-semibold mt-1">—</div>
        <div id="kpi_total_deals_delta" class="text-xs mt-2 text-[rgb(var(--muted))]"></div>
      </div>
      <div class="kpi">
        <div class="text-xs text-[rgb(var(--muted))]">Total Amount (YTD)</div>
        <div id="kpi_total_amount" class="text-2xl font-semibold mt-1">—</div>
        <div id="kpi_total_amount_delta" class="text-xs mt-2 text-[rgb(var(--muted))]"></div>
      </div>
      <div class="kpi">
        <div class="text-xs text-[rgb(var(--muted))]">Average Deal Size</div>
        <div id="kpi_avg_deal" class="text-2xl font-semibold mt-1">—</div>
        <div id="kpi_avg_deal_delta" class="text-xs mt-2 text-[rgb(var(--muted))]"></div>
      </div>
      <div class="kpi">
        <div class="text-xs text-[rgb(var(--muted))]">Overall Win Rate</div>
        <div id="kpi_winrate" class="text-2xl font-semibold mt-1">—</div>
        <div id="kpi_winrate_delta" class="text-xs mt-2 text-[rgb(var(--muted))]"></div>
      </div>
    </div>

    <!-- Grids -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
      <div class="card">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">Mix by Deal Size (100% stacked)</h2>
          <span class="chip">Distribution • by period</span>
        </div>
        <div id="chart_mix" class="mt-2" style="height:360px;"></div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">Win Rate by Deal Band</h2>
          <span class="chip">Dot plot</span>
        </div>
        <div id="chart_winrate" class="mt-2" style="height:360px;"></div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">Contribution by Band (Pareto)</h2>
          <span class="chip">Value concentration</span>
        </div>
        <div id="chart_pareto" class="mt-2" style="height:360px;"></div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">Deal Size vs Cycle Time</h2>
          <span class="chip">Bubble • color by outcome</span>
        </div>
        <div id="chart_scatter" class="mt-2" style="height:360px;"></div>
      </div>
    </div>

    <!-- Table -->
    <div class="card mt-6">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold">Executive Breakdown</h2>
        <span class="chip">Ranked by closed amount (YTD)</span>
      </div>
      <div class="overflow-x-auto mt-2">
        <table class="min-w-full text-sm">
          <thead class="text-left text-[rgb(var(--muted))]">
            <tr>
              <th class="py-2 pr-4">Deal Band</th>
              <th class="py-2 pr-4">Deals</th>
              <th class="py-2 pr-4">Closed Amount</th>
              <th class="py-2 pr-4">Win Rate</th>
              <th class="py-2 pr-4">Median Cycle</th>
            </tr>
          </thead>
          <tbody id="exec_rows"></tbody>
        </table>
      </div>
    </div>

    <footer class="text-[rgb(var(--muted))] text-xs mt-8">
      Generated from Salesforce data • {timestamp}
    </footer>
  </div>

<script>
// ======= DATA INJECTION =======
const DATA = {data_json};

// ======= THEME TOGGLE =======
const toggle = document.getElementById('themeToggle');
toggle.addEventListener('change', () => {{
  document.documentElement.classList.toggle('dark');
}});
// Persist user preference (optional)
if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
  document.documentElement.classList.add('dark');
  toggle.checked = true;
}}

// ======= RENDER META =======
const meta = document.getElementById('metaChips');
DATA.metadata.filters.forEach(f => {{
  const span = document.createElement('span');
  span.className = 'chip';
  span.textContent = f;
  meta.appendChild(span);
}});
const gen = document.createElement('span');
gen.className = 'chip';
gen.textContent = `Updated ${{DATA.metadata.generated}}`;
meta.appendChild(gen);

// ======= FORMATTERS =======
const fmtCurrency = (n)=> n.toLocaleString(undefined,{{style:'currency',currency:'USD',maximumFractionDigits:0}});
const fmtPct = (p)=> (p*100).toFixed(1)+'%';
const fmtDelta = (s)=> s.startsWith('-') ? `▼ ${{s.replace('-','')}}` : `▲ ${{s}}`;

// ======= KPIS =======
document.getElementById('kpi_total_deals').textContent = DATA.kpis.total_deals.toLocaleString();
document.getElementById('kpi_total_deals_delta').textContent = fmtDelta(DATA.kpis.total_deals_delta);
document.getElementById('kpi_total_amount').textContent = fmtCurrency(DATA.kpis.total_amount);
document.getElementById('kpi_total_amount_delta').textContent = fmtDelta(DATA.kpis.total_amount_delta);
document.getElementById('kpi_avg_deal').textContent = fmtCurrency(DATA.kpis.avg_deal);
document.getElementById('kpi_avg_deal_delta').textContent = fmtDelta(DATA.kpis.avg_deal_delta);
document.getElementById('kpi_winrate').textContent = fmtPct(DATA.kpis.winrate);
document.getElementById('kpi_winrate_delta').textContent = fmtDelta(DATA.kpis.winrate_delta);

// ======= MIX (100% STACKED) =======
(function(){{
  const traces = DATA.bands.map((band, j) => ({{
    x: DATA.periods,
    y: DATA.share.map(row => row[j]*100),
    name: band,
    type: 'bar',
    hovertemplate: '%{{y:.1f}}% ' + band + '<extra></extra>'
  }}));
  const layout = {{
    barmode: 'stack',
    xaxis: {{ tickangle: -10 }},
    yaxis: {{ title: 'Share of deals', ticksuffix:'%', rangemode:'tozero', range:[0,100] }},
    margin: {{l:40,r:12,t:8,b:40}},
    legend: {{ orientation:'h', x:0, y:1.15 }},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)'
  }};
  Plotly.newPlot('chart_mix', traces, layout, {{displayModeBar:false, responsive:true}});
}})();

// ======= WIN RATE DOT PLOT =======
(function(){{
  const trace = {{
    x: DATA.winrate.map(v=>v*100),
    y: DATA.bands,
    type: 'scatter',
    mode: 'markers',
    marker: {{ size: 12, line: {{ width: 1, color: 'rgba(0,0,0,0.25)'}} }},
    hovertemplate: '%{{y}}: %{{x:.1f}}%<extra></extra>'
  }};
  const layout = {{
    xaxis: {{ title: 'Win rate', ticksuffix:'%', range:[0,100] }},
    margin: {{l:110,r:20,t:8,b:40}},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)'
  }};
  Plotly.newPlot('chart_winrate', [trace], layout, {{displayModeBar:false, responsive:true}});
}})();

// ======= PARETO (bars + cumulative %) =======
(function(){{
  // sort bands by amount descending
  const pairs = DATA.bands.map((b,i)=>({{band:b, amt: DATA.amount[i]}}))
    .sort((a,b)=>b.amt-a.amt);
  const bands = pairs.map(p=>p.band);
  const amounts = pairs.map(p=>p.amt);
  const total = amounts.reduce((a,b)=>a+b,0);
  let cum = []; let run=0;
  for(const a of amounts){{ run+=a; cum.push( (run/total)*100 ); }}
  const bar = {{ x: bands, y: amounts, type:'bar', name:'Amount', hovertemplate:'%{{x}}: '+
      '%{{y:$,.0f}}<extra></extra>'}};
  const line = {{ x: bands, y: cum, type:'scatter', mode:'lines+markers', yaxis:'y2', name:'Cumulative %',
      hovertemplate:'%{{y:.1f}}%<extra></extra>'}};
  const layout = {{
    yaxis: {{ title:'Closed amount', rangemode:'tozero' }},
    yaxis2: {{ overlaying:'y', side:'right', ticksuffix:'%', range:[0,100] }},
    margin: {{l:60,r:50,t:8,b:40}},
    legend: {{ orientation:'h', x:0, y:1.15 }},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)'
  }};
  Plotly.newPlot('chart_pareto',[bar,line],layout,{{displayModeBar:false, responsive:true}});
}})();

// ======= SCATTER (bubble) =======
(function(){{
  const xs = DATA.scatter.map(d=>d[0]);
  const ys = DATA.scatter.map(d=>d[1]);
  const colors = DATA.scatter.map(d=> d[2]==='Won' ? '#22c55e' : '#ef4444');
  const trace = {{
    x: xs, y: ys, mode:'markers', type:'scatter',
    marker: {{ size: xs.map(v=>Math.max(6, Math.min(24, Math.sqrt(v)/8))), color: colors, opacity:0.85 }},
    hovertemplate:'Size: %{{x:$,.0f}}<br>Cycle: %{{y}} days<extra></extra>'
  }};
  const layout = {{
    xaxis: {{ title:'Deal size (USD)', tickprefix:'$', separatethousands:true }},
    yaxis: {{ title:'Sales cycle (days)' }},
    margin: {{l:60,r:12,t:8,b:60}},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)'
  }};
  Plotly.newPlot('chart_scatter', [trace], layout, {{displayModeBar:false, responsive:true}});
}})();

// ======= EXEC TABLE =======
(function(){{
  const tbody = document.getElementById('exec_rows');
  const rows = DATA.table_rows
    .sort((a,b)=>b.amount-a.amount)
    .map(r => `
      <tr class="border-t border-[rgb(var(--ring))]">
        <td class="py-2 pr-4 font-medium">${{r.band}}</td>
        <td class="py-2 pr-4">${{r.deals.toLocaleString()}}</td>
        <td class="py-2 pr-4">${{fmtCurrency(r.amount)}}</td>
        <td class="py-2 pr-4">${{fmtPct(r.winrate)}}</td>
        <td class="py-2 pr-4">${{r.median_cycle}} days</td>
      </tr>
    `).join('');
  tbody.innerHTML = rows;
}})();
</script>
</body>
</html>"""
    
    # Format the HTML with the data
    html_content = html_template.format(data_json=data_json, timestamp=timestamp)
    
    # Write the HTML file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML Dashboard generated: {filename}")
    return filename


# ==========================================================
# MAIN
# ==========================================================
def main():
    print("\n" + "="*70)
    print("DEAL SIZE & WIN RATE METRICS")
    print("Professional Services Revenue | Excluding Disqualified from Win Rate")
    print("="*70)

    # Connect to Salesforce
    sf = connect_to_salesforce()
    
    # Get Deal Size data (Professional Services Amount) - include cycle time for scatter plot
    deal_size_df = get_deal_size_data(sf, months_back=24, include_cycle_time=True)
    
    # Get Win Rate data (excluding Disqualified) - include deal size for win rate by band
    win_rate_df = get_win_rate_data(sf, months_back=24, include_deal_size=True)
    
    if deal_size_df.empty and win_rate_df.empty:
        print("\n⚠️ No opportunity data found. Exiting.")
        return
    
    # Show stage breakdown for validation
    if not win_rate_df.empty:
        show_stage_breakdown(win_rate_df)
    
    # Calculate Deal Size Distributions (YTD, QoQ, YoY)
    print("\n" + "="*70)
    print("CALCULATING DEAL SIZE DISTRIBUTIONS")
    print("="*70)
    
    deal_distributions = {}
    for period in ['YTD', 'QoQ', 'YoY']:
        deal_distributions[period] = calculate_deal_size_distribution(deal_size_df, period=period)
    
    display_deal_size_distribution(deal_distributions)
    
    # Calculate Win Rate by Rep (YTD, QoQ, YoY)
    print("\n" + "="*70)
    print("CALCULATING WIN RATE BY SALES REP")
    print("="*70)
    
    win_rate_by_rep = {}
    
    # YTD and QoQ: Active reps only
    for period in ['YTD', 'QoQ']:
        win_rate_by_rep[period] = calculate_win_rate_by_rep(win_rate_df, period=period, yoy_mode=False)
    
    # YoY: Include all reps who had closed won deals
    win_rate_by_rep['YoY'] = calculate_win_rate_by_rep(win_rate_df, period='YoY', yoy_mode=True)
    
    display_win_rate_by_rep(win_rate_by_rep)
    
    # Export data to CSV
    export_data(deal_size_df, deal_distributions, win_rate_df, win_rate_by_rep)
    
    # Generate HTML Dashboard
    if PLOTLY_AVAILABLE:
        create_html_dashboard(deal_size_df, deal_distributions, win_rate_df, win_rate_by_rep)
    
    print("\n" + "="*70)
    print("✅ METRICS COMPLETE")
    print("="*70)


def validate_against_report():
    """Validate script output against Salesforce report"""
    print("\n" + "="*70)
    print("VALIDATING AGAINST SALESFORCE REPORT")
    print("Report: YTD - Bookings (00OPQ000004oWNN2A2)")
    print("Expected: 711 deals, $20,730,051.50")
    print("="*70)

    # Connect to Salesforce
    sf = connect_to_salesforce()
    
    # Get Deal Size data matching report filters
    deal_size_df = get_deal_size_data(sf, validate_against_report=True)
    
    if deal_size_df.empty:
        print("\n⚠️ No opportunity data found matching report filters.")
        return
    
    # Summary comparison
    total_deals = len(deal_size_df)
    total_amount = deal_size_df['Professional_Services_Amount__c'].sum()
    
    print("\n" + "="*70)
    print("VALIDATION RESULTS")
    print("="*70)
    print(f"\n📊 Script Results:")
    print(f"   Total Deals: {total_deals}")
    print(f"   Total Professional Services Amount: ${total_amount:,.2f}")
    
    print(f"\n📊 Report Expected:")
    print(f"   Total Deals: 711")
    print(f"   Total Professional Services Amount: $20,730,051.50")
    
    print(f"\n📊 Differences:")
    deal_diff = total_deals - 711
    amount_diff = total_amount - 20730051.50
    
    print(f"   Deal Count: {deal_diff:+d} ({deal_diff/711*100:+.2f}%)")
    print(f"   Amount: ${amount_diff:+,.2f} ({amount_diff/20730051.50*100:+.2f}%)")
    
    if deal_diff == 0 and abs(amount_diff) < 0.01:
        print("\n✅ VALIDATION PASSED - Numbers match exactly!")
    else:
        print("\n⚠️ VALIDATION MISMATCH - Investigate differences")
    
    # Export validation data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    validation_file = f"validation_against_report_{timestamp}.csv"
    deal_size_df.to_csv(validation_file, index=False)
    print(f"\n📁 Validation data exported to: {validation_file}")


if __name__ == "__main__":
    import sys
    
    # Check if validation mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == "--validate":
        validate_against_report()
    else:
        main()
                position: relative;
                overflow: hidden;
                will-change: transform, box-shadow;
            }}
            
            .kpi-card::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 4px;
                height: 100%;
                background: var(--primary-gradient);
                transition: var(--transition);
                z-index: 0;
            }}
            
            .kpi-card > * {{
                position: relative;
                z-index: 1;
            }}
            
            .kpi-card:hover {{
                box-shadow: var(--shadow-md);
                transform: translateY(-2px);
                border-left-width: 6px;
            }}
            
            .kpi-card:active {{
                transform: translateY(0);
            }}
            
            .kpi-card h3 {{
                font-size: clamp(10px, 1.2vw, 13px);
                color: var(--text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 12px;
                font-weight: 600;
            }}
            
            .kpi-card .value {{
                font-size: clamp(28px, 4vw, 48px);
                font-weight: 700;
                color: var(--text-primary);
                margin-bottom: 8px;
                line-height: 1.1;
                letter-spacing: -0.02em;
            }}
            
            .kpi-card .label {{
                font-size: clamp(11px, 1.3vw, 14px);
                color: var(--text-tertiary);
                font-weight: 400;
            }}
            
            .chart-section {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(min(400px, 100%), 1fr));
                gap: clamp(16px, 2vw, 24px);
                margin-bottom: clamp(24px, 3vw, 40px);
            }}
            
            .chart-container {{
                background: var(--bg-primary);
                padding: clamp(20px, 2.5vw, 32px);
                border-radius: var(--radius-md);
                box-shadow: var(--shadow-sm);
                transition: var(--transition);
                min-height: 450px;
                display: flex;
                flex-direction: column;
                position: relative;
                overflow: hidden;
                will-change: box-shadow;
            }}
            
            .chart-container::after {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: var(--primary-gradient);
                opacity: 0;
                transition: opacity 0.3s;
            }}
            
            .chart-container:hover {{
                box-shadow: var(--shadow-md);
            }}
            
            .chart-container:hover::after {{
                opacity: 1;
            }}
            
            .chart-container:focus-within::after {{
                opacity: 1;
            }}
            
            .chart-container[style*="grid-column: 1 / -1"] {{
                grid-column: 1 / -1;
                min-height: 550px;
            }}
            
            .chart-title {{
                font-size: clamp(14px, 1.8vw, 20px);
                font-weight: 600;
                color: var(--text-primary);
                margin-bottom: clamp(16px, 2vw, 24px);
                padding-bottom: clamp(12px, 1.5vw, 16px);
                border-bottom: 2px solid var(--border-color);
                letter-spacing: -0.01em;
            }}
            
            .chart-container > div[id^="deal-size"],
            .chart-container > div[id^="win-rate"],
            .chart-container > div[id="bubble-chart"] {{
                flex: 1;
                min-height: 350px;
                width: 100%;
                position: relative;
            }}
            
            /* Ensure Plotly charts respect container */
            .chart-container > div > .js-plotly-plot {{
                width: 100% !important;
                height: 100% !important;
            }}
            
            /* Better chart sizing constraints */
            @supports (container-type: inline-size) {{
                .chart-container {{
                    container-type: inline-size;
                }}
            }}
            
            .footer {{
                text-align: center;
                color: var(--text-tertiary);
                font-size: clamp(10px, 1.2vw, 13px);
                margin-top: clamp(24px, 3vw, 40px);
                padding-top: clamp(16px, 2vw, 24px);
                border-top: 1px solid var(--border-color);
            }}
            
            /* Responsive breakpoints */
            @media (max-width: 1200px) {{
                .chart-section {{
                    grid-template-columns: repeat(auto-fit, minmax(min(350px, 100%), 1fr));
                }}
            }}
            
            @media (max-width: 768px) {{
                body {{
                    padding: 12px;
                }}
                
                .kpi-section {{
                    grid-template-columns: 1fr;
                }}
                
                .chart-section {{
                    grid-template-columns: 1fr;
                }}
                
                .chart-container[style*="grid-column: 1 / -1"] {{
                    grid-column: 1;
                }}
                
                .chart-container {{
                    min-height: 400px;
                }}
            }}
            
            @media (min-width: 1400px) {{
                .chart-container {{
                    min-height: 500px;
                }}
                
                .chart-container[style*="grid-column: 1 / -1"] {{
                    min-height: 600px;
                }}
                
                .kpi-section {{
                    gap: 32px;
                }}
                
                .chart-section {{
                    gap: 32px;
                }}
            }}
            
            /* Ultra-wide screens */
            @media (min-width: 1920px) {{
                .dashboard-container {{
                    max-width: 2000px;
                }}
                
                .chart-container {{
                    min-height: 550px;
                }}
                
                .chart-container[style*="grid-column: 1 / -1"] {{
                    min-height: 650px;
                }}
            }}
            
            /* Better mobile landscape */
            @media (max-width: 768px) and (orientation: landscape) {{
                .chart-container {{
                    min-height: 300px;
                }}
            }}
            
            /* Smooth animations */
            @keyframes fadeIn {{
                from {{
                    opacity: 0;
                    transform: translateY(10px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
            
            .kpi-card,
            .chart-container {{
                animation: fadeIn 0.5s ease-out;
            }}
            
            .kpi-card:nth-child(1) {{ animation-delay: 0.1s; }}
            .kpi-card:nth-child(2) {{ animation-delay: 0.2s; }}
            .kpi-card:nth-child(3) {{ animation-delay: 0.3s; }}
            .kpi-card:nth-child(4) {{ animation-delay: 0.4s; }}
            
            /* Loading states */
            .chart-container::before {{
                content: '';
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 40px;
                height: 40px;
                border: 3px solid var(--border-color);
                border-top-color: var(--primary-color);
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
                opacity: 0;
                transition: opacity 0.3s;
            }}
            
            @keyframes spin {{
                to {{
                    transform: translate(-50%, -50%) rotate(360deg);
                }}
            }}
            
            /* Better chart container sizing */
            .chart-section {{
                container-type: inline-size;
            }}
            
            @container (min-width: 500px) {{
                .chart-container {{
                    min-height: 450px;
                }}
            }}
            
            @container (min-width: 800px) {{
                .chart-container {{
                    min-height: 500px;
                }}
            }}
            
            /* Enhanced hover effects */
            .chart-container:focus-within {{
                box-shadow: var(--shadow-lg);
                outline: 2px solid var(--primary-color);
                outline-offset: 2px;
            }}
            
            /* Better spacing for stacked charts */
            .chart-section:has(.chart-container[style*="grid-column: 1 / -1"]) {{
                grid-template-rows: repeat(auto-fit, minmax(450px, auto)) 1fr;
            }}
            
            /* Smooth scroll */
            html {{
                scroll-padding-top: 20px;
            }}
            
            /* Focus visible for accessibility */
            *:focus-visible {{
                outline: 2px solid var(--primary-color);
                outline-offset: 2px;
                border-radius: 4px;
            }}
            
            /* Better text selection */
            ::selection {{
                background: var(--primary-color);
                color: white;
            }}
            
            /* Optimize font rendering */
            body,
            .kpi-card,
            .chart-title {{
                text-rendering: optimizeLegibility;
                -webkit-font-feature-settings: "kern" 1;
                font-feature-settings: "kern" 1;
                font-kerning: normal;
            }}
            
            /* Better number formatting */
            .kpi-card .value {{
                font-variant-numeric: tabular-nums;
                font-feature-settings: "tnum";
            }}
            
            /* Subtle gradient overlays for depth */
            .dashboard-header::after {{
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 1px;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
                pointer-events: none;
            }}
            
            /* Loading skeleton states */
            @keyframes pulse {{
                0%, 100% {{
                    opacity: 1;
                }}
                50% {{
                    opacity: 0.5;
                }}
            }}
            
            .chart-container:empty::before {{
                content: 'Loading chart...';
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: var(--text-tertiary);
                font-size: 14px;
                animation: pulse 2s ease-in-out infinite;
            }}
            
            /* Better grid alignment */
            .kpi-section,
            .chart-section {{
                align-items: stretch;
            }}
            
            /* Prevent text overflow */
            .kpi-card .value,
            .kpi-card .label,
            .chart-title {{
                overflow-wrap: break-word;
                word-wrap: break-word;
                hyphens: auto;
            }}
            
            /* Better spacing for long titles */
            .chart-title {{
                line-height: 1.3;
            }}
            
            /* Print styles */
            @media print {{
                body {{
                    background: white;
                    padding: 0;
                }}
                
                .kpi-card,
                .chart-container {{
                    break-inside: avoid;
                    page-break-inside: avoid;
                    box-shadow: none;
                    border: 1px solid #ddd;
                }}
                
                .dashboard-header {{
                    background: #667eea !important;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .kpi-card,
                .chart-container {{
                    border: 2px solid var(--text-primary);
                }}
                
                .kpi-card .value,
                .chart-title {{
                    color: var(--text-primary);
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                *,
                *::before,
                *::after {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            /* Dark mode support (for future) */
            @media (prefers-color-scheme: dark) {{
                /* Can be enabled later if needed */
            }}
        </style>
    </head>
    <body>
        <div class="dashboard-container">
        <div class="dashboard-header">
            <h1>Deal Size & Win Rate Executive Dashboard</h1>
            <p>Professional Services Revenue Analysis | Generated: {current_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <div class="kpi-section">
            <div class="kpi-card">
                <h3>Total Deals (YTD)</h3>
                <div class="value">{total_deals_ytd:,}</div>
                <div class="label">{current_year} Year-to-Date</div>
            </div>
            <div class="kpi-card">
                <h3>Total Amount (YTD)</h3>
                <div class="value">${total_amount_ytd:,.0f}</div>
                <div class="label">Professional Services Revenue</div>
            </div>
            <div class="kpi-card">
                <h3>Average Deal Size</h3>
                <div class="value">${avg_deal_size_ytd:,.0f}</div>
                <div class="label">YTD Average</div>
            </div>
            <div class="kpi-card">
                <h3>Overall Win Rate</h3>
                <div class="value">{overall_win_rate_ytd:.1f}%</div>
                <div class="label">{total_won_ytd} Won / {total_closed_ytd} Closed</div>
            </div>
        </div>
        
        <div class="chart-section">
"""
    
    # Add Deal Size Distribution charts
    all_figs = []
    
    for period, dist_data in deal_distributions.items():
        if period == 'YTD' and isinstance(dist_data, pd.DataFrame) and not dist_data.empty:
            fig = create_deal_size_donut_chart(dist_data, dist_data.iloc[0]['Period'])
            if fig:
                html_content += f"""
            <div class="chart-container">
                <div class="chart-title">Deal Size Distribution - {dist_data.iloc[0]['Period']}</div>
                <div id="deal-size-{period}"></div>
            </div>
"""
                all_figs.append((fig, f"deal-size-{period}"))
        
        elif isinstance(dist_data, list):
            # For QoQ and YoY, show comparison
            for idx, dist_df in enumerate(dist_data):
                if not dist_df.empty:
                    fig = create_deal_size_donut_chart(dist_df, dist_df.iloc[0]['Period'])
                    if fig:
                        div_id = f"deal-size-{period}-{idx}"
                        html_content += f"""
            <div class="chart-container">
                <div class="chart-title">Deal Size Distribution - {dist_df.iloc[0]['Period']}</div>
                <div id="{div_id}"></div>
            </div>
"""
                        all_figs.append((fig, div_id))
    
    # Add Win Rate Heatmap
    win_heatmap = create_win_rate_heatmap(win_rate_by_rep)
    if win_heatmap:
        html_content += f"""
            <div class="chart-container">
                <div class="chart-title">Win Rate Heatmap by Sales Rep</div>
                <div id="win-rate-heatmap"></div>
            </div>
"""
        all_figs.append((win_heatmap, "win-rate-heatmap"))
    
    # Add Bubble Chart
    bubble_chart = create_deal_size_bubble_chart(deal_distributions)
    if bubble_chart:
        html_content += f"""
            <div class="chart-container" style="grid-column: 1 / -1;">
                <div class="chart-title">Deal Size Distribution Over Time</div>
                <div id="bubble-chart"></div>
            </div>
"""
        all_figs.append((bubble_chart, "bubble-chart"))
    
    # Add all chart scripts - properly embed each chart with actual data
    html_content += "\n<script>\n"
    html_content += "// Wait for Plotly to load before creating charts\n"
    html_content += "(function() {\n"
    html_content += "  function initCharts() {\n"
    html_content += "    if (typeof Plotly === 'undefined') {\n"
    html_content += "      setTimeout(initCharts, 100);\n"
    html_content += "      return;\n"
    html_content += "    }\n"
    
    for fig, div_id in all_figs:
        # Build chart data by extracting actual values from traces
        chart_data = []
        for trace in fig.data:
            trace_dict = {}
            # Get trace type
            trace_type = trace.type if hasattr(trace, 'type') else 'scatter'
            trace_dict['type'] = trace_type
            
            # Extract common properties directly from trace
            trace_dict['name'] = getattr(trace, 'name', None)
            
            # Handle Pie charts (most common for our use case)
            if trace_type == 'pie':
                # Get labels and values directly
                if hasattr(trace, 'labels'):
                    labels_val = trace.labels
                    if isinstance(labels_val, np.ndarray):
                        trace_dict['labels'] = labels_val.tolist()
                    elif hasattr(labels_val, 'tolist'):
                        trace_dict['labels'] = labels_val.tolist()
                    else:
                        trace_dict['labels'] = list(labels_val) if labels_val is not None else []
                
                if hasattr(trace, 'values'):
                    values_val = trace.values
                    if isinstance(values_val, np.ndarray):
                        trace_dict['values'] = values_val.tolist()
                    elif hasattr(values_val, 'tolist'):
                        trace_dict['values'] = values_val.tolist()
                    elif isinstance(values_val, (list, tuple)):
                        trace_dict['values'] = [int(v) if isinstance(v, (np.integer, int)) else float(v) for v in values_val]
                    else:
                        trace_dict['values'] = [values_val] if values_val is not None else []
                
                # Get other pie properties
                for prop in ['hole', 'textinfo', 'textposition', 'hovertemplate']:
                    if hasattr(trace, prop):
                        val = getattr(trace, prop)
                        trace_dict[prop] = val
                
                # Handle marker separately - it's a Plotly Marker object, not a dict
                if hasattr(trace, 'marker'):
                    marker_obj = trace.marker
                    marker_dict = {}
                    # Extract marker properties
                    if hasattr(marker_obj, 'colors'):
                        colors = marker_obj.colors
                        if isinstance(colors, np.ndarray):
                            marker_dict['colors'] = colors.tolist()
                        elif hasattr(colors, 'tolist'):
                            marker_dict['colors'] = colors.tolist()
                        elif isinstance(colors, (list, tuple)):
                            marker_dict['colors'] = list(colors)
                        else:
                            marker_dict['colors'] = [colors] if colors else []
                    # Get any other marker properties
                    for mk_prop in ['line', 'opacity', 'size']:
                        if hasattr(marker_obj, mk_prop):
                            mk_val = getattr(marker_obj, mk_prop)
                            if isinstance(mk_val, dict):
                                marker_dict[mk_prop] = {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in mk_val.items()}
                            else:
                                marker_dict[mk_prop] = mk_val
                    trace_dict['marker'] = marker_dict
            
            # Handle Scatter charts (for bubble chart)
            elif trace_type == 'scatter':
                if hasattr(trace, 'x'):
                    x_val = trace.x
                    if isinstance(x_val, np.ndarray):
                        trace_dict['x'] = x_val.tolist()
                    elif hasattr(x_val, 'tolist'):
                        trace_dict['x'] = x_val.tolist()
                    else:
                        trace_dict['x'] = list(x_val) if x_val is not None else []
                
                if hasattr(trace, 'y'):
                    y_val = trace.y
                    if isinstance(y_val, np.ndarray):
                        trace_dict['y'] = y_val.tolist()
                    elif hasattr(y_val, 'tolist'):
                        trace_dict['y'] = y_val.tolist()
                    else:
                        trace_dict['y'] = list(y_val) if y_val is not None else []
                
                # Get other scatter properties
                for prop in ['mode', 'name', 'text', 'hovertemplate']:
                    if hasattr(trace, prop):
                        val = getattr(trace, prop)
                        trace_dict[prop] = val
                
                # Handle marker separately - it's a Plotly Marker object
                if hasattr(trace, 'marker'):
                    marker_obj = trace.marker
                    marker_dict = {}
                    # Extract marker properties
                    for mk_prop in ['color', 'colors', 'size', 'sizemode', 'sizeref', 'sizemin', 'line', 'opacity']:
                        if hasattr(marker_obj, mk_prop):
                            mk_val = getattr(marker_obj, mk_prop)
                            if isinstance(mk_val, np.ndarray):
                                marker_dict[mk_prop] = mk_val.tolist()
                            elif hasattr(mk_val, 'tolist'):
                                marker_dict[mk_prop] = mk_val.tolist()
                            elif isinstance(mk_val, dict):
                                marker_dict[mk_prop] = {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in mk_val.items()}
                            elif isinstance(mk_val, (np.integer, np.floating)):
                                marker_dict[mk_prop] = mk_val.item()
                            else:
                                marker_dict[mk_prop] = mk_val
                    trace_dict['marker'] = marker_dict
            
            # Handle Heatmap
            elif trace_type == 'heatmap':
                for prop in ['z', 'x', 'y', 'colorscale', 'colorbar', 'hovertemplate']:
                    if hasattr(trace, prop):
                        val = getattr(trace, prop)
                        if isinstance(val, np.ndarray):
                            trace_dict[prop] = val.tolist()
                        elif hasattr(val, 'tolist'):
                            trace_dict[prop] = val.tolist()
                        elif isinstance(val, dict):
                            trace_dict[prop] = {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in val.items()}
                        else:
                            trace_dict[prop] = val
            
            chart_data.append(trace_dict)
        
        # Build layout dict
        layout_dict = fig.layout.to_plotly_json()
        # Clean layout of any binary-encoded data
        def clean_layout(obj):
            if isinstance(obj, dict):
                if 'dtype' in obj and 'bdata' in obj:
                    return None  # Skip binary data
                return {k: clean_layout(v) for k, v in obj.items() if clean_layout(v) is not None}
            elif isinstance(obj, list):
                return [clean_layout(item) for item in obj]
            else:
                return obj
        
        clean_layout_dict = clean_layout(layout_dict)
        
        # Serialize to JSON
        var_name = div_id.replace('-', '_')
        data_json = json.dumps(chart_data, default=str, ensure_ascii=False)
        layout_json = json.dumps(clean_layout_dict, default=str, ensure_ascii=False)
        
        # Embed as JavaScript object with responsive config
        html_content += f"""
        var figure_data_{var_name} = {data_json};
        var figure_layout_{var_name} = {layout_json};
        var config_{var_name} = {{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
            toImageButtonOptions: {{
                format: 'png',
                filename: 'deal_size_chart',
                height: 500,
                width: 800,
                scale: 2
            }}
        }};
        Plotly.newPlot("{div_id}", figure_data_{var_name}, figure_layout_{var_name}, config_{var_name});
        
        // Make chart responsive on window resize with debouncing
        let resizeTimeout_{var_name};
        window.addEventListener('resize', function() {{
            clearTimeout(resizeTimeout_{var_name});
            resizeTimeout_{var_name} = setTimeout(function() {{
                Plotly.Plots.resize("{div_id}");
            }}, 250);
        }});
"""
    html_content += """
  }
  
  // Try to initialize immediately, or wait for load
  if (document.readyState === 'complete') {
    initCharts();
  } else {
    window.addEventListener('load', initCharts);
    document.addEventListener('DOMContentLoaded', function() {
      setTimeout(initCharts, 100);
    });
  }
})();

// Performance optimization: Intersection Observer for lazy chart rendering
        if ('IntersectionObserver' in window) {
            const chartObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const chartId = entry.target.id;
                        if (window['figure_data_' + chartId.replace(/-/g, '_')]) {
                            // Chart already loaded, just resize
                            Plotly.Plots.resize(chartId);
                        }
                        chartObserver.unobserve(entry.target);
                    }
                });
            }, {
                rootMargin: '50px',
                threshold: 0.1
            });
            
            // Observe all chart containers
            document.querySelectorAll('[id^="deal-size"], [id^="win-rate"], [id="bubble-chart"]').forEach(el => {
                chartObserver.observe(el);
            });
        }
        
        // Smooth scroll for accessibility
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
"""
    html_content += "</script>\n"
    
    html_content += """
        </div>
        </div>
        
        <div class="footer">
            <p>Generated by Deal Size & Win Rate Analysis Script | Professional Services Revenue Metrics</p>
        </div>
    </body>
    </html>
"""
    
    # Write HTML file
    with open(filename, 'w') as f:
        f.write(html_content)
    
    print(f"📊 HTML Dashboard exported to: {filename}")
    return filename


# ==========================================================
# MAIN
# ==========================================================
def main():
    print("\n" + "="*70)
    print("DEAL SIZE & WIN RATE METRICS")
    print("Professional Services Revenue | Excluding Disqualified from Win Rate")
    print("="*70)

    # Connect to Salesforce
    sf = connect_to_salesforce()
    
    # Get Deal Size data (Professional Services Amount) - include cycle time for scatter plot
    deal_size_df = get_deal_size_data(sf, months_back=24, include_cycle_time=True)
    
    # Get Win Rate data (excluding Disqualified) - include deal size for win rate by band
    win_rate_df = get_win_rate_data(sf, months_back=24, include_deal_size=True)
    
    if deal_size_df.empty and win_rate_df.empty:
        print("\n⚠️ No opportunity data found. Exiting.")
        return
    
    # Show stage breakdown for validation
    if not win_rate_df.empty:
        show_stage_breakdown(win_rate_df)
    
    # Calculate Deal Size Distributions (YTD, QoQ, YoY)
    print("\n" + "="*70)
    print("CALCULATING DEAL SIZE DISTRIBUTIONS")
    print("="*70)
    
    deal_distributions = {}
    for period in ['YTD', 'QoQ', 'YoY']:
        deal_distributions[period] = calculate_deal_size_distribution(deal_size_df, period=period)
    
    display_deal_size_distribution(deal_distributions)
    
    # Calculate Win Rate by Rep (YTD, QoQ, YoY)
    print("\n" + "="*70)
    print("CALCULATING WIN RATE BY SALES REP")
    print("="*70)
    
    win_rate_by_rep = {}
    
    # YTD and QoQ: Active reps only
    for period in ['YTD', 'QoQ']:
        win_rate_by_rep[period] = calculate_win_rate_by_rep(win_rate_df, period=period, yoy_mode=False)
    
    # YoY: Include all reps who had closed won deals
    win_rate_by_rep['YoY'] = calculate_win_rate_by_rep(win_rate_df, period='YoY', yoy_mode=True)
    
    display_win_rate_by_rep(win_rate_by_rep)
    
    # Export all data
    export_data(deal_size_df, deal_distributions, win_rate_df, win_rate_by_rep)
    
    # Create HTML dashboard
    if PLOTLY_AVAILABLE:
        print("\n" + "="*70)
        print("CREATING HTML DASHBOARD")
        print("="*70)
        create_html_dashboard(deal_size_df, deal_distributions, win_rate_df, win_rate_by_rep)
    
    print("\n" + "="*70)
    print("✅ METRICS COMPLETE")
    print("="*70)
    print("\n💡 Key Metrics Summary:")
    print("   ✓ Deal Size: Professional_Services_Amount__c (not Amount)")
    print("   ✓ Win Rate: Won / (Won + Lost) - EXCLUDES Disqualified")
    print("   ✓ Deal Size Bands: 0-10k, 10k-50k, 50k-100k, 100k+")
    print("   ✓ Win Rate by Rep: Active reps (YTD/QoQ), All with wins (YoY)")
    print("\n📊 All data exported to CSV for further analysis and visualization")


def validate_against_report():
    """Validate script output against Salesforce report"""
    print("\n" + "="*70)
    print("VALIDATING AGAINST SALESFORCE REPORT")
    print("Report: YTD - Bookings (00OPQ000004oWNN2A2)")
    print("Expected: 711 deals, $20,730,051.50")
    print("="*70)

    # Connect to Salesforce
    sf = connect_to_salesforce()
    
    # Get Deal Size data matching report filters
    deal_size_df = get_deal_size_data(sf, validate_against_report=True)
    
    if deal_size_df.empty:
        print("\n⚠️ No opportunity data found matching report filters.")
        return
    
    # Summary comparison
    total_deals = len(deal_size_df)
    total_amount = deal_size_df['Professional_Services_Amount__c'].sum()
    
    print("\n" + "="*70)
    print("VALIDATION RESULTS")
    print("="*70)
    print(f"\n📊 Script Results:")
    print(f"   Total Deals: {total_deals}")
    print(f"   Total Professional Services Amount: ${total_amount:,.2f}")
    
    print(f"\n📊 Report Expected:")
    print(f"   Total Deals: 711")
    print(f"   Total Professional Services Amount: $20,730,051.50")
    
    print(f"\n📊 Differences:")
    deal_diff = total_deals - 711
    amount_diff = total_amount - 20730051.50
    
    print(f"   Deal Count: {deal_diff:+d} ({deal_diff/711*100:+.2f}%)")
    print(f"   Amount: ${amount_diff:+,.2f} ({amount_diff/20730051.50*100:+.2f}%)")
    
    if deal_diff == 0 and abs(amount_diff) < 0.01:
        print("\n✅ VALIDATION PASSED - Numbers match exactly!")
    else:
        print("\n⚠️ VALIDATION MISMATCH - Investigate differences")
    
    # Export validation data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    validation_file = f"validation_against_report_{timestamp}.csv"
    deal_size_df.to_csv(validation_file, index=False)
    print(f"\n📁 Validation data exported to: {validation_file}")


if __name__ == "__main__":
    import sys
    
    # Check if validation mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == "--validate":
        validate_against_report()
    else:
        main()
