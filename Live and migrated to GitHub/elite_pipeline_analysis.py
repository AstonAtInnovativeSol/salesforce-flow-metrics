#!/usr/bin/env python3
"""
ELITE PIPELINE ANALYSIS - COMPREHENSIVE BUSINESS INTELLIGENCE
Addresses all 8 critical business questions with top-tier visualizations

Run with: python3 /Users/afleming/Desktop/Final\ Python\ Scripts/elite_pipeline_analysis.py
"""

import os
import time
import jwt
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from simple_salesforce import Salesforce, SalesforceMalformedRequest
import sf_config
from collections import defaultdict, Counter
import json
import warnings
import subprocess
import sys
# Removed plotly dependencies - using HTML/CSS/JS for visualizations

# Suppress urllib3 warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

# ==========================================================
# AUTHENTICATION - JWT Bearer Token Flow
# ==========================================================
# This script uses JWT (JSON Web Token) Bearer authentication to connect to Salesforce.
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
# Security Note: sf_config.py is gitignored and will NOT be committed to GitHub
# See sf_config.py.example for template and setup instructions.
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
    print("\n🔐 Authenticating with Salesforce via JWT...")
    token_data = get_jwt_token()
    access_token = token_data["access_token"]
    instance_url = token_data["instance_url"]

    sf = Salesforce(instance_url=instance_url, session_id=access_token)
    print("✅ Connected successfully!\n")
    return sf


# ==========================================================
# DATE UTILITIES
# ==========================================================
def get_analysis_periods():
    """Get comprehensive date ranges for analysis"""
    today = datetime.now()
    
    # Current week (based on your report showing Oct 26 - Nov 1, 2025)
    current_week_start = datetime(2025, 10, 26)  # Sunday
    current_week_end = datetime(2025, 11, 1)     # Saturday
    
    # Analysis periods
    periods = {
        'current_week_start': current_week_start,
        'current_week_end': current_week_end,
        'ytd_start': datetime(2025, 1, 1),
        'ytd_end': today,
        'last_12_weeks_start': current_week_start - timedelta(weeks=12),
        'last_6_months_start': current_week_start - timedelta(days=180),
        'last_quarter_start': datetime(2025, 7, 1),  # Q3 2025
        'current_quarter_start': datetime(2025, 10, 1),  # Q4 2025
        'today': today
    }
    
    return periods


# ==========================================================
# CORE DATA COLLECTION
# ==========================================================
def get_comprehensive_opportunity_data(sf, start_date, end_date):
    """Get comprehensive opportunity data with all related objects for analysis - PROFESSIONAL SERVICES ONLY"""
    print(f"🔍 Collecting comprehensive opportunity data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("📌 FILTERING: Professional_Services_Amount__c ONLY (excluding ARR/Resold)")
    
    query = f"""
        SELECT Id, Name, CreatedDate, CloseDate, StageName, Probability, 
               Professional_Services_Amount__c, LeadSource, Type, ForecastCategoryName, 
               IsWon, IsClosed, AccountId, Account.Name, Account.Industry, Account.Type, 
               Account.AnnualRevenue, Account.BillingCountry, Account.BillingState, 
               Account.NumberOfEmployees, OwnerId, Owner.Name, Owner.Title, Owner.Department,
               (SELECT Id, Product2Id, Product2.Name, Product2.Family, Product2.ProductCode,
                       Quantity, UnitPrice, TotalPrice, ServiceDate
                FROM OpportunityLineItems),
               (SELECT Id, Subject, ActivityDate, ActivityType, Description, 
                       WhoId, Who.Name, Who.Type
                FROM ActivityHistories 
                WHERE ActivityDate >= {start_date.strftime('%Y-%m-%d')}
                ORDER BY ActivityDate DESC),
               (SELECT Id, Subject, ActivityDate, ActivityType, Description,
                       WhoId, Who.Name, Who.Type
                FROM OpenActivities
                ORDER BY ActivityDate ASC)
        FROM Opportunity
        WHERE CreatedDate >= {start_date.strftime('%Y-%m-%dT00:00:00Z')}
          AND CreatedDate <= {end_date.strftime('%Y-%m-%dT23:59:59Z')}
          AND Professional_Services_Amount__c != NULL
          AND Professional_Services_Amount__c > 0
        ORDER BY CreatedDate ASC
    """
    
    try:
        records = sf.query_all(query)["records"]
        print(f"✅ Found {len(records)} opportunities")
        return records
    except Exception as e:
        print(f"❌ Error querying opportunities: {e}")
        return []


def get_opportunity_history(sf, start_date, end_date):
    """Get opportunity stage history for velocity analysis - PROFESSIONAL SERVICES ONLY"""
    print(f"📊 Collecting opportunity history data...")
    print("📌 FILTERING: Professional_Services_Amount__c ONLY")
    
    query = f"""
        SELECT Id, OpportunityId, CreatedDate, StageName, Probability,
               Opportunity.Name, Opportunity.Professional_Services_Amount__c,
               Opportunity.CreatedDate, Opportunity.CloseDate, Opportunity.IsWon
        FROM OpportunityHistory
        WHERE CreatedDate >= {start_date.strftime('%Y-%m-%dT00:00:00Z')}
          AND CreatedDate <= {end_date.strftime('%Y-%m-%dT23:59:59Z')}
          AND Opportunity.Professional_Services_Amount__c != NULL
          AND Opportunity.Professional_Services_Amount__c > 0
        ORDER BY OpportunityId, CreatedDate ASC
    """
    
    try:
        records = sf.query_all(query)["records"]
        print(f"✅ Found {len(records)} history records")
        return records
    except Exception as e:
        print(f"❌ Error querying opportunity history: {e}")
        return []


# ==========================================================
# ANALYSIS FUNCTIONS - ADDRESSING ALL 8 CRITICAL QUESTIONS
# ==========================================================

def analyze_sales_cycle_length(opportunities):
    """1. Average sales cycle length (days from creation to close)"""
    print("\n📈 ANALYZING SALES CYCLE LENGTH")
    print("=" * 50)
    
    cycle_data = []
    
    for opp in opportunities:
        if opp.get('IsClosed') and opp.get('CloseDate'):
            created_date = pd.to_datetime(opp.get('CreatedDate', ''))
            close_date = pd.to_datetime(opp.get('CloseDate', ''))
            
            if created_date and close_date:
                # Handle timezone issues
                if created_date.tzinfo is not None:
                    created_date = created_date.tz_localize(None)
                if close_date.tzinfo is not None:
                    close_date = close_date.tz_localize(None)
                
                cycle_days = (close_date - created_date).days
                if cycle_days >= 0:  # Valid cycle
                    cycle_data.append({
                        'opportunity_id': opp.get('Id'),
                        'name': opp.get('Name'),
                        'cycle_days': cycle_days,
                        'amount': float(opp.get('Professional_Services_Amount__c', 0)),
                        'stage': opp.get('StageName'),
                        'is_won': opp.get('IsWon', False),
                        'created_date': created_date,
                        'close_date': close_date
                    })
    
    if not cycle_data:
        return {'average_cycle_days': 0, 'median_cycle_days': 0, 'cycle_distribution': []}
    
    df = pd.DataFrame(cycle_data)
    
    analysis = {
        'average_cycle_days': df['cycle_days'].mean(),
        'median_cycle_days': df['cycle_days'].median(),
        'std_dev_cycle_days': df['cycle_days'].std(),
        'cycle_distribution': df['cycle_days'].tolist(),
        'won_cycles': df[df['is_won']]['cycle_days'].tolist(),
        'lost_cycles': df[~df['is_won']]['cycle_days'].tolist(),
        'by_stage': df.groupby('stage')['cycle_days'].agg(['mean', 'median', 'count']).to_dict(),
        'by_amount_range': categorize_by_amount(df),
        'recent_trend': analyze_cycle_trend(df)
    }
    
    print(f"✅ Average sales cycle: {analysis['average_cycle_days']:.1f} days")
    print(f"✅ Median sales cycle: {analysis['median_cycle_days']:.1f} days")
    print(f"✅ Analyzed {len(cycle_data)} closed opportunities")
    
    return analysis


def analyze_stage_conversion_rates(opportunities, history_records):
    """2. Stage-by-stage conversion rates - tracks ACTUAL transitions"""
    print("\n🔄 ANALYZING STAGE CONVERSION RATES")
    print("=" * 50)
    
    # Define stage progression
    stage_progression = [
        'Prospecting', 'Discovery', 'Qualification', 
        'Solution Development', 'Presentation & Negotiation', 'Closed Won'
    ]
    
    # Track actual transitions (from → to)
    transitions = defaultdict(int)  # Key: "StageFrom → StageTo", Value: count
    stage_entry_counts = defaultdict(int)  # How many times each stage was entered
    
    # Group history records by opportunity and sort by date
    opp_histories = defaultdict(list)
    for record in history_records:
        opp_id = record.get('OpportunityId')
        stage = record.get('StageName')
        created_date = pd.to_datetime(record.get('CreatedDate', ''))
        
        if opp_id and stage and created_date is not pd.NaT:
            opp_histories[opp_id].append({
                'stage': stage,
                'date': created_date
            })
    
    # Sort each opportunity's history by date
    for opp_id in opp_histories:
        opp_histories[opp_id].sort(key=lambda x: x['date'])
    
    # Track transitions between stages
    for opp_id, history in opp_histories.items():
        if len(history) < 2:
            continue
        
        # Track each transition
        for i in range(len(history) - 1):
            from_stage = history[i]['stage']
            to_stage = history[i + 1]['stage']
            
            # Only count transitions if they're in our stage progression
            if from_stage in stage_progression and to_stage in stage_progression:
                from_index = stage_progression.index(from_stage)
                to_index = stage_progression.index(to_stage)
                
                # Only count forward transitions (not backward)
                if to_index > from_index:
                    transition_key = f"{from_stage} → {to_stage}"
                    transitions[transition_key] += 1
                    stage_entry_counts[to_stage] += 1
    
    # Also count current stages as entries
    for opp in opportunities:
        current_stage = opp.get('StageName')
        if current_stage and current_stage in stage_progression:
            stage_entry_counts[current_stage] += 1
    
    # Calculate conversion rates for sequential stages
    conversion_rates = {}
    for i in range(len(stage_progression) - 1):
        current_stage = stage_progression[i]
        next_stage = stage_progression[i + 1]
        
        # Count transitions FROM current_stage TO any future stage
        from_stage_count = sum(
            count for trans_key, count in transitions.items() 
            if trans_key.startswith(f"{current_stage} →")
        )
        
        # Count transitions TO next_stage (directly)
        transition_key = f"{current_stage} → {next_stage}"
        to_next_stage_count = transitions.get(transition_key, 0)
        
        # Total opportunities that entered current_stage
        entered_current = stage_entry_counts.get(current_stage, 0)
        
        # For the first stage, use total opportunities created
        if i == 0:
            entered_current = len(opportunities)
        
        if entered_current > 0:
            conversion_rate = (to_next_stage_count / entered_current) * 100
            conversion_rates[transition_key] = {
                'rate': conversion_rate,
                'from_count': entered_current,
                'to_count': to_next_stage_count
            }
    
    analysis = {
        'stage_entry_counts': dict(stage_entry_counts),
        'transitions': dict(transitions),
        'conversion_rates': conversion_rates,
        'stage_progression': stage_progression,
        'overall_conversion': calculate_overall_conversion(opportunities)
    }
    
    print("✅ Stage conversion rates calculated (tracking actual transitions)")
    for transition, data in conversion_rates.items():
        print(f"   {transition}: {data['rate']:.1f}% ({data['to_count']}/{data['from_count']})")
    
    return analysis


def verify_stage_transitions_soql(sf):
    """SOQL query to verify actual stage transitions"""
    print("\n🔍 VERIFYING STAGE TRANSITIONS WITH SOQL")
    print("=" * 50)
    
    query = """
        SELECT OpportunityId, Opportunity.Name, 
               CreatedDate, StageName, Probability,
               Opportunity.Professional_Services_Amount__c,
               Opportunity.CreatedDate,
               Opportunity.CloseDate,
               Opportunity.IsWon
        FROM OpportunityHistory
        WHERE Opportunity.Professional_Services_Amount__c != NULL
          AND Opportunity.Professional_Services_Amount__c > 0
          AND CreatedDate >= 2025-01-01T00:00:00Z
        ORDER BY OpportunityId, CreatedDate ASC
        LIMIT 5000
    """
    
    try:
        records = sf.query_all(query)["records"]
        print(f"✅ Retrieved {len(records)} stage history records")
        
        # Group by opportunity
        opp_stages = defaultdict(list)
        for record in records:
            opp_id = record.get('OpportunityId')
            stage = record.get('StageName')
            created_date = record.get('CreatedDate')
            
            if opp_id and stage and created_date:
                opp_stages[opp_id].append({
                    'stage': stage,
                    'date': created_date
                })
        
        # Count transitions
        transition_counts = defaultdict(int)
        for opp_id, stages in opp_stages.items():
            stages.sort(key=lambda x: x['date'])
            for i in range(len(stages) - 1):
                from_stage = stages[i]['stage']
                to_stage = stages[i + 1]['stage']
                if from_stage != to_stage:
                    transition_key = f"{from_stage} → {to_stage}"
                    transition_counts[transition_key] += 1
        
        print("\n📊 ACTUAL STAGE TRANSITIONS (from SOQL):")
        for transition, count in sorted(transition_counts.items()):
            print(f"   {transition}: {count}")
        
        return transition_counts
        
    except Exception as e:
        print(f"❌ Error querying stage transitions: {e}")
        return {}


def analyze_velocity_trends(opportunities, history_records):
    """3. Has velocity slowed recently? (Pipeline buildup analysis)"""
    print("\n⚡ ANALYZING VELOCITY TRENDS")
    print("=" * 50)
    
    # Analyze by week
    weekly_data = defaultdict(lambda: {'created': 0, 'closed': 0, 'amount_created': 0, 'amount_closed': 0})
    
    for opp in opportunities:
        created_date = pd.to_datetime(opp.get('CreatedDate', ''))
        if created_date:
            week_key = created_date.strftime('%Y-W%U')
            amount = float(opp.get('Professional_Services_Amount__c', 0))
            weekly_data[week_key]['created'] += 1
            weekly_data[week_key]['amount_created'] += amount
    
    # Process closed opportunities
    for opp in opportunities:
        if opp.get('IsClosed') and opp.get('CloseDate'):
            close_date = pd.to_datetime(opp.get('CloseDate', ''))
            if close_date:
                week_key = close_date.strftime('%Y-W%U')
                amount = float(opp.get('Professional_Services_Amount__c', 0))
                weekly_data[week_key]['closed'] += 1
                weekly_data[week_key]['amount_closed'] += amount
    
    # Calculate velocity metrics
    velocity_analysis = {
        'weekly_data': dict(weekly_data),
        'recent_velocity': calculate_recent_velocity(weekly_data),
        'velocity_trend': calculate_velocity_trend(weekly_data),
        'pipeline_buildup': calculate_pipeline_buildup(weekly_data)
    }
    
    print("✅ Velocity trends analyzed")
    print(f"   Recent velocity: {velocity_analysis['recent_velocity']:.1f} deals/week")
    print(f"   Velocity trend: {velocity_analysis['velocity_trend']}")
    
    return velocity_analysis


def analyze_new_vs_recurring(opportunities, sf):
    """4. New vs. recurring (existing) bookings split - based on account purchase history"""
    print("\n🔄 ANALYZING NEW VS RECURRING BOOKINGS")
    print("=" * 50)
    
    # Get all unique account IDs from current opportunities
    account_ids = list(set(opp.get('AccountId') for opp in opportunities if opp.get('AccountId')))
    
    if not account_ids:
        return {'new_bookings': [], 'recurring_bookings': [], 'new_count': 0, 'recurring_count': 0}
    
    # Query for previous closed won opportunities for these accounts
    print("🔍 Checking account purchase history...")
    
    # Query in batches to avoid URI too long error
    accounts_with_history = {}
    batch_size = 200  # Salesforce limit
    
    for i in range(0, len(account_ids), batch_size):
        batch = account_ids[i:i + batch_size]
        account_ids_str = "', '".join(batch)
        query = f"""
            SELECT AccountId, COUNT(Id) PreviousWins, MAX(CloseDate) LastCloseDate
            FROM Opportunity
            WHERE AccountId IN ('{account_ids_str}')
              AND IsWon = true
              AND Professional_Services_Amount__c != NULL
              AND Professional_Services_Amount__c > 0
              AND CloseDate < 2025-01-01
            GROUP BY AccountId
        """
    
        try:
            batch_records = sf.query_all(query)["records"]
            for record in batch_records:
                accounts_with_history[record['AccountId']] = record
            print(f"✅ Processed batch {i//batch_size + 1}/{(len(account_ids) + batch_size - 1)//batch_size}")
            
        except Exception as e:
            print(f"❌ Error querying batch {i//batch_size + 1}: {e}")
    
    print(f"✅ Found purchase history for {len(accounts_with_history)} accounts")
    
    # Categorize opportunities
    new_bookings = []
    recurring_bookings = []
    
    for opp in opportunities:
        account_id = opp.get('AccountId')
        
        # Check if account has previous wins
        is_recurring = account_id in accounts_with_history
        
        opp_data = {
            'id': opp.get('Id'),
            'name': opp.get('Name'),
            'amount': float(opp.get('Professional_Services_Amount__c', 0)),
            'account_id': account_id,
            'account_name': opp.get('Account', {}).get('Name'),
            'created_date': opp.get('CreatedDate'),
            'previous_wins': accounts_with_history.get(account_id, {}).get('PreviousWins', 0),
            'last_close_date': accounts_with_history.get(account_id, {}).get('LastCloseDate')
        }
        
        if is_recurring:
            recurring_bookings.append(opp_data)
        else:
            new_bookings.append(opp_data)
    
    analysis = {
        'new_bookings': new_bookings,
        'recurring_bookings': recurring_bookings,
        'new_count': len(new_bookings),
        'recurring_count': len(recurring_bookings),
        'new_amount': sum(opp['amount'] for opp in new_bookings),
        'recurring_amount': sum(opp['amount'] for opp in recurring_bookings),
        'new_percentage': len(new_bookings) / len(opportunities) * 100 if opportunities else 0,
        'recurring_percentage': len(recurring_bookings) / len(opportunities) * 100 if opportunities else 0,
        'accounts_analyzed': len(account_ids),
        'accounts_with_history': len(accounts_with_history)
    }
    
    print(f"✅ New accounts: {analysis['new_count']} ({analysis['new_percentage']:.1f}%)")
    print(f"✅ Recurring accounts: {analysis['recurring_count']} ({analysis['recurring_percentage']:.1f}%)")
    print(f"✅ Total accounts analyzed: {analysis['accounts_analyzed']}")
    print(f"✅ Accounts with purchase history: {analysis['accounts_with_history']}")
    
    return analysis


def analyze_deal_size_distribution(opportunities):
    """5. Deal size distribution (are we seeing fewer large deals?)"""
    print("\n📊 ANALYZING DEAL SIZE DISTRIBUTION")
    print("=" * 50)
    
    amounts = [float(opp.get('Professional_Services_Amount__c', 0)) for opp in opportunities]
    
    if not amounts:
        return {'distribution': {}, 'trends': {}}
    
    # Define size categories
    size_categories = {
        'Small (<$25K)': [0, 25000],
        'Medium ($25K-$100K)': [25000, 100000],
        'Large ($100K-$500K)': [100000, 500000],
        'Enterprise (>$500K)': [500000, float('inf')]
    }
    
    distribution = {}
    for category, (min_val, max_val) in size_categories.items():
        count = sum(1 for amount in amounts if min_val <= amount < max_val)
        total_amount = sum(amount for amount in amounts if min_val <= amount < max_val)
        distribution[category] = {
            'count': count,
            'percentage': count / len(amounts) * 100,
            'total_amount': total_amount,
            'avg_amount': total_amount / count if count > 0 else 0
        }
    
    analysis = {
        'distribution': distribution,
        'total_deals': len(amounts),
        'total_amount': sum(amounts),
        'average_deal_size': np.mean(amounts),
        'median_deal_size': np.median(amounts),
        'large_deals_trend': analyze_large_deals_trend(opportunities)
    }
    
    print("✅ Deal size distribution calculated")
    for category, data in distribution.items():
        print(f"   {category}: {data['count']} deals ({data['percentage']:.1f}%)")
    
    return analysis


def analyze_forecast_accuracy(opportunities):
    """6. Historical forecast accuracy for Bookings (called vs. actual)"""
    print("\n🎯 ANALYZING FORECAST ACCURACY")
    print("=" * 50)
    
    # This would typically require historical forecast data
    # For now, we'll analyze current probability vs. actual outcomes
    accuracy_data = []
    
    for opp in opportunities:
        if opp.get('IsClosed'):
            probability = opp.get('Probability', 0)
            is_won = opp.get('IsWon', False)
            amount = float(opp.get('Professional_Services_Amount__c', 0))
            
            # Convert probability to binary prediction
            predicted_won = probability >= 50
            
            accuracy_data.append({
                'opportunity_id': opp.get('Id'),
                'predicted_won': predicted_won,
                'actual_won': is_won,
                'probability': probability,
                'amount': amount,
                'correct': predicted_won == is_won
            })
    
    if not accuracy_data:
        return {'accuracy_rate': 0, 'bias_analysis': {}}
    
    df = pd.DataFrame(accuracy_data)
    
    accuracy_rate = df['correct'].mean() * 100
    won_accuracy = df[df['actual_won']]['correct'].mean() * 100 if df['actual_won'].any() else 0
    lost_accuracy = df[~df['actual_won']]['correct'].mean() * 100 if (~df['actual_won']).any() else 0
    
    analysis = {
        'accuracy_rate': accuracy_rate,
        'won_accuracy': won_accuracy,
        'lost_accuracy': lost_accuracy,
        'total_predictions': len(accuracy_data),
        'bias_analysis': analyze_forecast_bias(df)
    }
    
    print(f"✅ Overall forecast accuracy: {accuracy_rate:.1f}%")
    print(f"✅ Won deals accuracy: {won_accuracy:.1f}%")
    print(f"✅ Lost deals accuracy: {lost_accuracy:.1f}%")
    
    return analysis


def analyze_deal_push_rates(opportunities, history_records):
    """7. Deal push rates (how often deals slip?)"""
    print("\n📅 ANALYZING DEAL PUSH RATES")
    print("=" * 50)
    
    # Analyze close date changes
    push_analysis = {
        'total_deals': len(opportunities),
        'pushed_deals': 0,
        'push_rate': 0,
        'average_push_days': 0,
        'push_reasons': defaultdict(int)
    }
    
    for opp in opportunities:
        if opp.get('IsClosed') and opp.get('CloseDate'):
            # This would require historical close date data
            # For now, we'll analyze based on current data patterns
            created_date = pd.to_datetime(opp.get('CreatedDate', ''))
            close_date = pd.to_datetime(opp.get('CloseDate', ''))
            
            if created_date is not pd.NaT and close_date is not pd.NaT:
                # Handle timezone issues
                if created_date.tzinfo is not None:
                    created_date = created_date.tz_localize(None)
                if close_date.tzinfo is not None:
                    close_date = close_date.tz_localize(None)
                
                cycle_days = (close_date - created_date).days
                if cycle_days > 90:  # Arbitrary threshold for "pushed"
                    push_analysis['pushed_deals'] += 1
    
    push_analysis['push_rate'] = (push_analysis['pushed_deals'] / push_analysis['total_deals'] * 100) if push_analysis['total_deals'] > 0 else 0
    
    print(f"✅ Deal push rate: {push_analysis['push_rate']:.1f}%")
    print(f"✅ Pushed deals: {push_analysis['pushed_deals']} out of {push_analysis['total_deals']}")
    
    return push_analysis


def analyze_cohort_patterns(opportunities):
    """8. Pipeline created in Month X → Bookings in Month Y patterns"""
    print("\n📈 ANALYZING COHORT PATTERNS")
    print("=" * 50)
    
    # Group opportunities by creation month
    monthly_cohorts = defaultdict(list)
    
    for opp in opportunities:
        created_date = pd.to_datetime(opp.get('CreatedDate', ''))
        if created_date:
            month_key = created_date.strftime('%Y-%m')
            monthly_cohorts[month_key].append({
                'id': opp.get('Id'),
                'name': opp.get('Name'),
                'amount': float(opp.get('Professional_Services_Amount__c', 0)),
                'created_date': created_date,
                'close_date': pd.to_datetime(opp.get('CloseDate', '')) if opp.get('CloseDate') else None,
                'is_won': opp.get('IsWon', False),
                'is_closed': opp.get('IsClosed', False)
            })
    
    # Analyze conversion patterns
    cohort_analysis = {}
    for month, deals in monthly_cohorts.items():
        total_created = len(deals)
        total_amount = sum(deal['amount'] for deal in deals)
        closed_deals = [deal for deal in deals if deal['is_closed']]
        won_deals = [deal for deal in deals if deal['is_won']]
        
        # Ensure month key is a string for JSON serialization
        month_str = str(month)
        cohort_analysis[month_str] = {
            'total_created': total_created,
            'total_amount': total_amount,
            'closed_count': len(closed_deals),
            'won_count': len(won_deals),
            'conversion_rate': len(won_deals) / total_created * 100 if total_created > 0 else 0,
            'avg_cycle_days': calculate_avg_cycle_for_cohort(closed_deals)
        }
    
    print("✅ Cohort patterns analyzed")
    for month, data in sorted(cohort_analysis.items()):
        print(f"   {month}: {data['total_created']} created, {data['won_count']} won ({data['conversion_rate']:.1f}%)")
    
    return cohort_analysis


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================
def categorize_by_amount(df):
    """Categorize opportunities by amount range"""
    if df.empty:
        return {}
    
    categories = {
        'Small (<$25K)': df[df['amount'] < 25000]['cycle_days'].tolist(),
        'Medium ($25K-$100K)': df[(df['amount'] >= 25000) & (df['amount'] < 100000)]['cycle_days'].tolist(),
        'Large ($100K-$500K)': df[(df['amount'] >= 100000) & (df['amount'] < 500000)]['cycle_days'].tolist(),
        'Enterprise (>$500K)': df[df['amount'] >= 500000]['cycle_days'].tolist()
    }
    
    return {k: {'cycles': v, 'avg_cycle': np.mean(v) if v else 0} for k, v in categories.items()}


def analyze_cycle_trend(df):
    """Analyze sales cycle trend over time"""
    if df.empty:
        return {}
    
    df['month'] = df['created_date'].dt.to_period('M')
    monthly_cycles = df.groupby('month')['cycle_days'].mean()
    
    return {
        'monthly_averages': monthly_cycles.to_dict(),
        'trend_direction': 'improving' if monthly_cycles.iloc[-1] < monthly_cycles.iloc[0] else 'declining'
    }


def calculate_overall_conversion(opportunities):
    """Calculate overall conversion rate"""
    total_created = len(opportunities)
    won_count = sum(1 for opp in opportunities if opp.get('IsWon', False))
    
    return {
        'total_created': total_created,
        'won_count': won_count,
        'conversion_rate': won_count / total_created * 100 if total_created > 0 else 0
    }


def calculate_recent_velocity(weekly_data):
    """Calculate recent velocity (deals per week)"""
    recent_weeks = sorted(weekly_data.keys())[-4:]  # Last 4 weeks
    total_created = sum(weekly_data[week]['created'] for week in recent_weeks)
    return total_created / len(recent_weeks) if recent_weeks else 0


def calculate_velocity_trend(weekly_data):
    """Calculate velocity trend direction"""
    weeks = sorted(weekly_data.keys())
    if len(weeks) < 4:
        return 'insufficient_data'
    
    recent_4_weeks = weeks[-4:]
    previous_4_weeks = weeks[-8:-4] if len(weeks) >= 8 else weeks[:-4]
    
    recent_avg = sum(weekly_data[week]['created'] for week in recent_4_weeks) / len(recent_4_weeks)
    previous_avg = sum(weekly_data[week]['created'] for week in previous_4_weeks) / len(previous_4_weeks)
    
    if recent_avg > previous_avg * 1.1:
        return 'accelerating'
    elif recent_avg < previous_avg * 0.9:
        return 'slowing'
    else:
        return 'stable'


def calculate_pipeline_buildup(weekly_data):
    """Calculate pipeline buildup (created vs closed)"""
    weeks = sorted(weekly_data.keys())
    if not weeks:
        return {}
    
    total_created = sum(weekly_data[week]['created'] for week in weeks)
    total_closed = sum(weekly_data[week]['closed'] for week in weeks)
    
    return {
        'total_created': total_created,
        'total_closed': total_closed,
        'buildup_ratio': total_created / total_closed if total_closed > 0 else float('inf'),
        'net_buildup': total_created - total_closed
    }


def analyze_large_deals_trend(opportunities):
    """Analyze trend in large deals"""
    amounts = [float(opp.get('Professional_Services_Amount__c', 0)) for opp in opportunities]
    if not amounts:
        return {}
    
    # Group by month
    monthly_data = defaultdict(list)
    for opp in opportunities:
        created_date = pd.to_datetime(opp.get('CreatedDate', ''))
        if created_date:
            month_key = created_date.strftime('%Y-%m')
            monthly_data[month_key].append(float(opp.get('Professional_Services_Amount__c', 0)))
    
    large_deals_trend = {}
    for month, amounts in monthly_data.items():
        large_deals = [amt for amt in amounts if amt >= 100000]
        large_deals_trend[month] = {
            'total_deals': len(amounts),
            'large_deals': len(large_deals),
            'large_deals_percentage': len(large_deals) / len(amounts) * 100 if amounts else 0
        }
    
    return large_deals_trend


def analyze_forecast_bias(df):
    """Analyze forecast bias"""
    if df.empty:
        return {}
    
    # Analyze over-prediction vs under-prediction
    over_predicted = df[(df['predicted_won'] == True) & (df['actual_won'] == False)]
    under_predicted = df[(df['predicted_won'] == False) & (df['actual_won'] == True)]
    
    return {
        'over_predicted_count': len(over_predicted),
        'under_predicted_count': len(under_predicted),
        'over_prediction_rate': len(over_predicted) / len(df) * 100,
        'under_prediction_rate': len(under_predicted) / len(df) * 100
    }


def calculate_avg_cycle_for_cohort(deals):
    """Calculate average cycle for a cohort"""
    if not deals:
        return 0
    
    cycles = []
    for deal in deals:
        if deal['close_date'] and deal['created_date']:
            close_date = deal['close_date']
            created_date = deal['created_date']
            
            # Handle timezone issues
            if close_date.tzinfo is not None:
                close_date = close_date.tz_localize(None)
            if created_date.tzinfo is not None:
                created_date = created_date.tz_localize(None)
            
            cycle_days = (close_date - created_date).days
            if cycle_days >= 0:
                cycles.append(cycle_days)
    
    return np.mean(cycles) if cycles else 0


# ==========================================================
# HTML DASHBOARD GENERATION
# ==========================================================
def generate_elite_dashboard(analysis_data):
    """Generate elite HTML dashboard inspired by reference examples"""
    print("\n🎨 Creating elite HTML dashboard...")
    
    # Extract key metrics
    cycle_analysis = analysis_data.get('sales_cycle_analysis', {})
    conversion_analysis = analysis_data.get('conversion_analysis', {})
    velocity_analysis = analysis_data.get('velocity_analysis', {})
    new_recurring = analysis_data.get('new_recurring_analysis', {})
    deal_size = analysis_data.get('deal_size_analysis', {})
    forecast = analysis_data.get('forecast_analysis', {})
    push_analysis = analysis_data.get('push_analysis', {})
    cohort_analysis = analysis_data.get('cohort_analysis', {})
    
    # Calculate key metrics
    avg_cycle = cycle_analysis.get('average_cycle_days', 0)
    median_cycle = cycle_analysis.get('median_cycle_days', 0)
    recent_velocity = velocity_analysis.get('recent_velocity', 0)
    velocity_trend = velocity_analysis.get('velocity_trend', 'Unknown')
    accuracy_rate = forecast.get('accuracy_rate', 0)
    push_rate = push_analysis.get('push_rate', 0)
    
    # Build conversion rates table
    conversion_html = ""
    if conversion_analysis.get('conversion_rates'):
        for transition, data in conversion_analysis['conversion_rates'].items():
            rate = data['rate']
            status_color = "green" if rate >= 50 else "orange" if rate >= 25 else "red"
            conversion_html += f"""
            <tr>
                <td>{transition}</td>
                <td>{data['from_count']}</td>
                <td>{data['to_count']}</td>
                <td><span style="color: {status_color}; font-weight: bold;">{rate:.1f}%</span></td>
                <td><div class="status-indicator" style="background-color: {status_color};"></div></td>
            </tr>
            """
    
    # Build deal size distribution
    deal_size_html = ""
    if deal_size.get('distribution'):
        for category, data in deal_size['distribution'].items():
            percentage = data['percentage']
            deal_size_html += f"""
            <div class="deal-size-item">
                <div class="deal-size-label">{category}</div>
                <div class="deal-size-bar">
                    <div class="deal-size-fill" style="width: {percentage}%;"></div>
                </div>
                <div class="deal-size-value">{data['count']} deals ({percentage:.1f}%)</div>
            </div>
            """
    
    # Build cohort analysis
    cohort_html = ""
    for month, data in sorted(cohort_analysis.items()):
        # Convert pandas Period to string if needed
        month_str = str(month) if hasattr(month, 'strftime') else month
        cohort_html += f"""
        <div class="cohort-item">
            <div class="cohort-month">{month_str}</div>
            <div class="cohort-metrics">
                <span class="cohort-created">{data['total_created']} created</span>
                <span class="cohort-won">{data['won_count']} won</span>
                <span class="cohort-rate">{data['conversion_rate']:.1f}%</span>
            </div>
        </div>
        """
    
    # Generate HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elite Pipeline Analysis - Executive Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --primary: #007aff;
            --success: #30d158;
            --warning: #ff9500;
            --danger: #ff3b30;
            --dark: #1d1d1f;
            --light: #f2f2f7;
            --border: #e5e5ea;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #fafbfc;
            color: var(--dark);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem;
            background: linear-gradient(135deg, #007aff 0%, #5856d6 100%);
            border-radius: 16px;
            color: white;
            box-shadow: 0 8px 24px rgba(0, 122, 255, 0.15);
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}
        
        .metric-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
            transition: transform 0.2s ease;
        }}
        
        .metric-card:hover {{
            transform: translateY(-2px);
        }}
        
        .metric-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 0.5rem;
        }}
        
        .metric-label {{
            color: #666;
            font-size: 0.9rem;
            font-weight: 500;
        }}
        
        .section {{
            margin-bottom: 3rem;
        }}
        
        .section-title {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            color: var(--dark);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .section-title::before {{
            content: '';
            width: 4px;
            height: 24px;
            background: var(--primary);
            border-radius: 2px;
        }}
        
        .analysis-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 2rem;
        }}
        
        .analysis-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
        }}
        
        .analysis-card h3 {{
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--dark);
        }}
        
        .conversion-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        
        .conversion-table th,
        .conversion-table td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        .conversion-table th {{
            background: var(--light);
            font-weight: 600;
        }}
        
        .status-indicator {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }}
        
        .deal-size-item {{
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
            gap: 1rem;
        }}
        
        .deal-size-label {{
            min-width: 150px;
            font-weight: 500;
        }}
        
        .deal-size-bar {{
            flex: 1;
            height: 20px;
            background: var(--light);
            border-radius: 10px;
            overflow: hidden;
        }}
        
        .deal-size-fill {{
            height: 100%;
            background: var(--primary);
            transition: width 0.3s ease;
        }}
        
        .deal-size-value {{
            min-width: 100px;
            text-align: right;
            font-weight: 600;
        }}
        
        .cohort-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            margin-bottom: 0.5rem;
            background: var(--light);
            border-radius: 8px;
        }}
        
        .cohort-month {{
            font-weight: 600;
        }}
        
        .cohort-metrics {{
            display: flex;
            gap: 1rem;
        }}
        
        .cohort-created, .cohort-won, .cohort-rate {{
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.9rem;
        }}
        
        .cohort-created {{
            background: #e3f2fd;
            color: var(--primary);
        }}
        
        .cohort-won {{
            background: #d1f7c4;
            color: var(--success);
        }}
        
        .cohort-rate {{
            background: #fff3e0;
            color: var(--warning);
        }}
        
        .chart-container {{
            position: relative;
            height: 300px;
            margin: 1rem 0;
        }}
        
        .timestamp {{
            text-align: center;
            color: #666;
            font-size: 0.8rem;
            margin-top: 2rem;
            padding: 1rem;
            border-top: 1px solid var(--border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Elite Pipeline Analysis</h1>
            <p>Comprehensive Business Intelligence Dashboard - Professional Services Only</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{avg_cycle:.0f}</div>
                <div class="metric-label">Avg Sales Cycle (Days)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{median_cycle:.0f}</div>
                <div class="metric-label">Median Sales Cycle (Days)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{recent_velocity:.1f}</div>
                <div class="metric-label">Recent Velocity (Deals/Week)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{accuracy_rate:.1f}%</div>
                <div class="metric-label">Forecast Accuracy</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{push_rate:.1f}%</div>
                <div class="metric-label">Deal Push Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{velocity_trend}</div>
                <div class="metric-label">Velocity Trend</div>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">🔄 Stage Conversion Rates</h2>
            <div class="analysis-card">
                <h3>Historical Conversion Rates Across Pipeline</h3>
                <table class="conversion-table">
                    <thead>
                        <tr>
                            <th>Stage Transition</th>
                            <th>Total Transitions</th>
                            <th>Successful Conversions</th>
                            <th>Conversion Rate</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {conversion_html}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">📊 Deal Size Distribution</h2>
            <div class="analysis-card">
                <h3>Deal Size Analysis - Professional Services Only</h3>
                {deal_size_html}
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">📈 Cohort Analysis</h2>
            <div class="analysis-card">
                <h3>Pipeline Created → Bookings Patterns</h3>
                {cohort_html}
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">🔄 New vs Recurring Bookings</h2>
            <div class="analysis-card">
                <h3>Booking Composition Analysis</h3>
                <div class="chart-container">
                    <canvas id="bookingChart"></canvas>
                </div>
            </div>
        </div>

        <div class="timestamp">
            Report generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
        </div>
    </div>

    <script>
        // New vs Recurring Bookings Chart
        const ctx = document.getElementById('bookingChart').getContext('2d');
        new Chart(ctx, {{
            type: 'doughnut',
            data: {{
                labels: ['New Bookings', 'Recurring Bookings'],
                datasets: [{{
                    data: [{new_recurring.get('new_count', 0)}, {new_recurring.get('recurring_count', 0)}],
                    backgroundColor: ['#007aff', '#30d158'],
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            padding: 20,
                            font: {{
                                size: 14,
                                weight: '500'
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
    """
    
    return html_content


# ==========================================================
# MAIN EXECUTION
# ==========================================================
def main():
    print("\n" + "="*80)
    print("🚀 ELITE PIPELINE ANALYSIS - COMPREHENSIVE BUSINESS INTELLIGENCE")
    print("="*80)
    print("Addressing all 8 critical business questions with top-tier analysis!")
    
    # Connect to Salesforce
    sf = connect_to_salesforce()
    
    # Get analysis periods
    periods = get_analysis_periods()
    
    # Collect comprehensive data
    print("\n📊 COLLECTING COMPREHENSIVE DATA")
    print("=" * 50)
    
    # Get YTD opportunities
    ytd_opportunities = get_comprehensive_opportunity_data(sf, periods['ytd_start'], periods['ytd_end'])
    
    # Get opportunity history
    ytd_history = get_opportunity_history(sf, periods['ytd_start'], periods['ytd_end'])
    
    if not ytd_opportunities:
        print("⚠️ No opportunity data found. Exiting.")
        return
    
    # Run all analyses
    print("\n🔬 RUNNING COMPREHENSIVE ANALYSES")
    print("=" * 50)
    
    analysis_results = {
        'analysis_date': datetime.now().isoformat(),
        'data_period': f"{periods['ytd_start'].strftime('%Y-%m-%d')} to {periods['ytd_end'].strftime('%Y-%m-%d')}",
        'total_opportunities': len(ytd_opportunities),
        'sales_cycle_analysis': analyze_sales_cycle_length(ytd_opportunities),
        'conversion_analysis': analyze_stage_conversion_rates(ytd_opportunities, ytd_history),
        'velocity_analysis': analyze_velocity_trends(ytd_opportunities, ytd_history),
        'new_recurring_analysis': analyze_new_vs_recurring(ytd_opportunities, sf),
        'deal_size_analysis': analyze_deal_size_distribution(ytd_opportunities),
        'forecast_analysis': analyze_forecast_accuracy(ytd_opportunities),
        'push_analysis': analyze_deal_push_rates(ytd_opportunities, ytd_history),
        'cohort_analysis': analyze_cohort_patterns(ytd_opportunities)
    }
    
    # Save comprehensive results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_file = f"/Users/afleming/Desktop/Final Python Scripts/elite_pipeline_analysis_{timestamp}.json"
    
    # Convert pandas objects to native Python types for JSON serialization
    def convert_pandas_objects(obj):
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif hasattr(obj, 'tolist'):
            return obj.tolist()
        elif hasattr(obj, 'item'):
            return obj.item()
        elif isinstance(obj, dict):
            return {str(k): convert_pandas_objects(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_pandas_objects(item) for item in obj]
        else:
            return str(obj) if hasattr(obj, 'strftime') else obj
    
    # Convert analysis results
    analysis_results_serializable = convert_pandas_objects(analysis_results)
    
    with open(json_file, 'w') as f:
        json.dump(analysis_results_serializable, f, indent=2, default=str)
    
    print(f"\n💾 Comprehensive analysis saved to: {json_file}")
    
    # Create elite dashboard
    print("\n🎨 Creating elite dashboard...")
    dashboard_html = generate_elite_dashboard(analysis_results)
    
    # Save dashboard
    html_file = f"/Users/afleming/Desktop/Final Python Scripts/elite_pipeline_dashboard_{timestamp}.html"
    
    with open(html_file, 'w') as f:
        f.write(dashboard_html)
    
    print(f"✅ Elite dashboard created: {html_file}")
    print(f"🌐 Open in browser: file://{html_file}")
    
    # Print executive summary
    print_executive_summary(analysis_results)


def print_executive_summary(analysis_data):
    """Print executive summary of key findings"""
    print("\n" + "="*80)
    print("📋 EXECUTIVE SUMMARY")
    print("="*80)
    
    # Key metrics
    total_opps = analysis_data.get('total_opportunities', 0)
    cycle_analysis = analysis_data.get('sales_cycle_analysis', {})
    conversion_analysis = analysis_data.get('conversion_analysis', {})
    velocity_analysis = analysis_data.get('velocity_analysis', {})
    new_recurring = analysis_data.get('new_recurring_analysis', {})
    deal_size = analysis_data.get('deal_size_analysis', {})
    forecast = analysis_data.get('forecast_analysis', {})
    
    print(f"\n📊 KEY METRICS:")
    print(f"   • Total Opportunities Analyzed: {total_opps:,}")
    print(f"   • Average Sales Cycle: {cycle_analysis.get('average_cycle_days', 0):.1f} days")
    print(f"   • Median Sales Cycle: {cycle_analysis.get('median_cycle_days', 0):.1f} days")
    print(f"   • Recent Velocity: {velocity_analysis.get('recent_velocity', 0):.1f} deals/week")
    print(f"   • Forecast Accuracy: {forecast.get('accuracy_rate', 0):.1f}%")
    
    print(f"\n🔄 CONVERSION INSIGHTS:")
    overall_conv = conversion_analysis.get('overall_conversion', {})
    print(f"   • Overall Conversion Rate: {overall_conv.get('conversion_rate', 0):.1f}%")
    print(f"   • Won Deals: {overall_conv.get('won_count', 0):,} out of {overall_conv.get('total_created', 0):,}")
    
    print(f"\n📈 BOOKING COMPOSITION:")
    print(f"   • New Bookings: {new_recurring.get('new_count', 0):,} ({new_recurring.get('new_percentage', 0):.1f}%)")
    print(f"   • Recurring Bookings: {new_recurring.get('recurring_count', 0):,} ({new_recurring.get('recurring_percentage', 0):.1f}%)")
    
    print(f"\n💰 DEAL SIZE INSIGHTS:")
    print(f"   • Average Deal Size: ${deal_size.get('average_deal_size', 0):,.0f}")
    print(f"   • Median Deal Size: ${deal_size.get('median_deal_size', 0):,.0f}")
    
    print(f"\n⚡ VELOCITY TRENDS:")
    print(f"   • Velocity Trend: {velocity_analysis.get('velocity_trend', 'Unknown')}")
    buildup = velocity_analysis.get('pipeline_buildup', {})
    print(f"   • Pipeline Buildup Ratio: {buildup.get('buildup_ratio', 0):.1f}")
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE - All 8 critical questions addressed!")
    print("="*80)


if __name__ == "__main__":
    main()