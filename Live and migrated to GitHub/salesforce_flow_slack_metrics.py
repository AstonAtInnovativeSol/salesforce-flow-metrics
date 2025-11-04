#!/usr/bin/env python3
"""
Salesforce Flow Slack Alert Metrics Tracker
Tracks Flow execution metrics for Slack alerts:
- Number of alerts sent
- Response time
- Closed out value

Usage:
    python3 salesforce_flow_slack_metrics.py 

Configuration:
    - Set FLOW_URL_1 and FLOW_URL_2 in the script or as environment variables
    - Or pass flow IDs directly as FLOW_ID_1 and FLOW_ID_2

JWT Authentication Setup:
    This script uses JWT (JSON Web Token) Bearer authentication to connect to Salesforce.
    
    Required Configuration (in sf_config.py - NOT committed to GitHub):
    - SF_USERNAME: Your Salesforce username (e.g., 'user@example.com')
    - SF_CONSUMER_KEY: Connected App Consumer Key from Salesforce
    - SF_DOMAIN: 'login' for production, 'test' for sandbox
    - PRIVATE_KEY_FILE: Path to your RSA private key file (.pem)
    
    Setup Steps:
    1. Create a Connected App in Salesforce:
       - Setup → App Manager → New Connected App
       - Enable OAuth Settings
       - Enable "Use digital signatures" and upload your public certificate
       - Note the Consumer Key
    2. Generate RSA key pair:
       - openssl genrsa -out server.key 2048
       - openssl req -new -x509 -key server.key -out server.crt -days 365
    3. Upload the certificate to your Connected App
    4. Create sf_config.py (copy from sf_config.py.example):
       - Fill in your credentials
       - Store private key securely (NOT in repository)
    
    Security Note:
    - sf_config.py is gitignored and will NOT be committed to GitHub
    - Never commit private keys, consumer keys, or passwords
    - Use environment variables or secure secret management in production
"""

import os
import re
import time
import jwt
import requests
import json
import csv
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from simple_salesforce import Salesforce, SalesforceMalformedRequest
import sf_config
from collections import defaultdict
from typing import Dict, List, Optional

# ==========================================================
# CONFIGURATION
# ==========================================================
# Flow URLs - Update these with your actual Flow URLs
# Or set as environment variables: FLOW_URL_1, FLOW_URL_2
FLOW_URL_1 = os.getenv('FLOW_URL_1', 'https://innovativesolutions.lightning.force.com/builder_platform_interaction/flowBuilder.app?flowId=301PQ00000iX6QRYA0')
FLOW_URL_2 = os.getenv('FLOW_URL_2', 'https://innovativesolutions.lightning.force.com/builder_platform_interaction/flowBuilder.app?flowId=301PQ00000iMEFuYAO')

# Alternative: Set Flow IDs directly
FLOW_ID_1 = os.getenv('FLOW_ID_1', '301PQ00000iX6QRYA0')  # Ghost Pipeline
FLOW_ID_2 = os.getenv('FLOW_ID_2', '301PQ00000iMEFuYAO')  # Past Due Closed Date

# Custom Opportunity fields that track alert dates (if your Flows populate these)
GHOST_PIPELINE_ALERT_FIELD = 'Ghost_Pipeline_Alert_Sent_Date__c'  # Custom field for Ghost Pipeline alerts
PAST_DUE_ALERT_FIELD = 'Overdue_Alert_Sent_Date__c'  # Custom field for Past Due Closed Date alerts

# Salesforce instance URL (extracted from Flow URLs)
SALESFORCE_INSTANCE = 'innovativesolutions.lightning.force.com'  # Default, will be extracted from flow URL

# Time window for analysis (days back)
DEFAULT_DAYS_BACK = 90  # Extended to 90 days for better metrics

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
# FLOW ID EXTRACTION
# ==========================================================
def extract_flow_id_from_url(url: str) -> Optional[str]:
    """
    Extract Flow ID from various Salesforce Flow URL formats
    
    Supports:
    - /builder_platform_interaction/apex/platformInteractions?flowId=301xx000000XXXX
    - /setup/home/home.jsp?setupid=Flows&id=301xx000000XXXX
    - Direct Flow ID: 301xx000000XXXX
    """
    if not url:
        return None
    
    # If it's already just an ID (15 or 18 chars starting with 301)
    if re.match(r'^301[a-zA-Z0-9]{12,15}$', url):
        return url
    
    # Extract from query parameters
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    # Check for flowId parameter
    if 'flowId' in params:
        return params['flowId'][0]
    
    # Check for id parameter
    if 'id' in params:
        flow_id = params['id'][0]
        if flow_id.startswith('301'):
            return flow_id
    
    # Try to extract from path
    path_match = re.search(r'301[a-zA-Z0-9]{12,15}', url)
    if path_match:
        return path_match.group(0)
    
    return None


def get_flow_name(sf, flow_id: str) -> str:
    """Get Flow name from Flow ID - Flow object is not queryable via SOQL, use ID mapping"""
    # Map known Flow IDs to names
    flow_name_map = {
        '301PQ00000iX6QRYA0': 'Ghost Pipeline',
        '301PQ00000iMEFuYAO': 'Past Due Closed Date'
    }
    
    if flow_id in flow_name_map:
        return flow_name_map[flow_id]
    
    return f'Flow {flow_id[:15]}'


# ==========================================================
# FLOW EXECUTION DATA COLLECTION
# ==========================================================
def get_flow_executions(sf, flow_id: str, days_back: int = DEFAULT_DAYS_BACK) -> List[Dict]:
    """
    Get Flow execution records (FlowInterview) for a specific Flow
    
    Note: FlowInterview doesn't have FlowDefinitionId directly.
    We'll query all recent FlowInterviews and filter by FlowVersionId.
    FlowVersionId references FlowVersion, which has a FlowId field.
    
    FlowInterview fields:
    - Id: Interview ID
    - CreatedDate: When flow started
    - CreatedBy: Who triggered it
    - InterviewStatus: Success, Failed, Paused, etc.
    - CurrentElement: Current step in flow
    - FlowVersionId: Version of the flow (references FlowVersion)
    - InterviewLabel: Label for the interview
    - Guid: Unique identifier
    """
    try:
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        # First, try to get FlowVersionId from FlowVersion that matches our Flow ID
        # Query FlowVersion to find versions for this Flow
        flow_version_query = f"""
        SELECT Id, FlowId, Label
        FROM FlowVersion
        WHERE FlowId = '{flow_id}'
          AND Status = 'Active'
        ORDER BY VersionNumber DESC
        LIMIT 10
        """
        
        flow_version_ids = []
        try:
            # Note: FlowVersion is not queryable via SOQL in most orgs - this is expected to fail
            version_result = sf.query_all(flow_version_query)
            flow_version_ids = [v['Id'] for v in version_result['records']]
            if flow_version_ids:
                print(f"📊 Found {len(flow_version_ids)} active Flow versions")
        except Exception as e:
            # This is expected - FlowVersion isn't queryable via SOQL
            # Silently skip and use custom field tracking instead
            pass
        
        # Query FlowInterview records - if we have version IDs, filter by them
        if flow_version_ids:
            # Build WHERE clause with multiple FlowVersionId values
            version_ids_str = "', '".join(flow_version_ids)
            query = f"""
            SELECT 
                Id, 
                CreatedDate, 
                CreatedBy.Name, 
                CreatedBy.Email,
                InterviewStatus, 
                CurrentElement,
                FlowVersionId,
                InterviewLabel,
                Guid
            FROM FlowInterview 
            WHERE FlowVersionId IN ('{version_ids_str}')
              AND CreatedDate >= {start_date}
            ORDER BY CreatedDate DESC
            """
        else:
            # Fallback: query all recent FlowInterviews (we'll filter by custom field tracking)
            query = f"""
            SELECT 
                Id, 
                CreatedDate, 
                CreatedBy.Name, 
                CreatedBy.Email,
                InterviewStatus, 
                CurrentElement,
                FlowVersionId,
                InterviewLabel,
                Guid
            FROM FlowInterview 
            WHERE CreatedDate >= {start_date}
            ORDER BY CreatedDate DESC
            LIMIT 1000
            """
        
        try:
            result = sf.query_all(query)
            executions = result['records']
            
            if executions:
                print(f"✅ Found {len(executions)} Flow execution records")
            
            return executions
        
        except Exception as e:
            # FlowInterview queries often fail - this is expected in many orgs
            # Will use custom field tracking instead, which is more reliable
            pass
        
        return []
    
    except Exception as e:
        # FlowInterview is not reliably queryable - expected to fail
        # Will use custom field tracking instead
        return []


def get_flow_execution_details(sf, interview_ids: List[str]) -> Dict:
    """
    Get detailed execution information
    
    For Slack alerts, we might also want to check:
    - PlatformEventBusSubscriber records (for platform events)
    - Custom log objects if they exist
    """
    details = {}
    
    try:
        # Query for any related records or logs
        # This is a placeholder - adjust based on your Flow's logging setup
        if interview_ids:
            ids_str = "', '".join(interview_ids[:200])  # Limit to 200 IDs
            
            # Example: Query for Platform Events if flows use them
            # query = f"SELECT Id, CreatedDate, Payload FROM PlatformEventBusSubscriber WHERE ..."
            
            pass
    
    except Exception as e:
        print(f"⚠️  Could not get detailed execution info: {e}")
    
    return details


# ==========================================================
# DATE PARSING HELPER
# ==========================================================
def parse_salesforce_datetime(date_str: str) -> Optional[datetime]:
    """
    Parse Salesforce datetime string with various formats
    Handles: +0000, +00:00, Z, and other timezone formats
    """
    if not isinstance(date_str, str):
        return None
    
    try:
        # Start with the original string
        date_str_clean = date_str.strip()
        
        # Handle Z timezone
        if date_str_clean.endswith('Z'):
            date_str_clean = date_str_clean.replace('Z', '+00:00')
        
        # Handle +0000 format (replace all occurrences)
        if '+0000' in date_str_clean:
            date_str_clean = date_str_clean.replace('+0000', '+00:00')
        if '-0000' in date_str_clean:
            date_str_clean = date_str_clean.replace('-0000', '-00:00')
        
        # Try parsing with timezone
        try:
            return datetime.fromisoformat(date_str_clean)
        except ValueError:
            # Try parsing without timezone - extract just the date/time part
            if '+' in date_str_clean:
                date_part = date_str_clean.split('+')[0].rstrip()
            elif '-' in date_str_clean[-6:]:  # Timezone at end
                # Find the last '-' that might be timezone (format: -00:00 or -0000)
                parts = date_str_clean.rsplit('-', 1)
                if len(parts) == 2 and len(parts[1]) <= 5:  # Likely timezone
                    date_part = parts[0]
                else:
                    date_part = date_str_clean
            else:
                date_part = date_str_clean
            
            # Ensure it has time component
            if 'T' not in date_part:
                date_part = date_part + 'T00:00:00'
            elif date_part.count('T') == 1:
                time_part = date_part.split('T')[1]
                if len(time_part) < 8:  # Incomplete time
                    date_part = date_part.split('T')[0] + 'T00:00:00'
            
            # Parse without timezone
            parsed = datetime.fromisoformat(date_part)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    
    except Exception:
        return None


# ==========================================================
# RESPONSE TIME CALCULATION
# ==========================================================
def calculate_response_time(sf, flow_executions: List[Dict], flow_id: str, alert_field: Optional[str] = None) -> Dict:
    """
    Calculate response time metrics
    
    Response time = Time from Flow execution (alert sent) to related record update/close
    
    If alert_field is provided (custom field like Ghost_Pipeline_Alert_Sent_Date__c),
    we can directly query Opportunities with that field populated and calculate
    response time from alert date to LastModifiedDate/CloseDate.
    """
    response_times = []
    
    try:
        # Method 1: Use custom alert date field if available (more accurate)
        if alert_field:
            try:
                # First try current field values
                query = f"""
                SELECT 
                    Id, 
                    {alert_field}, 
                    LastModifiedDate, 
                    CloseDate, 
                    StageName, 
                    Amount,
                    IsClosed,
                    IsWon
                FROM Opportunity
                WHERE {alert_field} != null
                  AND {alert_field} >= LAST_N_DAYS:{DEFAULT_DAYS_BACK}
                ORDER BY {alert_field} DESC
                """
                
                result = sf.query_all(query)
                
                # If no current values, try Field History (for fields that get cleared)
                if not result.get('records'):
                    result = {'records': []}  # Initialize if empty
                    try:
                        history_query = f"""
                        SELECT 
                            OpportunityId,
                            NewValue,
                            CreatedDate
                        FROM OpportunityFieldHistory
                        WHERE Field = '{alert_field}'
                          AND NewValue != null
                          AND CreatedDate >= LAST_N_DAYS:{DEFAULT_DAYS_BACK}
                        ORDER BY CreatedDate DESC
                        """
                        history_result = sf.query_all(history_query)
                        
                        if history_result.get('records'):
                            # Get opportunity details for history records
                            opp_ids = list(set([h['OpportunityId'] for h in history_result['records']]))
                            if opp_ids:
                                opp_ids_str = "', '".join(opp_ids[:200])  # Limit to 200
                                opp_query = f"""
                                SELECT 
                                    Id, 
                                    LastModifiedDate, 
                                    CloseDate, 
                                    StageName, 
                                    Amount,
                                    IsClosed,
                                    IsWon
                                FROM Opportunity
                                WHERE Id IN ('{opp_ids_str}')
                                """
                                opp_result = sf.query_all(opp_query)
                                
                                # Merge history dates with opportunity data
                                history_map = {{h['OpportunityId']: h for h in history_result['records']}}
                                for opp in opp_result.get('records', []):
                                    if opp['Id'] in history_map:
                                        history_record = history_map[opp['Id']]
                                        opp[alert_field] = history_record['CreatedDate']  # Use history date as alert date
                                        result['records'].append(opp)
                    except Exception as history_error:
                        # Field History not available - continue with empty result
                        pass
                
                for opp in result['records']:
                    if not opp.get(alert_field):
                        continue
                    
                    # Get alert sent date using helper function
                    alert_date_str = opp.get(alert_field)
                    alert_date = parse_salesforce_datetime(alert_date_str)
                    if not alert_date:
                        continue
                    
                    # Calculate response time to LastModifiedDate (when opportunity was updated after alert)
                    last_modified_str = opp.get('LastModifiedDate')
                    if last_modified_str:
                        try:
                            last_modified = parse_salesforce_datetime(last_modified_str)
                            if last_modified and last_modified > alert_date:
                                response_hours = (last_modified - alert_date).total_seconds() / 3600
                                if 0 < response_hours < 720:  # Within 30 days
                                    response_times.append(response_hours)
                        except Exception:
                            pass  # Skip this record if date parsing fails
                    
                    # Also calculate time to close if closed
                    if opp.get('IsClosed') and opp.get('CloseDate'):
                        close_date_str = opp.get('CloseDate')
                        try:
                            # CloseDate is typically just a date, not datetime
                            close_date = datetime.fromisoformat(close_date_str + 'T00:00:00')
                            if close_date > alert_date:
                                response_hours = (close_date - alert_date).total_seconds() / 3600
                                if 0 < response_hours < 720:  # Within 30 days
                                    response_times.append(response_hours)
                        except Exception:
                            pass  # Skip this record if date parsing fails
                
                if response_times:
                    response_times.sort()
                    return {
                        'avg_response_hours': sum(response_times) / len(response_times),
                        'median_response_hours': response_times[len(response_times) // 2],
                        'min_response_hours': min(response_times),
                        'max_response_hours': max(response_times),
                        'total_with_response': len(response_times),
                        'method': 'custom_field'
                    }
            
            except Exception as e:
                print(f"⚠️  Could not use custom field method: {e}")
                print("   Falling back to Flow execution method...")
        
        # Method 2: Fallback to Flow execution time correlation
        if not flow_executions:
            return {
                'avg_response_hours': 0,
                'median_response_hours': 0,
                'min_response_hours': 0,
                'max_response_hours': 0,
                'total_with_response': 0,
                'method': 'none'
            }
        
        # Get execution times
        for execution in flow_executions[:50]:  # Limit to 50 for performance
            exec_time = datetime.fromisoformat(execution['CreatedDate'].replace('Z', '+00:00'))
            
            # Look for Opportunities updated within 48 hours after Flow execution
            window_start = exec_time
            window_end = exec_time + timedelta(hours=48)
            
            try:
                query = f"""
                SELECT Id, LastModifiedDate, CloseDate, StageName, Amount
                FROM Opportunity
                WHERE LastModifiedDate >= {window_start.strftime('%Y-%m-%dT%H:%M:%S.000Z')}
                  AND LastModifiedDate <= {window_end.strftime('%Y-%m-%dT%H:%M:%S.000Z')}
                  AND IsClosed = true
                ORDER BY LastModifiedDate ASC
                LIMIT 5
                """
                
                result = sf.query(query)
                if result['records']:
                    opp = result['records'][0]
                    opp_time = datetime.fromisoformat(opp['LastModifiedDate'].replace('Z', '+00:00'))
                    response_hours = (opp_time - exec_time).total_seconds() / 3600
                    
                    if 0 < response_hours < 48:
                        response_times.append(response_hours)
            
            except Exception as e:
                continue
        
        if response_times:
            response_times.sort()
            return {
                'avg_response_hours': sum(response_times) / len(response_times),
                'median_response_hours': response_times[len(response_times) // 2],
                'min_response_hours': min(response_times),
                'max_response_hours': max(response_times),
                'total_with_response': len(response_times),
                'method': 'flow_execution'
            }
    
    except Exception as e:
        print(f"⚠️  Error calculating response time: {e}")
    
    return {
        'avg_response_hours': 0,
        'median_response_hours': 0,
        'min_response_hours': 0,
        'max_response_hours': 0,
        'total_with_response': 0,
        'method': 'none'
    }


# ==========================================================
# CLOSED OUT VALUE CALCULATION
# ==========================================================
def analyze_flow_setup(sf, flow_id: str, alert_field: str, current_status: Dict, gap_analysis: Dict) -> Dict:
    """
    Analyze Past Due Closed Date flow setup and provide optimization recommendations
    """
    analysis = {
        'flow_id': flow_id,
        'efficiency_score': 0,
        'issues': [],
        'recommendations': [],
        'setup_type': 'unknown',
        'optimal': False
    }
    
    alert_count = current_status.get('alert_field_count', 0)
    report_count = current_status.get('report_criteria_count', 0)
    gap = report_count - alert_count
    
    # Calculate efficiency score (0-100)
    if report_count > 0:
        efficiency = (alert_count / report_count) * 100
        analysis['efficiency_score'] = round(efficiency, 1)
    else:
        analysis['efficiency_score'] = 100 if alert_count == 0 else 0
    
    # Identify issues
    if gap > 0:
        analysis['issues'].append({
            'severity': 'high' if gap > 5 else 'medium',
            'issue': f'{gap} opportunities ({round((gap/report_count)*100, 1)}%) are past due but have no alert field',
            'impact': 'Reps are not being notified about these opportunities'
        })
    
    if alert_count == 0 and report_count > 0:
        analysis['issues'].append({
            'severity': 'critical',
            'issue': 'Flow appears to not be triggering at all',
            'impact': 'No alerts are being sent to reps'
        })
    
    # Analyze flow setup type based on patterns
    if gap == 0:
        analysis['setup_type'] = 'optimal'
        analysis['optimal'] = True
        analysis['recommendations'].append({
            'priority': 'info',
            'recommendation': 'Flow is working perfectly - all past due opportunities are being tracked'
        })
    elif gap > 0 and alert_count > 0:
        analysis['setup_type'] = 'partial_coverage'
        analysis['optimal'] = False
    elif alert_count == 0:
        analysis['setup_type'] = 'not_triggering'
        analysis['optimal'] = False
    
    # Provide specific recommendations
    if analysis['setup_type'] == 'partial_coverage':
        analysis['recommendations'].append({
            'priority': 'high',
            'recommendation': 'Flow is missing opportunities - check flow entry criteria',
            'details': [
                'Ensure flow entry criteria matches report criteria exactly',
                'Verify flow entry criteria matches opportunity records',
                'Verify Account Name exclusions are in flow conditions',
                'Consider if flow is scheduled vs record-triggered'
            ]
        })
        
        # Check if opportunities have been past due for a while
        if gap_analysis.get('sample_opportunities'):
            sample_opps = gap_analysis['sample_opportunities']
            days_past_list = []
            for opp in sample_opps:
                if opp.get('CloseDate'):
                    try:
                        cd = datetime.fromisoformat(opp['CloseDate'] + 'T00:00:00')
                        days_past = (datetime.now() - cd).days
                        days_past_list.append(days_past)
                    except:
                        pass
            
            if days_past_list:
                avg_days = sum(days_past_list) / len(days_past_list)
                if avg_days > 30:
                    analysis['recommendations'].append({
                        'priority': 'high',
                        'recommendation': 'Opportunities have been past due for extended periods',
                        'details': [
                            f'Average days past due: {avg_days:.0f} days',
                            'Flow may not be running daily or may be scheduled incorrectly',
                            'Consider using a scheduled flow that runs daily to catch all past due opportunities'
                        ]
                    })
    
    elif analysis['setup_type'] == 'not_triggering':
        analysis['recommendations'].append({
            'priority': 'critical',
            'recommendation': 'Flow is not triggering - immediate action needed',
            'details': [
                'Check if flow is active and published',
                'Verify entry criteria matches opportunity records',
                'Check for flow errors in Setup → Flow Debug Logs',
                'Verify custom field Overdue_Alert_Sent_Date__c exists and is updateable',
                'Consider if flow type (record-triggered vs scheduled) is correct'
            ]
        })
    
    # General recommendations for optimal setup
    analysis['recommendations'].append({
        'priority': 'medium',
        'recommendation': 'Optimal Flow Setup Recommendations',
        'details': [
            'Flow Type: Use Scheduled Flow (runs daily) OR Record-Triggered Flow (runs on update)',
            'Entry Criteria: Match report criteria exactly (CloseDate < Today, Stage IN list, etc.)',
            'Alert Field: Set Overdue_Alert_Sent_Date__c to TODAY() when alert is sent',
            'Clear Logic: Only clear alert field when CloseDate is updated to future date',
            'Field History: Enable Field History Tracking for Overdue_Alert_Sent_Date__c to track cleared alerts'
        ]
    })
    
    return analysis


def analyze_gap_opportunities(sf, alert_field: Optional[str] = None, max_show: int = 10) -> Dict:
    """
    Analyze opportunities matching report criteria that DON'T have the alert field
    This helps identify why there's a gap between report count and alert field count
    """
    if not alert_field:
        return {
            'gap_count': 0,
            'sample_opportunities': [],
            'insights': []
        }
    
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get opportunities matching report criteria WITHOUT alert field
        gap_query = f"""
        SELECT 
            Id,
            Name,
            CloseDate,
            StageName,
            CreatedDate,
            LastModifiedDate,
            Opportunity_Owner__c,
            Account.Name,
            {alert_field}
        FROM Opportunity
        WHERE CloseDate < {today}
          AND IsClosed = false
          AND StageName IN ('Prospecting', 'Discovery', 'Qualification', 'Solution Development', 'Presentation & Negotiation')
          AND Professional_Services_Amount__c != null
          AND Professional_Services_Amount__c > 0
          AND Account.Name NOT LIKE '%Test Account1%'
          AND Account.Name NOT LIKE '%ACME Corporation%'
          AND Account.Name NOT LIKE '%Test Account%'
          AND ({alert_field} = null OR {alert_field} = '')
        ORDER BY CloseDate DESC
        LIMIT {max_show}
        """
        
        gap_result = sf.query_all(gap_query)
        gap_opps = gap_result.get('records', [])
        
        insights = []
        if gap_opps:
            # Analyze patterns
            created_dates = [datetime.fromisoformat(o['CreatedDate'].replace('Z', '+00:00')) for o in gap_opps if o.get('CreatedDate')]
            close_dates = [datetime.fromisoformat(o['CloseDate'] + 'T00:00:00') for o in gap_opps if o.get('CloseDate')]
            
            if created_dates and close_dates:
                avg_days_past_due = sum((datetime.now() - cd).days for cd in close_dates) / len(close_dates)
                insights.append(f"Average days past due: {avg_days_past_due:.0f} days")
            
            # Check if opportunities were created before or after a certain date
            recent_creations = sum(1 for cd in created_dates if (datetime.now() - cd).days < 30)
            insights.append(f"{recent_creations} created in last 30 days")
            
            # Common stages
            stages = [o.get('StageName', 'Unknown') for o in gap_opps]
            from collections import Counter
            stage_counts = Counter(stages)
            most_common_stage = stage_counts.most_common(1)[0] if stage_counts else None
            if most_common_stage:
                insights.append(f"Most common stage: {most_common_stage[0]} ({most_common_stage[1]})")
        
        return {
            'gap_count': len(gap_opps),
            'sample_opportunities': gap_opps[:max_show],
            'insights': insights,
            'total_gap_query': gap_result.get('totalSize', 0)
        }
    
    except Exception as e:
        return {
            'gap_count': 0,
            'sample_opportunities': [],
            'insights': [],
            'error': str(e)
        }


def get_current_past_due_count(sf, alert_field: Optional[str] = None) -> Dict:
    """
    Get current count of Past Due opportunities
    This checks both:
    1. Opportunities with alert field populated (flow-tracked)
    2. Opportunities matching report criteria (Close Date in Past + Open)
    
    The report shows the true state, while the alert field shows what the flow has tracked
    """
    results = {
        'alert_field_count': 0,
        'report_criteria_count': 0,
        'current_count': 0,
        'status': 'unknown',
        'message': 'No alert field configured'
    }
    
    if alert_field:
        try:
            # Count by alert field (what flow has tracked)
            query = f"""
            SELECT COUNT() 
            FROM Opportunity
            WHERE {alert_field} != null
            """
            result = sf.query(query)
            results['alert_field_count'] = result.get('totalSize', 0)
        except Exception as e:
            pass
    
    # Also query by report criteria (Close Date in Past) - EXACT MATCH TO SALESFORCE REPORT
    try:
        # Match report criteria:
        # 1. Close Date < Today
        # 2. Stage IN (Prospecting, Discovery, Qualification, Solution Development, Presentation & Negotiation)
        # 3. Account Name does NOT contain: "Test Account1", "ACME Corporation", "Test Account"
        # 4. Professional Services Amount != null and > 0
        # 5. IsClosed = false
        today = datetime.now().strftime('%Y-%m-%d')
        
        report_query = f"""
        SELECT COUNT() 
        FROM Opportunity
        WHERE CloseDate < {today}
          AND IsClosed = false
          AND StageName IN ('Prospecting', 'Discovery', 'Qualification', 'Solution Development', 'Presentation & Negotiation')
          AND Professional_Services_Amount__c != null
          AND Professional_Services_Amount__c > 0
          AND Account.Name NOT LIKE '%Test Account1%'
          AND Account.Name NOT LIKE '%ACME Corporation%'
          AND Account.Name NOT LIKE '%Test Account%'
        """
        
        print(f"   🔍 Executing report criteria query...")
        print(f"   📋 Query filters:")
        print(f"      - CloseDate < {today}")
        print(f"      - IsClosed = false")
        print(f"      - Stage IN (Prospecting, Discovery, Qualification, Solution Development, Presentation & Negotiation)")
        print(f"      - Professional_Services_Amount__c > 0")
        print(f"      - Account.Name excludes: Test Account1, ACME Corporation, Test Account")
        
        report_result = sf.query(report_query)
        results['report_criteria_count'] = report_result.get('totalSize', 0)
        
        print(f"   ✅ Report criteria count: {results['report_criteria_count']}")
        
        # Validation: If count is 1 or very different from expected 10, query sample opportunities
        if results['report_criteria_count'] != 10:
            print(f"   ⚠️  Count mismatch! Expected ~10 (from Salesforce report), got {results['report_criteria_count']}")
            print(f"   🔍 Querying sample opportunities to validate criteria...")
            
            sample_query = f"""
            SELECT Id, Name, CloseDate, StageName, Account.Name, Professional_Services_Amount__c
            FROM Opportunity
            WHERE CloseDate < {today}
              AND IsClosed = false
              AND StageName IN ('Prospecting', 'Discovery', 'Qualification', 'Solution Development', 'Presentation & Negotiation')
              AND Professional_Services_Amount__c != null
              AND Professional_Services_Amount__c > 0
              AND Account.Name NOT LIKE '%Test Account1%'
              AND Account.Name NOT LIKE '%ACME Corporation%'
              AND Account.Name NOT LIKE '%Test Account%'
            ORDER BY CloseDate DESC
            LIMIT 15
            """
            
            try:
                sample_result = sf.query_all(sample_query)
                sample_opps = sample_result.get('records', [])
                print(f"   📊 Sample opportunities matching criteria ({len(sample_opps)} shown):")
                for i, opp in enumerate(sample_opps[:10], 1):
                    name = opp.get('Name', 'Unknown')[:40]
                    stage = opp.get('StageName', 'N/A')
                    close_date = opp.get('CloseDate', 'N/A')
                    account = opp.get('Account', {}).get('Name', 'N/A')[:30] if opp.get('Account') else 'N/A'
                    print(f"      {i}. {name} | {stage} | Close: {close_date} | Account: {account}")
                
                if len(sample_opps) < 10:
                    print(f"   💡 Only {len(sample_opps)} opportunities found.")
            except Exception as sample_error:
                print(f"   ⚠️  Could not query sample opportunities: {sample_error}")
        
        # Use report criteria count as PRIMARY (it matches the Salesforce report exactly)
        # This is the TRUE state
        results['current_count'] = results['report_criteria_count']
        
        # Show breakdown if there's a discrepancy
        if results['report_criteria_count'] != results['alert_field_count']:
            gap = abs(results['report_criteria_count'] - results['alert_field_count'])
            if results['report_criteria_count'] > results['alert_field_count']:
                results['message'] = f"{results['report_criteria_count']} opportunities past due (report criteria - EXACT MATCH) vs {results['alert_field_count']} with alert field (gap: {gap})"
            else:
                results['message'] = f"{results['report_criteria_count']} opportunities past due (report criteria) - Alert field shows {results['alert_field_count']} (may include cleared fields)"
        else:
            results['message'] = f"{results['report_criteria_count']} opportunities past due (matches alert field)"
        
        status = 'compliant' if results['current_count'] == 0 else 'action_needed'
        results['status'] = status
        
        if results['current_count'] == 0:
            results['message'] = 'All caught up! ✅'
        
    except Exception as e:
        # Fallback to alert field count only
        results['current_count'] = results['alert_field_count']
        results['status'] = 'compliant' if results['current_count'] == 0 else 'action_needed'
        results['message'] = f'Could not query report criteria: {str(e)}'
    
    return results


def calculate_compliance_over_time(sf, alert_field: Optional[str] = None, days_back: int = 30, max_count: int = 3, use_report_criteria: bool = False) -> Dict:
    """
    Calculate how often the Past Due count stays at max_count or less over time
    
    If use_report_criteria=True, uses report criteria (Close Date in Past + Open)
    instead of just the alert field. This is more accurate since the flow may
    clear the alert field when opportunities are brought current.
    
    Uses Field History to reconstruct the count at different points in time
    """
    if not alert_field:
        return {
            'compliance_percentage': 0,
            'days_compliant': 0,
            'total_days': days_back,
            'method': 'not_available'
        }
    
    try:
        # If using report criteria, query opportunities directly and track by CloseDate
        if use_report_criteria:
            # Query opportunities matching report criteria over time
            today = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            # Get all opportunities that would be "past due" at any point in the period
            opp_query = f"""
            SELECT 
                Id,
                CloseDate,
                IsClosed,
                StageName,
                CreatedDate,
                LastModifiedDate
            FROM Opportunity
            WHERE CloseDate >= {start_date}
              AND CloseDate < {today}
              AND IsClosed = false
              AND StageName IN ('Prospecting', 'Discovery', 'Qualification', 'Solution Development', 'Presentation & Negotiation')
              AND Professional_Services_Amount__c != null
              AND Professional_Services_Amount__c > 0
              AND Account.Name NOT LIKE '%Test Account1%'
              AND Account.Name NOT LIKE '%ACME Corporation%'
              AND Account.Name NOT LIKE '%Test Account%'
            ORDER BY CloseDate ASC
            """
            
            opp_result = sf.query_all(opp_query)
            
            if opp_result.get('records'):
                # Build daily timeline based on CloseDate
                from collections import defaultdict
                daily_counts = []
                current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)
                end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Group opportunities by close date
                opps_by_date = defaultdict(list)
                for opp in opp_result['records']:
                    if opp.get('CloseDate'):
                        try:
                            close_date = datetime.fromisoformat(opp['CloseDate'] + 'T00:00:00')
                            close_date_only = close_date.replace(hour=0, minute=0, second=0, microsecond=0)
                            opps_by_date[close_date_only].append(opp)
                        except:
                            continue
                
                # Build daily count timeline
                # For each day, count opportunities where CloseDate <= that day and still open
                daily_counts = []
                while current_date <= end_date:
                    count = 0
                    # Count all opportunities that passed their close date by this day
                    for opp in opp_result['records']:
                        if not opp.get('CloseDate'):
                            continue
                        try:
                            opp_close_date = datetime.fromisoformat(opp['CloseDate'] + 'T00:00:00')
                            opp_close_date_only = opp_close_date.replace(hour=0, minute=0, second=0, microsecond=0)
                            
                            # If close date has passed by current_date and opp is still open
                            if opp_close_date_only <= current_date and not opp.get('IsClosed', False):
                                count += 1
                        except:
                            continue
                    
                    daily_counts.append((current_date, count))
                    current_date += timedelta(days=1)
                
                if daily_counts:
                    # Calculate compliance
                    days_compliant = sum(1 for _, count in daily_counts if count <= max_count)
                    compliance_percentage = (days_compliant / len(daily_counts) * 100) if daily_counts else 0
                    
                    # Get min/max/avg counts
                    all_counts = [count for _, count in daily_counts]
                    min_count = min(all_counts) if all_counts else 0
                    max_count_actual = max(all_counts) if all_counts else 0
                    avg_count = sum(all_counts) / len(all_counts) if all_counts else 0
                    
                    current_count = all_counts[-1] if all_counts else 0
                    
                    return {
                        'compliance_percentage': round(compliance_percentage, 1),
                        'days_compliant': days_compliant,
                        'total_days': len(daily_counts),
                        'method': 'report_criteria',
                        'min_count': min_count,
                        'max_count': max_count_actual,
                        'avg_count': round(avg_count, 1),
                        'current_count': current_count,
                        'note': 'Based on report criteria (Close Date in Past + Open). Calculated daily based on CloseDate.'
                    }
                else:
                    # No opportunities in period
                    return {
                        'compliance_percentage': 100.0,
                        'days_compliant': days_back,
                        'total_days': days_back,
                        'method': 'report_criteria',
                        'current_count': 0,
                        'note': 'No opportunities matching report criteria in period'
                    }
        
        # Query Field History for this field to see when it was set/cleared
        history_query = f"""
        SELECT 
            OpportunityId,
            OldValue,
            NewValue,
            CreatedDate
        FROM OpportunityFieldHistory
        WHERE Field = '{alert_field}'
          AND CreatedDate >= LAST_N_DAYS:{days_back}
        ORDER BY CreatedDate ASC
        """
        
        history_result = sf.query_all(history_query)
        
        if not history_result.get('records'):
            # No Field History - try to estimate from current opportunities
            query = f"""
            SELECT COUNT(), {alert_field}
            FROM Opportunity
            WHERE {alert_field} != null
            GROUP BY {alert_field}
            """
            try:
                result = sf.query_all(query)
                # Simple approximation: assume current count for all days
                current_count_query = f"SELECT COUNT() FROM Opportunity WHERE {alert_field} != null"
                current_result = sf.query(current_count_query)
                current_count = current_result.get('totalSize', 0)
                
                days_compliant = days_back if current_count <= max_count else 0
                compliance_percentage = 100.0 if current_count <= max_count else 0.0
                
                return {
                    'compliance_percentage': compliance_percentage,
                    'days_compliant': days_compliant,
                    'total_days': days_back,
                    'method': 'estimated_current_only',
                    'note': 'Field History not available - using current count as estimate'
                }
            except:
                return {
                    'compliance_percentage': 0,
                    'days_compliant': 0,
                    'total_days': days_back,
                    'method': 'not_available'
                }
        
        # Build timeline from Field History
        from collections import defaultdict
        from datetime import datetime, timedelta
        
        # Track count changes over time
        changes = []  # List of (datetime, change: +1 or -1)
        
        for record in history_result['records']:
            change_date = datetime.fromisoformat(record['CreatedDate'].replace('Z', '+00:00'))
            old_val = record.get('OldValue')
            new_val = record.get('NewValue')
            
            # Field was set (went from null to a date)
            if (old_val is None or old_val == '') and (new_val is not None and new_val != ''):
                changes.append((change_date, +1))
            # Field was cleared (went from a date to null)
            elif (old_val is not None and old_val != '') and (new_val is None or new_val == ''):
                changes.append((change_date, -1))
        
        # Also get current count
        current_count_query = f"SELECT COUNT() FROM Opportunity WHERE {alert_field} != null"
        current_result = sf.query(current_count_query)
        current_count = current_result.get('totalSize', 0)
        
        # Build daily timeline
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate count at start (current count minus all additions in period)
        period_additions = sum(1 for _, change in changes if change > 0)
        period_subtractions = sum(1 for _, change in changes if change < 0)
        start_count = current_count - period_additions + period_subtractions
        
        # Simulate day by day
        daily_counts = []
        current_date = start_date
        count = start_count
        
        changes_by_date = defaultdict(int)
        for change_date, change in changes:
            change_date_only = change_date.replace(hour=0, minute=0, second=0, microsecond=0)
            changes_by_date[change_date_only] += change
        
        while current_date <= end_date:
            # Apply changes for this date
            if current_date in changes_by_date:
                count += changes_by_date[current_date]
            
            daily_counts.append((current_date, count))
            current_date += timedelta(days=1)
        
        # Calculate compliance
        days_compliant = sum(1 for _, count in daily_counts if count <= max_count)
        compliance_percentage = (days_compliant / len(daily_counts) * 100) if daily_counts else 0
        
        # Get min/max counts for reporting
        all_counts = [count for _, count in daily_counts]
        min_count = min(all_counts) if all_counts else 0
        max_count_actual = max(all_counts) if all_counts else 0
        avg_count = sum(all_counts) / len(all_counts) if all_counts else 0
        
        return {
            'compliance_percentage': compliance_percentage,
            'days_compliant': days_compliant,
            'total_days': len(daily_counts),
            'method': 'field_history',
            'min_count': min_count,
            'max_count': max_count_actual,
            'avg_count': round(avg_count, 1),
            'current_count': current_count
        }
    
    except Exception as e:
        error_str = str(e)
        # Check for specific Salesforce errors
        if 'INVALID_FIELD' in error_str or 'No such column' in error_str or 'INVALID_TYPE' in error_str:
            # Field History object not available or field not tracked
            return {
                'compliance_percentage': 0,
                'days_compliant': 0,
                'total_days': days_back,
                'method': 'field_history_not_enabled',
                'note': 'Field History Tracking not enabled for this field',
                'error': error_str
            }
        elif 'sObject type' in error_str and 'not supported' in error_str:
            # OpportunityFieldHistory not accessible
            return {
                'compliance_percentage': 0,
                'days_compliant': 0,
                'total_days': days_back,
                'method': 'field_history_not_available',
                'note': 'Field History objects not accessible via API',
                'error': error_str
            }
        else:
            # Other error - return with details
            return {
                'compliance_percentage': 0,
                'days_compliant': 0,
                'total_days': days_back,
                'method': 'error',
                'error': str(e),
                'note': f'Error querying Field History: {str(e)}'
            }


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================
def get_salesforce_instance_url() -> str:
    """Extract Salesforce instance URL from Flow URL or use default"""
    try:
        # Try to extract from FLOW_URL_1
        parsed = urlparse(FLOW_URL_1)
        if parsed.netloc:
            # Extract instance from netloc (e.g., 'innovativesolutions.lightning.force.com')
            return f"https://{parsed.netloc}"
    except:
        pass
    
    # Fallback to default
    return f"https://{SALESFORCE_INSTANCE}"


def get_opportunity_url(opp_id: str) -> str:
    """Generate Salesforce Lightning URL for an opportunity"""
    instance_url = get_salesforce_instance_url()
    return f"{instance_url}/lightning/r/Opportunity/{opp_id}/view"


# ==========================================================
# CLOSED OUT VALUE CALCULATION
# ==========================================================
def calculate_closed_value(sf, flow_executions: List[Dict], flow_id: str, alert_field: Optional[str] = None) -> Dict:
    """
    Calculate closed out value metrics
    
    Closed out value = Total value of Opportunities that were closed
    after being associated with Flow executions/alerts
    
    If alert_field is provided, we can directly query Opportunities with that field
    and filter for closed opportunities, which is more accurate.
    """
    try:
        # Method 1: Use custom alert field if available (more accurate)
        if alert_field:
            try:
                # Query Opportunities with alert field populated that are closed
                query = f"""
                SELECT 
                    Id, 
                    Name,
                    Account.Name,
                    Amount, 
                    IsWon, 
                    CloseDate, 
                    StageName,
                    {alert_field}
                FROM Opportunity
                WHERE {alert_field} != null
                  AND IsClosed = true
                  AND Amount != null
                  AND CloseDate >= LAST_N_DAYS:{DEFAULT_DAYS_BACK}
                ORDER BY CloseDate DESC
                """
                
                result = sf.query_all(query)
                
                total_value = 0
                won_value = 0
                lost_value = 0
                closed_count = 0
                won_count = 0
                
                for opp in result['records']:
                    alert_date_str = opp.get(alert_field)
                    close_date_str = opp.get('CloseDate')
                    
                    if not alert_date_str or not close_date_str:
                        continue
                    
                    # Ensure close date is after alert date (opportunity closed after alert was sent)
                    try:
                        # Handle different date formats using helper function
                        alert_date = parse_salesforce_datetime(alert_date_str)
                        if not alert_date:
                            continue
                        
                        close_date = datetime.fromisoformat(close_date_str + 'T00:00:00')
                        
                        if close_date >= alert_date:  # Closed after alert
                            amount = float(opp.get('Amount', 0))
                            total_value += amount
                            closed_count += 1
                            if opp.get('IsWon'):
                                won_count += 1
                                won_value += amount
                            else:
                                lost_value += amount
                    except:
                        continue
                
                if closed_count > 0:
                    avg_value = total_value / closed_count
                    win_rate = (won_count / closed_count * 100) if closed_count > 0 else 0
                    
                    # Get full opportunity details for display (with Name, Account, etc.)
                    closed_opps = []
                    for opp in result['records']:
                        alert_date_str = opp.get(alert_field)
                        close_date_str = opp.get('CloseDate')
                        
                        if not alert_date_str or not close_date_str:
                            continue
                        
                        try:
                            alert_date = parse_salesforce_datetime(alert_date_str)
                            if not alert_date:
                                continue
                            
                            close_date = datetime.fromisoformat(close_date_str + 'T00:00:00')
                            
                            if close_date >= alert_date:  # Closed after alert
                                closed_opps.append(opp)
                        except:
                            continue
                    
                    return {
                        'total_closed_value': total_value,
                        'won_value': won_value,
                        'lost_value': lost_value,
                        'avg_closed_value': avg_value,
                        'closed_count': closed_count,
                        'won_count': won_count,
                        'win_rate': win_rate,
                        'method': 'custom_field',
                        'closed_opportunities': closed_opps  # Full opportunity records
                    }
            
            except Exception as e:
                print(f"⚠️  Could not use custom field method: {e}")
                print("   Falling back to Flow execution method...")
        
        # Method 2: Fallback to Flow execution time correlation
        if not flow_executions:
            return {
                'total_closed_value': 0,
                'avg_closed_value': 0,
                'closed_count': 0,
                'won_count': 0,
                'win_rate': 0,
                'method': 'none'
            }
        
        # Get execution time windows
        execution_windows = []
        for execution in flow_executions[:100]:  # Limit for performance
            exec_time = datetime.fromisoformat(execution['CreatedDate'].replace('Z', '+00:00'))
            window_start = exec_time
            window_end = exec_time + timedelta(days=30)  # 30-day window
            
            execution_windows.append({
                'start': window_start,
                'end': window_end
            })
        
        if not execution_windows:
            return {
                'total_closed_value': 0,
                'avg_closed_value': 0,
                'closed_count': 0,
                'won_count': 0,
                'win_rate': 0,
                'method': 'none'
            }
        
        # Query for closed Opportunities in the time windows
        total_value = 0
        won_value = 0
        lost_value = 0
        closed_count = 0
        won_count = 0
        
        # Aggregate windows into a single query for efficiency
        earliest_start = min(w['start'] for w in execution_windows)
        latest_end = max(w['end'] for w in execution_windows)
        
        query = f"""
        SELECT Id, Amount, IsWon, CloseDate, StageName
        FROM Opportunity
        WHERE CloseDate >= {earliest_start.strftime('%Y-%m-%d')}
          AND CloseDate <= {latest_end.strftime('%Y-%m-%d')}
          AND IsClosed = true
          AND Amount != null
        ORDER BY CloseDate DESC
        """
        
        result = sf.query_all(query)
        
        # Filter opportunities that fall within execution windows
        for opp in result['records']:
            close_date = datetime.fromisoformat(opp['CloseDate'] + 'T00:00:00')
            
            # Check if close date is within any execution window
            in_window = False
            for window in execution_windows:
                if window['start'] <= close_date <= window['end']:
                    in_window = True
                    break
            
            if in_window and opp.get('Amount'):
                amount = float(opp['Amount'])
                total_value += amount
                closed_count += 1
                if opp.get('IsWon'):
                    won_count += 1
                    won_value += amount
                else:
                    lost_value += amount
        
        avg_value = total_value / closed_count if closed_count > 0 else 0
        win_rate = (won_count / closed_count * 100) if closed_count > 0 else 0
        
        return {
            'total_closed_value': total_value,
            'won_value': won_value,
            'lost_value': lost_value,
            'avg_closed_value': avg_value,
            'closed_count': closed_count,
            'won_count': won_count,
            'win_rate': win_rate,
            'method': 'flow_execution'
        }
    
    except Exception as e:
        print(f"⚠️  Error calculating closed value: {e}")
        return {
            'total_closed_value': 0,
            'won_value': 0,
            'lost_value': 0,
            'avg_closed_value': 0,
            'closed_count': 0,
            'won_count': 0,
            'win_rate': 0,
            'method': 'none'
        }


# ==========================================================
# METRICS AGGREGATION
# ==========================================================
def calculate_flow_metrics(sf, flow_id: str, flow_name: str, days_back: int = DEFAULT_DAYS_BACK, alert_field: Optional[str] = None) -> Dict:
    """Calculate all metrics for a Flow"""
    
    print(f"\n{'='*70}")
    print(f"📊 Analyzing Flow: {flow_name}")
    print(f"{'='*70}\n")
    
    # Determine which alert field to use based on flow name
    if not alert_field:
        if 'Ghost' in flow_name or flow_id == '301PQ00000iX6QRYA0':
            alert_field = GHOST_PIPELINE_ALERT_FIELD
        elif 'Past Due' in flow_name or flow_id == '301PQ00000iMEFuYAO':
            alert_field = PAST_DUE_ALERT_FIELD
    
    # Get Flow executions
    executions = get_flow_executions(sf, flow_id, days_back)
    
    # If we have custom alert field, use it for more accurate tracking
    alerts_from_field = 0
    if alert_field:
        try:
            # First, try current field values
            query = f"""
            SELECT COUNT() 
            FROM Opportunity
            WHERE {alert_field} != null
              AND {alert_field} >= LAST_N_DAYS:{days_back}
            """
            result = sf.query(query)
            alerts_from_field = result.get('totalSize', 0)
            
            if alerts_from_field > 0:
                print(f"✅ Found {alerts_from_field} alerts tracked via {alert_field} field")
            else:
                # Field might be cleared - try Field History Tracking instead
                print(f"ℹ️  No current values in {alert_field} field (may be cleared by flow)")
                print(f"   Checking Field History to track alerts even when field is cleared...")
                
                try:
                    # Query OpportunityFieldHistory to find when alerts were sent
                    # This captures alerts even if the field was later cleared
                    history_query = f"""
                    SELECT COUNT()
                    FROM OpportunityFieldHistory
                    WHERE Field = '{alert_field}'
                      AND NewValue != null
                      AND CreatedDate >= LAST_N_DAYS:{days_back}
                    """
                    history_result = sf.query(history_query)
                    alerts_from_history = history_result.get('totalSize', 0)
                    
                    if alerts_from_history > 0:
                        alerts_from_field = alerts_from_history
                        print(f"✅ Found {alerts_from_field} alerts via Field History (includes cleared fields)")
                        print(f"   Note: Field History shows alerts even when field is later cleared")
                    else:
                        # Check if Field History Tracking is enabled
                        print(f"⚠️  No Field History found for {alert_field}")
                        print(f"   This may indicate:")
                        print(f"   - Field History Tracking not enabled for this field")
                        print(f"   - Flow hasn't run recently")
                        print(f"   - Field name may be incorrect")
                        print(f"\n   💡 To enable Field History:")
                        print(f"      1. Setup → Object Manager → Opportunity → Fields & Relationships")
                        print(f"      2. Find '{alert_field}' and enable 'Track Field History'")
                        print(f"      3. Re-run this script after the next flow execution")
                        
                except Exception as history_error:
                    error_str = str(history_error)
                    if 'INVALID_FIELD' in error_str or 'No such column' in error_str:
                        print(f"⚠️  Field History Tracking not enabled for {alert_field}")
                        print(f"   Field History must be enabled to track cleared fields")
                        print(f"   See Setup → Object Manager → Opportunity → Field History")
                    else:
                        print(f"⚠️  Could not query Field History: {history_error}")
                        
        except Exception as e:
            error_str = str(e)
            if 'INVALID_FIELD' in error_str or 'No such column' in error_str:
                print(f"⚠️  Field '{alert_field}' doesn't exist on Opportunity")
                print(f"   💡 Verify the field API name in Salesforce Setup")
            else:
                print(f"⚠️  Could not count alerts from custom field: {e}")
    
    if not executions and alerts_from_field == 0:
        return {
            'flow_id': flow_id,
            'flow_name': flow_name,
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'alerts_sent': 0,
            'response_time': {},
            'closed_value': {},
            'analysis_period_days': days_back,
            'error': 'No executions found and no custom field data available'
        }
    
    # Basic execution stats from FlowInterview
    successful = sum(1 for e in executions if e.get('InterviewStatus') == 'Finished') if executions else 0
    failed = sum(1 for e in executions if e.get('InterviewStatus') == 'Failed') if executions else 0
    
    # Use custom field count if available and higher, otherwise use FlowInterview count
    total_alerts = max(alerts_from_field, successful) if alerts_from_field > 0 else successful
    
    # Calculate response time
    print("⏱️  Calculating response times...")
    response_metrics = calculate_response_time(sf, executions, flow_id, alert_field)
    
    # Calculate closed value
    print("💰 Calculating closed out values...")
    closed_value_metrics = calculate_closed_value(sf, executions, flow_id, alert_field)
    
    # Get current past due count (for Past Due flow)
    current_status = None
    compliance_metrics = None
    gap_analysis = None
    flow_setup_analysis = None
    if alert_field == PAST_DUE_ALERT_FIELD:
        print("📊 Checking current Past Due status...")
        current_status = get_current_past_due_count(sf, alert_field)
        
        count = current_status['current_count']
        alert_count = current_status.get('alert_field_count', 0)
        report_count = current_status.get('report_criteria_count', 0)
        
        # Always analyze gap opportunities (even if gap is 0)
        gap_analysis = analyze_gap_opportunities(sf, alert_field, max_show=5) if report_count > 0 else {'sample_opportunities': [], 'insights': []}
        
        # Always run flow setup analysis for Past Due flow
        flow_setup_analysis = analyze_flow_setup(sf, flow_id, alert_field, current_status, gap_analysis)
        
        if count == 0:
            print(f"   ✅ Current count: 0 (All caught up!)")
        else:
            print(f"   ⚠️  Current count: {count} opportunities past due")
            
            # Show breakdown if there's a discrepancy
            if report_count > alert_count:
                gap = report_count - alert_count
                print(f"   📊 Breakdown:")
                print(f"      - Report criteria (Close Date in Past): {report_count}")
                print(f"      - With alert field populated: {alert_count}")
                print(f"      - Gap: {gap} opportunities")
                print(f"\n   🔍 Analyzing gap opportunities...")
                
                if gap_analysis.get('sample_opportunities'):
                    print(f"   📋 Sample opportunities without alert field ({len(gap_analysis['sample_opportunities'])} shown):")
                    for i, opp in enumerate(gap_analysis['sample_opportunities'][:5], 1):
                        opp_name = opp.get('Name', 'Unknown')[:40]
                        close_date = opp.get('CloseDate', 'N/A')
                        stage = opp.get('StageName', 'N/A')
                        days_past = ''
                        if close_date:
                            try:
                                cd = datetime.fromisoformat(close_date + 'T00:00:00')
                                days_past = f"({(datetime.now() - cd).days} days past due)"
                            except:
                                pass
                        print(f"      {i}. {opp_name} - {stage} - Close: {close_date} {days_past}")
                    
                    if gap_analysis.get('insights'):
                        print(f"\n   💡 Insights:")
                        for insight in gap_analysis['insights']:
                            print(f"      - {insight}")
                    
                    print(f"\n   💡 Possible reasons for gap:")
                    print(f"      1. Flow may only trigger when CloseDate PASSES (scheduled)")
                    print(f"      2. Flow conditions may exclude some opportunities")
                    print(f"      3. Flow cleared the field when opportunities were updated")
                    print(f"      4. Flow hasn't run yet for opportunities that became past due")
                    print(f"\n   🎯 Recommendation:")
                    print(f"      The report count ({report_count}) is the TRUE state")
                    print(f"      Use this for compliance tracking instead of alert field")
                elif gap_analysis.get('error'):
                    print(f"   ⚠️  Could not analyze gap: {gap_analysis['error']}")
        
        # Print flow setup analysis (always show for Past Due flow)
        print(f"\n{'='*70}")
        print(f"🔧 FLOW SETUP ANALYSIS")
        print(f"{'='*70}")
        print(f"📊 Efficiency Score: {flow_setup_analysis['efficiency_score']}%")
        print(f"   ({alert_count} alerts sent / {report_count} opportunities past due)")
        print(f"📋 Setup Type: {flow_setup_analysis['setup_type'].replace('_', ' ').title()}")
        print(f"✅ Optimal Setup: {'Yes' if flow_setup_analysis['optimal'] else 'No'}")
        
        if flow_setup_analysis['issues']:
            print(f"\n⚠️  Issues Identified:")
            for i, issue in enumerate(flow_setup_analysis['issues'], 1):
                severity_icon = '🔴' if issue['severity'] == 'critical' else '🟠' if issue['severity'] == 'high' else '🟡'
                print(f"   {i}. {severity_icon} {issue['issue']}")
                print(f"      Impact: {issue['impact']}")
        
        if flow_setup_analysis['recommendations']:
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(flow_setup_analysis['recommendations'], 1):
                priority_icon = '🔴' if rec['priority'] == 'critical' else '🟠' if rec['priority'] == 'high' else '🟡' if rec['priority'] == 'medium' else 'ℹ️'
                print(f"   {i}. {priority_icon} {rec['recommendation']}")
                if rec.get('details'):
                    for detail in rec['details']:
                        print(f"      • {detail}")
        
        # Calculate compliance over time (how often count is <= 3)
        # Use report criteria instead of alert field for more accurate count
        print("📈 Calculating compliance over time (count <= 3)...")
        print("   Using report criteria (Close Date in Past + Open) for accurate count")
        try:
            # Try Field History first, but if not available, use report criteria directly
            compliance_metrics = calculate_compliance_over_time(sf, alert_field, days_back=30, max_count=3, use_report_criteria=True)
            method = compliance_metrics.get('method', 'unknown')
            
            if method in ['field_history', 'report_criteria']:
                print(f"   ✅ Compliance: {compliance_metrics['compliance_percentage']:.1f}% ({compliance_metrics['days_compliant']}/{compliance_metrics['total_days']} days)")
                if compliance_metrics.get('min_count') is not None:
                    print(f"   📊 Min: {compliance_metrics['min_count']}, Max: {compliance_metrics['max_count']}, Avg: {compliance_metrics['avg_count']}")
                if compliance_metrics.get('note'):
                    print(f"   ℹ️  {compliance_metrics['note']}")
            elif method == 'field_history_not_enabled':
                # Field History not enabled - show current status only
                current_count = current_status.get('current_count', 0) if current_status else 0
                is_currently_compliant = current_count <= 3
                print(f"   ⚠️  Field History not enabled for {alert_field}")
                print(f"   💡 To enable: Setup → Object Manager → Opportunity → Fields")
                print(f"      Find '{alert_field}' → Enable 'Track Field History'")
                print(f"\n   ℹ️  Current Compliance Check:")
                if is_currently_compliant:
                    print(f"      ✅ Current count ({current_count}) is ≤ 3 - Compliant NOW")
                else:
                    print(f"      ⚠️  Current count ({current_count}) is > 3 - Not compliant NOW")
                print(f"      📝 Historical compliance tracking requires Field History")
            elif method == 'estimated_current_only':
                compliance_pct = compliance_metrics.get('compliance_percentage', 0)
                days_comp = compliance_metrics.get('days_compliant', 0)
                print(f"   ℹ️  Field History not available - using current count estimate")
                print(f"   ℹ️  Estimated compliance: {compliance_pct:.1f}% ({days_comp}/{compliance_metrics.get('total_days', 30)} days)")
                print(f"   📝 Note: This assumes count has been constant (Field History needed for accuracy)")
            elif method == 'not_available':
                print(f"   ⚠️  Cannot calculate compliance: {compliance_metrics.get('note', 'Unknown reason')}")
            elif method == 'field_history_not_available':
                # Show current status as fallback
                current_count = current_status.get('current_count', 0) if current_status else 0
                is_currently_compliant = current_count <= 3
                print(f"   ⚠️  Field History objects not accessible via API")
                print(f"   💡 Field History may not be enabled at the org level")
                print(f"   💡 Try: Setup → Object Manager → Opportunity → Field History")
                print(f"      Enable 'Track Field History' at the object level")
                print(f"\n   ℹ️  Current Compliance Check:")
                if is_currently_compliant:
                    print(f"      ✅ Current count ({current_count}) is ≤ 3 - Compliant NOW")
                else:
                    print(f"      ⚠️  Current count ({current_count}) is > 3 - Not compliant NOW")
            elif method == 'error':
                error_msg = compliance_metrics.get('error', 'Unknown error')
                print(f"   ❌ Error calculating compliance: {error_msg}")
                print(f"   💡 This may indicate Field History is not enabled for {alert_field}")
                if compliance_metrics.get('note'):
                    print(f"   📝 {compliance_metrics['note']}")
                # Show current status as fallback
                current_count = current_status.get('current_count', 0) if current_status else 0
                if current_count <= 3:
                    print(f"\n   ℹ️  Current count ({current_count}) is ≤ 3 - Compliant NOW")
            else:
                print(f"   ⚠️  Could not calculate compliance metrics (method: {method})")
                if compliance_metrics.get('note'):
                    print(f"   Note: {compliance_metrics['note']}")
        except Exception as e:
            print(f"   ❌ Error in compliance calculation: {e}")
            compliance_metrics = {'method': 'error', 'error': str(e)}
            # Show current status as fallback
            current_count = current_status.get('current_count', 0) if current_status else 0
            if current_count <= 3:
                print(f"\n   ℹ️  Current count ({current_count}) is ≤ 3 - Compliant NOW")
    
    # Calculate success rate safely
    total_execs = len(executions) if executions else 0
    if total_execs > 0:
        success_rate = (successful / total_execs * 100)
    else:
        success_rate = 0.0
    
    # Summary
    metrics = {
        'flow_id': flow_id,
        'flow_name': flow_name,
        'total_executions': total_execs,
        'successful_executions': successful,
        'failed_executions': failed,
        'success_rate': success_rate,
        'alerts_sent': total_alerts,  # Use custom field count if available, otherwise FlowInterview
        'alerts_from_field': alerts_from_field,
        'response_time': response_metrics,
        'closed_value': closed_value_metrics,
        'analysis_period_days': days_back,
        'first_execution': executions[-1]['CreatedDate'] if executions else None,
        'last_execution': executions[0]['CreatedDate'] if executions else None,
        'execution_method': 'custom_field' if alerts_from_field > 0 and not executions else ('flow_interview' if executions else 'none'),
        'current_status': current_status,  # For Past Due flow - shows current count
        'compliance_metrics': compliance_metrics,  # For Past Due flow - shows compliance over time
        'gap_analysis': gap_analysis,  # For Past Due flow - analysis of gap opportunities
        'flow_setup_analysis': flow_setup_analysis  # For Past Due flow - setup optimization recommendations
    }
    
    return metrics


# ==========================================================
# REPORTING
# ==========================================================
def print_metrics_report(metrics: Dict):
    """Print formatted metrics report"""
    
    print(f"\n{'='*70}")
    print(f"📈 METRICS REPORT: {metrics.get('flow_name', 'Unknown Flow')}")
    print(f"{'='*70}\n")
    
    print(f"🔍 Flow ID: {metrics.get('flow_id', 'N/A')}")
    print(f"📅 Analysis Period: Last {metrics.get('analysis_period_days', DEFAULT_DAYS_BACK)} days")
    if metrics.get('first_execution'):
        print(f"📆 First Execution: {metrics['first_execution']}")
        print(f"📆 Last Execution: {metrics['last_execution']}")
    print()
    
    # Execution Stats - Only show detailed stats if we have FlowInterview data
    execution_method = metrics.get('execution_method', 'none')
    total_executions = metrics.get('total_executions', 0)
    alerts_sent = metrics.get('alerts_sent', 0)
    
    print("📊 EXECUTION STATISTICS")
    
    # If we have FlowInterview execution data, show full stats
    if execution_method == 'flow_interview' and total_executions > 0:
        print(f"   Total Executions: {total_executions}")
        success_rate = metrics.get('success_rate', 0)
        if success_rate > 0:
            print(f"   ✅ Successful: {metrics.get('successful_executions', 0)} ({success_rate:.1f}%)")
        else:
            print(f"   ✅ Successful: {metrics.get('successful_executions', 0)}")
        print(f"   ❌ Failed: {metrics.get('failed_executions', 0)}")
        print(f"   📤 Alerts Sent: {alerts_sent}")
    else:
        # When using custom field tracking, just show alerts sent
        print(f"   📤 Alerts Sent: {alerts_sent}")
    
    print()
    
    # Response Time
    rt = metrics.get('response_time', {})
    if rt.get('total_with_response', 0) > 0:
        print("⏱️  RESPONSE TIME METRICS")
        print(f"   Average Response: {rt['avg_response_hours']:.2f} hours ({rt['avg_response_hours']/24:.1f} days)")
        print(f"   Median Response: {rt['median_response_hours']:.2f} hours ({rt['median_response_hours']/24:.1f} days)")
        print(f"   Min Response: {rt['min_response_hours']:.2f} hours")
        print(f"   Max Response: {rt['max_response_hours']:.2f} hours")
        print(f"   Responses Tracked: {rt['total_with_response']}")
    else:
        print("⏱️  RESPONSE TIME METRICS")
        print("   ⚠️  No response time data available")
        print("   (May need custom logging in Flow to track response times)")
    print()
    
    # Current Status (for Past Due flow)
    current_status = metrics.get('current_status')
    compliance_metrics = metrics.get('compliance_metrics')
    
    if current_status and current_status.get('current_count') is not None:
        print("📊 CURRENT STATUS")
        count = current_status['current_count']
        status = current_status['status']
        alert_count = current_status.get('alert_field_count', 0)
        report_count = current_status.get('report_criteria_count', 0)
        
        if status == 'compliant':
            print(f"   ✅ Current Past Due Count: {count}")
            print(f"   🎯 Status: All caught up! (Goal achieved)")
        else:
            print(f"   ⚠️  Current Past Due Count: {count}")
            print(f"   📌 Status: Action needed")
            
            # Show breakdown if there's a discrepancy
            if report_count > alert_count:
                print(f"\n   📊 Detailed Breakdown:")
                print(f"      - Opportunities matching report criteria: {report_count}")
                print(f"      - Opportunities with alert field populated: {alert_count}")
                print(f"      - Gap: {report_count - alert_count} opportunities")
                print(f"   💡 The report shows ALL past due opportunities")
                print(f"      The alert field shows only those the flow has tracked")
        
        # Show compliance metrics if available
        if compliance_metrics and compliance_metrics.get('method') in ['field_history', 'report_criteria', 'estimated_current_only']:
            compliance_pct = compliance_metrics.get('compliance_percentage', 0)
            days_comp = compliance_metrics.get('days_compliant', 0)
            total_days = compliance_metrics.get('total_days', 0)
            
            print(f"\n📈 COMPLIANCE METRICS (Last {total_days} days)")
            print(f"   🎯 Goal: Keep count ≤ 3")
            print(f"   ✅ Days Compliant: {days_comp} / {total_days} ({compliance_pct:.1f}%)")
            
            if compliance_metrics.get('method') in ['field_history', 'report_criteria']:
                print(f"   📊 Count Range: {compliance_metrics.get('min_count', 0)} - {compliance_metrics.get('max_count', 0)}")
                print(f"   📊 Average Count: {compliance_metrics.get('avg_count', 0)}")
                if compliance_metrics.get('note'):
                    print(f"   ℹ️  {compliance_metrics['note']}")
        
        print()
    
    # Closed Value
    cv = metrics.get('closed_value', {})
    if cv.get('closed_count', 0) > 0:
        print("💰 CLOSED OUT VALUE METRICS")
        print(f"   Total Closed Value: ${cv['total_closed_value']:,.2f}")
        won_value = cv.get('won_value', 0)
        lost_value = cv.get('lost_value', 0)
        if won_value > 0 or lost_value > 0:
            print(f"   ✅ Won Value: ${won_value:,.2f}")
            print(f"   ❌ Lost Value: ${lost_value:,.2f}")
        print(f"   Average Closed Value: ${cv['avg_closed_value']:,.2f}")
        print(f"   Closed Count: {cv['closed_count']}")
        print(f"   Won Count: {cv['won_count']}")
        print(f"   Win Rate: {cv['win_rate']:.1f}%")
        
        # Show closed opportunities with links
        closed_opps = cv.get('closed_opportunities', [])
        if closed_opps:
            print(f"\n   📋 Closed Opportunities (from alerts):")
            for i, opp in enumerate(closed_opps, 1):
                opp_id = opp.get('Id', '')
                opp_name = opp.get('Name', 'Unknown')[:50]
                account_name = opp.get('Account', {}).get('Name', 'N/A')[:30] if opp.get('Account') else 'N/A'
                amount = float(opp.get('Amount', 0))
                close_date = opp.get('CloseDate', 'N/A')
                stage = opp.get('StageName', 'N/A')
                is_won = '✅ WON' if opp.get('IsWon') else '❌ Lost'
                
                # Get alert sent date based on flow (determine which field to use)
                flow_name = metrics.get('flow_name', '')
                if 'Ghost' in flow_name or metrics.get('flow_id') == '301PQ00000iX6QRYA0':
                    alert_field = GHOST_PIPELINE_ALERT_FIELD
                elif 'Past Due' in flow_name or metrics.get('flow_id') == '301PQ00000iMEFuYAO':
                    alert_field = PAST_DUE_ALERT_FIELD
                else:
                    alert_field = None
                
                alert_sent_date = opp.get(alert_field, 'N/A') if alert_field else 'N/A'
                # Format date if it exists
                if alert_sent_date != 'N/A' and alert_sent_date:
                    try:
                        alert_date = parse_salesforce_datetime(alert_sent_date)
                        if alert_date:
                            alert_sent_date = alert_date.strftime('%Y-%m-%d')
                    except:
                        pass
                
                opp_url = get_opportunity_url(opp_id) if opp_id else ''
                
                print(f"      {i}. {opp_name}")
                print(f"         Account: {account_name} | Stage: {stage} | {is_won}")
                # Display in order: Value | Alert Sent | Closed
                if alert_sent_date != 'N/A':
                    print(f"         Value: ${amount:,.2f} | 📅 Alert Sent: {alert_sent_date} | Closed: {close_date}")
                else:
                    print(f"         Value: ${amount:,.2f} | Closed: {close_date}")
                if opp_url:
                    print(f"         🔗 View: {opp_url}")
                print()
    else:
        print("💰 CLOSED OUT VALUE METRICS")
        print("   ⚠️  No closed value data available")
        print("   (May need custom logging to link Flow executions to Opportunities)")
    print()


def generate_json_report(all_metrics: List[Dict], output_file: Optional[str] = None) -> str:
    """Generate JSON report file"""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if not output_file:
        output_file = f"/Users/afleming/Desktop/Final Python Scripts/flow_slack_metrics_{timestamp}.json"
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'flows_analyzed': len(all_metrics),
        'metrics': all_metrics
    }
    
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    return output_file


def generate_csv_report(all_metrics: List[Dict], output_file: Optional[str] = None) -> str:
    """Generate CSV report file with closed opportunities"""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if not output_file:
        output_file = f"/Users/afleming/Desktop/Final Python Scripts/closed_opportunities_{timestamp}.csv"
    
    # Collect all closed opportunities from all flows
    all_closed_opps = []
    
    for metrics in all_metrics:
        flow_name = metrics.get('flow_name', 'Unknown Flow')
        flow_id = metrics.get('flow_id', 'N/A')
        cv = metrics.get('closed_value', {})
        closed_opps = cv.get('closed_opportunities', [])
        
        # Add flow context to each opportunity
        for opp in closed_opps:
            opp_with_context = opp.copy()
            opp_with_context['Flow_Name'] = flow_name
            opp_with_context['Flow_ID'] = flow_id
            opp_with_context['Salesforce_URL'] = get_opportunity_url(opp.get('Id', '')) if opp.get('Id') else ''
            all_closed_opps.append(opp_with_context)
    
    if not all_closed_opps:
        # Create empty CSV with headers
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Flow Name',
                'Flow ID',
                'Opportunity ID',
                'Opportunity Name',
                'Account Name',
                'Amount',
                'Close Date',
                'Stage',
                'Is Won',
                'Status',
                'Alert Sent Date',
                'Salesforce URL'
            ])
        return output_file
    
    # Write CSV with all opportunity data
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'Flow Name',
            'Flow ID',
            'Opportunity ID',
            'Opportunity Name',
            'Account Name',
            'Amount',
            'Close Date',
            'Stage',
            'Is Won',
            'Status',
            'Alert Sent Date',
            'Salesforce URL'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for opp in all_closed_opps:
            opp_id = opp.get('Id', '')
            opp_name = opp.get('Name', 'Unknown')
            account_name = opp.get('Account', {}).get('Name', 'N/A') if opp.get('Account') else 'N/A'
            amount = float(opp.get('Amount', 0))
            close_date = opp.get('CloseDate', 'N/A')
            stage = opp.get('StageName', 'N/A')
            is_won = opp.get('IsWon', False)
            status = 'Won' if is_won else 'Lost'
            
            # Get alert field value based on flow
            alert_field = None
            if opp.get('Flow_Name') == 'Ghost Pipeline' or 'Ghost' in opp.get('Flow_Name', ''):
                alert_field = GHOST_PIPELINE_ALERT_FIELD
            elif opp.get('Flow_Name') == 'Past Due Closed Date' or 'Past Due' in opp.get('Flow_Name', ''):
                alert_field = PAST_DUE_ALERT_FIELD
            
            alert_date = opp.get(alert_field, 'N/A') if alert_field else 'N/A'
            
            writer.writerow({
                'Flow Name': opp.get('Flow_Name', 'N/A'),
                'Flow ID': opp.get('Flow_ID', 'N/A'),
                'Opportunity ID': opp_id,
                'Opportunity Name': opp_name,
                'Account Name': account_name,
                'Amount': f"${amount:,.2f}" if amount > 0 else "$0.00",
                'Close Date': close_date,
                'Stage': stage,
                'Is Won': 'Yes' if is_won else 'No',
                'Status': status,
                'Alert Sent Date': alert_date,
                'Salesforce URL': opp.get('Salesforce_URL', '')
            })
    
    return output_file


def generate_html_dashboard(all_metrics: List[Dict], output_file: Optional[str] = None) -> List[str]:
    """Generate separate HTML dashboards for each Flow"""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_files = []
    
    # Generate a separate HTML file for each flow
    for metrics in all_metrics:
        flow_name = metrics.get('flow_name', 'Unknown Flow')
        flow_id = metrics.get('flow_id', 'N/A')
        
        # Create a safe filename from flow name
        safe_flow_name = flow_name.lower().replace(' ', '_').replace('/', '_')
        
        # Generate timestamped version
        timestamped_file = f"/Users/afleming/Desktop/Final Python Scripts/flow_slack_metrics_{safe_flow_name}_{timestamp}.html"
        
        # Generate "latest" version (consistent filename)
        latest_file = f"/Users/afleming/Desktop/Final Python Scripts/flow_slack_metrics_{safe_flow_name}_latest.html"
        
        html_content = _generate_single_flow_html(metrics)
        
        # Write timestamped version
        with open(timestamped_file, 'w') as f:
            f.write(html_content)
        output_files.append(timestamped_file)
        
        # Write latest version (same content, consistent filename)
        with open(latest_file, 'w') as f:
            f.write(html_content)
        output_files.append(latest_file)
    
    return output_files


def _generate_single_flow_html(metrics: Dict) -> str:
    """Generate HTML content for a single flow"""
    
    flow_name = metrics.get('flow_name', 'Unknown Flow')
    flow_id = metrics.get('flow_id', 'N/A')
    execution_method = metrics.get('execution_method', 'none')
    
    # Execution stats
    total = metrics.get('total_executions', 0)
    successful = metrics.get('successful_executions', 0)
    failed = metrics.get('failed_executions', 0)
    alerts_sent = metrics.get('alerts_sent', 0)
    success_rate = metrics.get('success_rate', 0)
    
    # Determine alert field for display
    if flow_id == '301PQ00000iX6QRYA0':  # Ghost Pipeline
        alert_field = GHOST_PIPELINE_ALERT_FIELD
    elif flow_id == '301PQ00000iMEFuYAO':  # Past Due Closed Date
        alert_field = PAST_DUE_ALERT_FIELD
    else:
        alert_field = None
    
    # Response time
    rt = metrics.get('response_time', {})
    rt_tracked = rt.get('total_with_response', 0)
    
    # Current status (for Past Due flow)
    current_status = metrics.get('current_status')
    
    # Closed value
    cv = metrics.get('closed_value', {})
    closed_count = cv.get('closed_count', 0)
    total_value = cv.get('total_closed_value', 0)
    won_value = cv.get('won_value', 0)
    lost_value = cv.get('lost_value', 0)
    
    # Build HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{flow_name} - Salesforce Flow Slack Alert Metrics</title>
    <style>
        :root {{
            --bg: #ffffff;
            --ink: #101418;
            --muted: #6b7280;
            --line: #e5e7eb;
            --panel: #fafafa;
            --brand: #4b7bec;
            --brand-2: #6b5af9;
            --accent: #f8fafc;
            --border: #e2e8f0;
            --glass: rgba(255,255,255,.65);
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        html, body {{
            margin: 0;
            background: var(--bg);
            color: var(--ink);
            font: 16px/1.45 -apple-system, BlinkMacSystemFont, Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        
        .wrap {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
            width: 100%;
        }}
        
        .hdr {{
            position: sticky;
            top: 0;
            z-index: 20;
            backdrop-filter: saturate(180%) blur(8px);
            background: linear-gradient(180deg, rgba(255,255,255,.92), rgba(255,255,255,.86) 60%, rgba(255,255,255,.70));
            border-bottom: 1px solid var(--line);
            padding: 12px 24px;
            margin: 0 -24px 12px;
        }}
        
        .hdr-inner {{
            display: flex;
            gap: 18px;
            align-items: flex-start;
            justify-content: space-between;
        }}
        
        .kicker {{
            letter-spacing: .22em;
            text-transform: uppercase;
            color: var(--muted);
            font-weight: 700;
            font-size: 12px;
        }}
        
        .title {{
            font-size: 24px;
            font-weight: 800;
            line-height: 1.1;
            margin: 4px 0 3px;
        }}
        
        .subtitle {{
            color: var(--muted);
            font-size: 13px;
            max-width: 960px;
            line-height: 1.4;
        }}
        
        .panel {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px;
            box-shadow: 0 1px 3px rgba(0,0,0,.05), 0 1px 2px rgba(0,0,0,.08);
            margin-bottom: 14px;
        }}
        
        .metric-section {{
            margin-bottom: 24px;
        }}
        
        .metric-section h3 {{
            color: var(--ink);
            font-size: 14px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: .08em;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
        }}
        
        .metric-box {{
            background: #fff;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            transition: transform .2s, box-shadow .2s;
        }}
        
        .metric-box:hover {{
            transform: translateY(-1px);
            box-shadow: 0 3px 8px rgba(0,0,0,.10);
        }}
        
        .metric-box[style*="border-left-color"] {{
            border-left-width: 4px;
            border-left-style: solid;
        }}
        
        .metric-label {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: var(--muted);
            margin-bottom: 8px;
        }}
        
        .metric-value {{
            font-size: 24px;
            font-weight: 800;
            color: var(--ink);
            font-variant-numeric: tabular-nums;
        }}
        
        .stat-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--line);
        }}
        
        .stat-row:last-child {{
            border-bottom: none;
        }}
        
        .stat-label {{
            color: var(--muted);
            font-size: 13px;
        }}
        
        .stat-value {{
            font-weight: 700;
            color: var(--ink);
            font-variant-numeric: tabular-nums;
        }}
        
        .chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 6px 10px;
            background: #fff;
            box-shadow: 0 1px 2px rgba(0,0,0,.05);
        }}
        
        .foot {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 14px;
            color: var(--muted);
            font-size: 12px;
        }}
        
        .brandmark {{
            font-weight: 900;
            letter-spacing: .08em;
        }}
        
        .note {{
            color: var(--muted);
            font-size: 12px;
            margin-top: 8px;
        }}
        
        .callout {{
            display: flex;
            align-items: center;
            gap: 12px;
            border-left: 4px solid var(--brand);
            background: linear-gradient(135deg, #f6f9ff, #f0f4ff);
            border-radius: 10px;
            padding: 14px 16px;
            font-size: 14px;
        }}
        
        .callout .strong {{
            font-weight: 800;
        }}
        
        code {{
            background: var(--accent);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 0.9em;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, monospace;
        }}
        
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
        }}
        
        @media (max-width: 1080px) {{
            .wrap {{
                padding: 18px;
            }}
            .title {{
                font-size: 22px;
            }}
            .metric-grid {{
                grid-template-columns: 1fr;
            }}
            .two-column {{
                grid-template-columns: 1fr;
            }}
        }}
        
        @media (max-width: 768px) {{
            .wrap {{
                padding: 12px;
            }}
            
            .hdr {{
                padding: 12px;
                margin: 0 -12px 12px;
            }}
            
            .hdr-inner {{
                flex-direction: column;
                gap: 12px;
            }}
            
            .header-content-wrapper {{
                flex-direction: column;
                gap: 12px;
            }}
            
            .header-flow-info {{
                width: 100%;
            }}
            
            .title {{
                font-size: 20px;
            }}
            
            .subtitle {{
                font-size: 12px;
            }}
            
            .kicker {{
                font-size: 10px;
            }}
            
            .metric-grid {{
                grid-template-columns: 1fr;
                gap: 10px;
            }}
            
            .metric-box {{
                padding: 12px;
            }}
            
            .metric-value {{
                font-size: 20px;
            }}
            
            .chip {{
                font-size: 11px;
                padding: 5px 8px;
            }}
            
            .panel {{
                padding: 12px;
                border-radius: 12px;
            }}
        }}
        
        @media (max-width: 480px) {{
            .wrap {{
                padding: 10px;
            }}
            
            .hdr {{
                padding: 10px;
                margin: 0 -10px 10px;
            }}
            
            .title {{
                font-size: 18px;
            }}
            
            .subtitle {{
                font-size: 11px;
            }}
            
            .metric-value {{
                font-size: 18px;
            }}
            
            .metric-label {{
                font-size: 10px;
            }}
            
            .chip {{
                font-size: 10px;
                padding: 4px 6px;
            }}
        }}
        
        .count-up {{
            font-variant-numeric: tabular-nums;
        }}
    </style>
    <script>
        // Animation: Count up numbers from 0
        function animateValue(element, start, end, duration, formatFn) {{
            let startTimestamp = null;
            const step = (timestamp) => {{
                if (!startTimestamp) startTimestamp = timestamp;
                const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                const value = Math.floor(progress * (end - start) + start);
                element.textContent = formatFn ? formatFn(value) : value;
                if (progress < 1) {{
                    window.requestAnimationFrame(step);
                }}
            }};
            window.requestAnimationFrame(step);
        }}
        
        function initAnimations() {{
            // Set zoom to 80% only on desktop (not mobile)
            if (window.innerWidth > 768) {{
                document.body.style.zoom = '0.8';
            }}
            
            // Find all metric values and animate them
            document.querySelectorAll('.metric-value').forEach(el => {{
                const originalText = el.textContent.trim();
                
                // Extract numbers from text
                let match = originalText.match(/[\$]?([\d,]+\.?\d*)/);
                if (match) {{
                    let numStr = match[1].replace(/,/g, '');
                    let num = parseFloat(numStr);
                    
                    if (!isNaN(num) && num > 0) {{
                        // Store original text for formatting reference
                        el.dataset.originalText = originalText;
                        
                        // Determine format
                        let formatFn;
                        if (originalText.includes('$')) {{
                            formatFn = (val) => {{
                                if (originalText.includes('.')) {{
                                    return '$' + val.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                                }} else {{
                                    return '$' + val.toLocaleString('en-US');
                                }}
                            }};
                        }} else if (originalText.includes('%')) {{
                            formatFn = (val) => val.toFixed(1) + '%';
                        }} else {{
                            formatFn = (val) => val.toLocaleString('en-US');
                        }}
                        
                        // Set initial value to 0
                        el.textContent = formatFn(0);
                        el.classList.add('count-up');
                        
                        // Animate with slight random delay for visual effect
                        setTimeout(() => {{
                            animateValue(el, 0, num, 1500, formatFn);
                        }}, Math.random() * 200);
                    }}
                }}
            }});
            
            // Animate stat values
            document.querySelectorAll('.stat-value').forEach(el => {{
                const originalText = el.textContent.trim();
                
                // Check if it contains hours format
                if (originalText.includes('hours') && originalText.includes('days')) {{
                    let match = originalText.match(/([\d,]+\.?\d*)\s+hours/);
                    if (match) {{
                        let numStr = match[1].replace(/,/g, '');
                        let num = parseFloat(numStr);
                        
                        if (!isNaN(num) && num > 0) {{
                            el.dataset.originalText = originalText;
                            el.textContent = '0.00 hours (0.0 days)';
                            
                            setTimeout(() => {{
                                animateValue(el, 0, num, 1500, (val) => {{
                                    const hours = val.toFixed(2);
                                    const days = (val / 24).toFixed(1);
                                    return hours + ' hours (' + days + ' days)';
                                }});
                            }}, 300);
                        }}
                    }}
                }} else {{
                    // Regular number
                    let match = originalText.match(/([\d,]+\.?\d*)/);
                    if (match) {{
                        let numStr = match[1].replace(/,/g, '');
                        let num = parseFloat(numStr);
                        
                        if (!isNaN(num) && num > 0) {{
                            el.dataset.originalText = originalText;
                            el.textContent = '0';
                            
                            setTimeout(() => {{
                                animateValue(el, 0, num, 1500, (val) => {{
                                    if (originalText.includes('.')) {{
                                        return val.toFixed(2);
                                    }} else {{
                                        return val.toLocaleString('en-US');
                                    }}
                                }});
                            }}, 300);
                        }}
                    }}
                }}
            }});
        }}
        
        // Run animations when page loads
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initAnimations);
        }} else {{
            initAnimations();
        }}
    </script>
</head>
<body>
    <div class="hdr">
        <div class="wrap hdr-inner">
            <div class="header-content-wrapper" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; flex-wrap: wrap;">
                <div style="flex: 1 1 auto; min-width: 0;">
                    <div class="kicker">Sales Ops • Flow Metrics</div>
                    <div class="title">{flow_name}</div>
                    <div class="subtitle">Real-time metrics for Slack alerts configured via Salesforce Flow Builder</div>
                    <div style="display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap;">
                        <div class="chip"><strong style="font-variant-numeric: tabular-nums;">{alerts_sent}</strong> alerts sent</div>
                        {f'<div class="chip"><strong style="font-variant-numeric: tabular-nums;">${total_value:,.0f}</strong> closed value</div>' if closed_count > 0 else ''}
                        {f'<div class="chip"><strong style="font-variant-numeric: tabular-nums;">{cv.get("win_rate", 0):.1f}%</strong> win rate</div>' if closed_count > 0 else ''}
                        <div class="chip"><span style="font-variant-numeric: tabular-nums;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span> updated</div>
                    </div>
                </div>
                
                <div class="header-flow-info" style="background: var(--glass); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; backdrop-filter: blur(10px); flex: 0 0 auto;">
                    <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 4px;">Flow ID</div>
                    <div style="font-weight: 700; font-family: 'SF Mono', Monaco, monospace; font-size: 11px; color: var(--ink); margin-bottom: 12px; word-break: break-all;">{flow_id}</div>
                    <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 4px;">📤 Alerts Sent</div>
                    <div style="font-size: 20px; font-weight: 800; color: var(--ink); font-variant-numeric: tabular-nums;">{alerts_sent}</div>
                    {f'<div style="font-size: 10px; color: var(--muted); line-height: 1.3; margin-top: 6px;">ℹ️ <code style="font-size: 9px;">{alert_field if alert_field else "N/A"}</code></div>' if execution_method == 'custom_field' and alerts_sent > 0 else ''}
                </div>
            </div>
        </div>
    </div>
    
    <div class="wrap">
"""
    
    # Current Status section (for Past Due flow)
    compliance_metrics = metrics.get('compliance_metrics')
    
    # Get breakdown counts for display
    alert_count = current_status.get('alert_field_count', 0) if current_status else 0
    report_count = current_status.get('report_criteria_count', 0) if current_status else 0
    
    if current_status and current_status.get('current_count') is not None:
        count = current_status['current_count']
        status = current_status['status']
        status_icon = '✅' if status == 'compliant' else '⚠️'
        status_color = '#30d158' if status == 'compliant' else '#ff9500'
        
        html_content += f"""
        <div class="panel">
            <div class="metric-section">
                <h3>📊 Current Status</h3>
                <div class="metric-box" style="border-left-color: {status_color};">
                    <div class="metric-label">Current Past Due Count (Report Criteria - EXACT MATCH)</div>
                    <div class="metric-value" style="color: {status_color};">{status_icon} {count}</div>
                    <div class="note" style="margin-top: 12px;">
                        {'🎯 All caught up! Goal achieved.' if status == 'compliant' else '📌 Action needed to bring count to 0'}
                        {'<br><span style="font-size: 0.75em;">ℹ️ This matches your Salesforce report exactly</span>' if report_count == count else ''}
                    </div>
"""
        
        # Show breakdown if there's a discrepancy
        if report_count > alert_count and report_count > 0:
            html_content += f"""
                    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line);">
                        <div style="font-size: 13px; color: var(--muted);">
                            <div style="font-weight: 700; margin-bottom: 6px; color: var(--ink);">Breakdown:</div>
                            <div style="margin-bottom: 4px;">📊 Report Criteria: <strong style="font-variant-numeric: tabular-nums;">{report_count}</strong></div>
                            <div style="margin-bottom: 4px;">🏷️  Alert Field: <strong style="font-variant-numeric: tabular-nums;">{alert_count}</strong></div>
                            <div style="color: var(--warning); margin-top: 6px; font-weight: 600;">⚠️  Gap: {report_count - alert_count} opportunities</div>
                            <div class="note" style="margin-top: 8px;">
                                Report shows ALL past due opportunities. Alert field shows only those the flow has tracked.
                            </div>
                        </div>
                    </div>
"""
        
        # Add compliance metrics if available
        if compliance_metrics and compliance_metrics.get('method') in ['field_history', 'report_criteria', 'estimated_current_only']:
            compliance_pct = compliance_metrics.get('compliance_percentage', 0)
            days_comp = compliance_metrics.get('days_compliant', 0)
            total_days = compliance_metrics.get('total_days', 30)
            compliance_color = '#30d158' if compliance_pct >= 90 else '#ff9500' if compliance_pct >= 70 else '#ff3b30'
            
            html_content += f"""
                <div class="metric-box" style="border-left-color: {compliance_color}; margin-top: 12px;">
                    <div class="metric-label">Compliance (Count ≤ 3)</div>
                    <div class="metric-value" style="color: {compliance_color}; font-size: 20px;">{compliance_pct:.1f}%</div>
                    <div class="note" style="margin-top: 8px;">
                        {days_comp} of {total_days} days compliant (last 30 days)
                    </div>
"""
            
            if compliance_metrics.get('method') in ['field_history', 'report_criteria']:
                html_content += f"""
                    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line);">
                        <div style="font-size: 13px; color: var(--muted); display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;">
                            <div><span style="font-weight: 600;">Min:</span> <span style="font-variant-numeric: tabular-nums;">{compliance_metrics.get('min_count', 0)}</span></div>
                            <div><span style="font-weight: 600;">Max:</span> <span style="font-variant-numeric: tabular-nums;">{compliance_metrics.get('max_count', 0)}</span></div>
                            <div><span style="font-weight: 600;">Avg:</span> <span style="font-variant-numeric: tabular-nums;">{compliance_metrics.get('avg_count', 0)}</span></div>
                        </div>
                    </div>
"""
            
            # Show breakdown if available
            if report_count > alert_count:
                gap = report_count - alert_count
                gap_analysis = metrics.get('gap_analysis')
                
                html_content += f"""
                <div style="margin-top: 14px; padding: 14px; background: linear-gradient(135deg, #fff9e6, #fff5e0); border-left: 4px solid var(--warning); border-radius: 10px;">
                    <div style="font-size: 13px;">
                        <div style="font-weight: 700; margin-bottom: 8px; color: var(--ink);">📊 Breakdown:</div>
                        <div style="margin-bottom: 4px;">📊 Report Criteria: <strong style="font-variant-numeric: tabular-nums;">{report_count}</strong></div>
                        <div style="margin-bottom: 4px;">🏷️  Alert Field: <strong style="font-variant-numeric: tabular-nums;">{alert_count}</strong></div>
                        <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); color: var(--warning); font-weight: 700;">⚠️  Gap: {gap} opportunities</div>
"""
                
                # Add gap analysis details if available
                if gap_analysis and gap_analysis.get('sample_opportunities'):
                        sample_opps = gap_analysis['sample_opportunities'][:5]
                        html_content += f"""
                                <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ddd;">
                                    <div style="font-weight: 600; margin-bottom: 8px; color: #333;">🔍 Sample Opportunities Without Alert Field:</div>
                                    <div style="font-size: 0.85em;">
"""
                        for i, opp in enumerate(sample_opps, 1):
                            opp_name = opp.get('Name', 'Unknown')[:50]
                            close_date = opp.get('CloseDate', 'N/A')
                            stage = opp.get('StageName', 'N/A')
                            days_past = ''
                            if close_date and close_date != 'N/A':
                                try:
                                    cd = datetime.fromisoformat(close_date + 'T00:00:00')
                                    days_past = f"({(datetime.now() - cd).days} days past due)"
                                except:
                                    pass
                            html_content += f"""
                                        <div style="margin-bottom: 6px; padding: 8px; background: white; border-radius: 3px;">
                                            <strong>{i}.</strong> {opp_name}<br>
                                            <span style="color: #666; font-size: 0.9em;">Stage: {stage} | Close: {close_date} {days_past}</span>
                                        </div>
"""
                        
                        if gap_analysis.get('insights'):
                            html_content += """
                                    </div>
                                    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ddd;">
                                        <div style="font-weight: 600; margin-bottom: 8px; color: #333;">💡 Insights:</div>
                                        <ul style="margin: 0; padding-left: 20px; font-size: 0.85em; color: #666;">
"""
                            for insight in gap_analysis['insights']:
                                html_content += f'<li style="margin-bottom: 4px;">{insight}</li>\n'
                            html_content += """
                                        </ul>
                                    </div>
"""
                        
                        html_content += """
                                    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ddd;">
                                        <div style="font-weight: 600; margin-bottom: 8px; color: #333;">💡 Possible Reasons for Gap:</div>
                                        <ul style="margin: 0; padding-left: 20px; font-size: 0.85em; color: #666;">
                                            <li style="margin-bottom: 4px;">Flow may only trigger when CloseDate PASSES (scheduled)</li>
                                            <li style="margin-bottom: 4px;">Flow conditions may exclude some opportunities</li>
                                            <li style="margin-bottom: 4px;">Flow cleared the field when opportunities were updated</li>
                                            <li style="margin-bottom: 4px;">Flow hasn't run yet for opportunities that became past due</li>
                                        </ul>
                                    </div>
                                    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ddd; background: #e8f5e9; padding: 10px; border-radius: 3px;">
                                        <div style="font-weight: 600; color: #2e7d32;">🎯 Recommendation:</div>
                                        <div style="font-size: 0.85em; color: #2e7d32; margin-top: 4px;">
                                            The report count (<strong>{report_count}</strong>) is the TRUE state.<br>
                                            Use this for compliance tracking instead of alert field.
                                        </div>
                                    </div>
"""
                    
                html_content += """
                            </div>
                        </div>
"""
            
            html_content += """
                    </div>
                </div>
            </div>
        </div>
"""
    
    # Closed Value section (moved up) - More compact horizontal layout
    if closed_count > 0:
        html_content += f"""
        <div class="panel">
            <div class="metric-section">
                <h3>💰 Closed Out Value</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;">
                    <div class="metric-box">
                        <div class="metric-label">Total Value</div>
                        <div class="metric-value">${total_value:,.2f}</div>
                    </div>
                    <div class="metric-box" style="border-left-color: var(--success);">
                        <div class="metric-label">✅ Won Value</div>
                        <div class="metric-value" style="color: var(--success);">${won_value:,.2f}</div>
                    </div>
                    <div class="metric-box" style="border-left-color: var(--warning);">
                        <div class="metric-label">❌ Lost Value</div>
                        <div class="metric-value" style="color: var(--warning);">${lost_value:,.2f}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Closed Count</div>
                        <div class="metric-value">{closed_count}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Win Rate</div>
                        <div class="metric-value">{cv.get('win_rate', 0):.1f}%</div>
                    </div>
                </div>
"""
        
        # Add closed opportunities list with clickable links (collapsible)
        closed_opps = cv.get('closed_opportunities', [])
        if closed_opps:
            html_content += f"""
                <div style="margin-top: 20px; padding-top: 20px; border-top: 2px solid var(--line);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; cursor: pointer;" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'; this.querySelector('.toggle-icon').textContent = this.nextElementSibling.style.display === 'none' ? '▶' : '▼';">
                        <h4 style="color: var(--ink); margin: 0; font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em;">📋 Closed Opportunities (Result of Alerts) - {len(closed_opps)} total</h4>
                        <span class="toggle-icon" style="font-size: 12px; color: var(--muted);">▼</span>
                    </div>
                    <div style="max-height: 400px; overflow-y: auto;">
"""
            for i, opp in enumerate(closed_opps, 1):
                opp_id = opp.get('Id', '')
                opp_name = opp.get('Name', 'Unknown')[:60]
                account_name = opp.get('Account', {}).get('Name', 'N/A')[:40] if opp.get('Account') else 'N/A'
                amount = float(opp.get('Amount', 0))
                close_date = opp.get('CloseDate', 'N/A')
                stage = opp.get('StageName', 'N/A')
                is_won = opp.get('IsWon', False)
                status_color = '#30d158' if is_won else '#ff9500'
                status_text = '✅ WON' if is_won else '❌ Lost'
                
                # Get alert sent date based on flow
                flow_name = metrics.get('flow_name', '')
                if 'Ghost' in flow_name or metrics.get('flow_id') == '301PQ00000iX6QRYA0':
                    alert_field = GHOST_PIPELINE_ALERT_FIELD
                elif 'Past Due' in flow_name or metrics.get('flow_id') == '301PQ00000iMEFuYAO':
                    alert_field = PAST_DUE_ALERT_FIELD
                else:
                    alert_field = None
                
                alert_sent_date = opp.get(alert_field, 'N/A') if alert_field else 'N/A'
                # Format date if it exists
                if alert_sent_date != 'N/A' and alert_sent_date:
                    try:
                        alert_date = parse_salesforce_datetime(alert_sent_date)
                        if alert_date:
                            alert_sent_date = alert_date.strftime('%Y-%m-%d')
                    except:
                        pass
                
                opp_url = get_opportunity_url(opp_id) if opp_id else ''
                
                html_content += f"""
                        <div style="margin-bottom: 12px; padding: 12px; background: #fff; border: 1px solid var(--border); border-left: 4px solid {status_color}; border-radius: 10px; transition: transform .2s, box-shadow .2s;" onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,.10)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                                <div style="flex: 1;">
                                    <div style="font-weight: 700; font-size: 14px; color: var(--ink); margin-bottom: 6px;">
                                        {i}. {opp_name}
                                    </div>
                                    <div style="font-size: 13px; color: var(--muted); margin-bottom: 4px;">
                                        <span style="font-weight: 600;">Account:</span> {account_name} | 
                                        <span style="font-weight: 600;">Stage:</span> {stage} | 
                                        <span style="color: {status_color}; font-weight: 700;">{status_text}</span>
                                    </div>
                                    <div style="font-size: 13px; color: var(--muted);">
                                        <span style="font-weight: 600;">Value:</span> <span style="font-variant-numeric: tabular-nums;">${amount:,.2f}</span>"""
                
                if alert_sent_date != 'N/A':
                    html_content += f""" | 
                                        <span style="font-weight: 600;">📅 Alert Sent:</span> {alert_sent_date}"""
                
                html_content += f""" | 
                                        <span style="font-weight: 600;">Closed:</span> {close_date}
                                    </div>
                                </div>
"""
                if opp_url:
                    html_content += f"""
                                <a href="{opp_url}" target="_blank" style="background: var(--brand); color: white; padding: 8px 14px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: 700; white-space: nowrap; margin-left: 10px; display: inline-block; transition: transform .2s, box-shadow .2s;" onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,.15)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
                                    🔗 View in Salesforce
                                </a>
"""
                html_content += """
                            </div>
                        </div>
"""
            html_content += """
                    </div>
                </div>
            </div>
        </div>
"""
    
    # Add Response Time section below Closed Out Value
    if rt_tracked > 0:
        html_content += f"""
        <div class="panel">
            <div class="metric-section">
                <h3>⏱️ Response Time</h3>
                <div class="metric-grid">
                    <div class="metric-box">
                        <div class="metric-label">Average Response</div>
                        <div class="metric-value">{rt.get('avg_response_hours', 0):.2f} hours</div>
                        <div class="note" style="margin-top: 4px;">({rt.get('avg_response_hours', 0)/24:.1f} days)</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Median Response</div>
                        <div class="metric-value">{rt.get('median_response_hours', 0):.2f} hours</div>
                        <div class="note" style="margin-top: 4px;">({rt.get('median_response_hours', 0)/24:.1f} days)</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Responses Tracked</div>
                        <div class="metric-value">{rt_tracked}</div>
                    </div>
                </div>
            </div>
        </div>
"""
    else:
        html_content += """
        <div class="panel">
            <div class="metric-section">
                <h3>⏱️ Response Time</h3>
                <div class="note">No response time data available</div>
            </div>
        </div>
"""
    
    if closed_count == 0:
        html_content += """
        <div class="panel">
            <div class="metric-section">
                <h3>💰 Closed Out Value</h3>
                <div class="note">No closed value data available</div>
            </div>
        </div>
"""
    
    # Add Flow Setup Analysis for Past Due flow
    if flow_id == '301PQ00000iMEFuYAO' and metrics.get('flow_setup_analysis'):
        flow_setup = metrics.get('flow_setup_analysis')
        efficiency = flow_setup.get('efficiency_score', 0)
        optimal = flow_setup.get('optimal', False)
        setup_type = flow_setup.get('setup_type', 'unknown')
        
        efficiency_color = '#30d158' if efficiency >= 90 else '#ff9500' if efficiency >= 70 else '#ff3b30'
        
        html_content += f"""
            <div class="metric-section">
                <h3>🔧 Flow Setup Analysis</h3>
                <div class="metric-box" style="border-left-color: {efficiency_color};">
                    <div class="metric-label">Efficiency Score</div>
                    <div class="metric-value" style="color: {efficiency_color};">{efficiency}%</div>
                    <p style="font-size: 0.85em; color: #666; margin-top: 10px;">
                        Status: <strong>{'✅ Optimal' if optimal else '⚠️ Needs Improvement'}</strong> | 
                        Type: <strong>{setup_type.replace('_', ' ').title()}</strong>
                    </p>
"""
        
        issues = flow_setup.get('issues', [])
        if issues:
            html_content += """
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;">
                        <div style="font-weight: 600; margin-bottom: 8px; color: #333;">⚠️ Issues Found:</div>
                        <ul style="margin: 0; padding-left: 20px; font-size: 0.85em; color: #666;">
"""
            for issue in issues:
                severity = issue.get('severity', 'medium')
                severity_color = '#ff3b30' if severity == 'critical' else '#ff9500' if severity == 'high' else '#ff9500'
                html_content += f"""
                            <li style="margin-bottom: 6px;">
                                <span style="color: {severity_color}; font-weight: 600;">[{severity.upper()}]</span> {issue.get('issue', 'Unknown issue')}
                                <br><span style="color: #999; font-size: 0.9em;">Impact: {issue.get('impact', 'N/A')}</span>
                            </li>
"""
            html_content += """
                        </ul>
                    </div>
"""
        
        recommendations = flow_setup.get('recommendations', [])
        if recommendations:
            html_content += """
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;">
                        <div style="font-weight: 600; margin-bottom: 8px; color: #333;">💡 Recommendations:</div>
                        <ul style="margin: 0; padding-left: 20px; font-size: 0.85em; color: #666;">
"""
            for rec in recommendations:
                priority = rec.get('priority', 'medium')
                priority_color = '#ff3b30' if priority == 'critical' else '#ff9500' if priority == 'high' else '#0176d3'
                html_content += f"""
                            <li style="margin-bottom: 8px;">
                                <span style="color: {priority_color}; font-weight: 600;">[{priority.upper()}]</span> {rec.get('recommendation', 'Unknown recommendation')}
"""
                if rec.get('details'):
                    html_content += """
                                <ul style="margin-top: 4px; padding-left: 20px; color: #666;">
"""
                    for detail in rec['details']:
                        html_content += f"""
                                    <li style="margin-bottom: 2px;">{detail}</li>
"""
                    html_content += """
                                </ul>
"""
                html_content += """
                            </li>
"""
            html_content += """
                        </ul>
                    </div>
"""
        
        html_content += """
                </div>
            </div>
"""
    
    # Close HTML
    html_content += """
        <div class="foot">
            <div class="note">Report generated automatically • Refresh page to update metrics</div>
            <div class="brandmark">INNOVATIVE • FLOW METRICS</div>
        </div>
    </div>
</body>
</html>
"""
    
    return html_content


# ==========================================================
# MAIN
# ==========================================================
def main():
    """Main function"""
    
    print("\n" + "="*70)
    print("🚀 Salesforce Flow Slack Alert Metrics Tracker")
    print("="*70 + "\n")
    
    # Get Flow IDs
    flow_ids = []
    flow_names = []
    
    # Extract Flow IDs from URLs or use direct IDs
    # Flow 1: Ghost Pipeline
    if FLOW_ID_1:
        flow_ids.append(FLOW_ID_1)
        flow_names.append('Ghost Pipeline')
    elif FLOW_URL_1:
        flow_id = extract_flow_id_from_url(FLOW_URL_1)
        if flow_id:
            flow_ids.append(flow_id)
            flow_names.append('Ghost Pipeline')
        else:
            print(f"⚠️  Could not extract Flow ID from URL 1: {FLOW_URL_1}")
    
    # Flow 2: Past Due Closed Date
    if FLOW_ID_2:
        flow_ids.append(FLOW_ID_2)
        flow_names.append('Past Due Closed Date')
    elif FLOW_URL_2:
        flow_id = extract_flow_id_from_url(FLOW_URL_2)
        if flow_id:
            flow_ids.append(flow_id)
            flow_names.append('Past Due Closed Date')
        else:
            print(f"⚠️  Could not extract Flow ID from URL 2: {FLOW_URL_2}")
    
    if not flow_ids:
        print("❌ No Flow IDs found!")
        print("\nPlease set one of the following:")
        print("  - FLOW_URL_1 and FLOW_URL_2 environment variables")
        print("  - FLOW_ID_1 and FLOW_ID_2 environment variables")
        print("  - Or update FLOW_URL_1 and FLOW_URL_2 in the script")
        return
    
    # Connect to Salesforce
    sf = connect_to_salesforce()
    
    # Get Flow names
    for i, flow_id in enumerate(flow_ids):
        flow_names[i] = get_flow_name(sf, flow_id)
    
    # Calculate metrics for each Flow
    all_metrics = []
    for i, (flow_id, flow_name) in enumerate(zip(flow_ids, flow_names)):
        # Determine alert field based on flow
        alert_field = None
        if flow_id == '301PQ00000iX6QRYA0':  # Ghost Pipeline
            alert_field = GHOST_PIPELINE_ALERT_FIELD
        elif flow_id == '301PQ00000iMEFuYAO':  # Past Due Closed Date
            alert_field = PAST_DUE_ALERT_FIELD  # Overdue_Alert_Sent_Date__c
        
        metrics = calculate_flow_metrics(sf, flow_id, flow_name, DEFAULT_DAYS_BACK, alert_field)
        all_metrics.append(metrics)
        print_metrics_report(metrics)
    
    # Generate reports
    print("\n" + "="*70)
    print("📄 Generating Reports...")
    print("="*70 + "\n")
    
    json_file = generate_json_report(all_metrics)
    html_files = generate_html_dashboard(all_metrics)
    csv_file = generate_csv_report(all_metrics)
    
    print(f"✅ JSON report saved: {json_file}")
    print(f"✅ CSV report saved: {csv_file}")
    print(f"\n✅ HTML dashboards saved:")
    
    # Separate timestamped and latest files for better display
    timestamped_files = [f for f in html_files if '_latest.html' not in f]
    latest_files = [f for f in html_files if '_latest.html' in f]
    
    if timestamped_files:
        print("\n   📅 Timestamped versions (for history):")
        for html_file in timestamped_files:
            print(f"      📄 {html_file}")
    
    if latest_files:
        print("\n   🔗 Latest versions (consistent links to share):")
        for html_file in latest_files:
            filename = os.path.basename(html_file)
            safe_name = filename.replace('_latest.html', '').replace('flow_slack_metrics_', '')
            print(f"      📄 {filename}")
            print(f"      🌐 GitHub Pages: https://astonatinnovativesol.github.io/salesforce-flow-metrics/{filename}")
    print()


if __name__ == "__main__":
    main()

