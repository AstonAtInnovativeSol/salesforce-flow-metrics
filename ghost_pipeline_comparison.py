#!/usr/bin/env python3
"""
Ghost Pipeline Comparison - Opportunities WITH vs WITHOUT Alerts
Analyzes last 90 days of opportunities to compare win rates, sales cycle velocity,
and Reason for Loss/Win between alerted and non-alerted opportunities.
"""

import os
import time
import jwt
import requests
import json
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from collections import defaultdict
import sys

# Import sf_config - adjust path if needed
try:
    import sf_config
except ImportError:
    # Try alternative import paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Try main folder first
    sys.path.insert(0, script_dir)
    # Try "Live and migrated to GitHub" folder
    live_folder = os.path.join(script_dir, "Live and migrated to GitHub")
    if os.path.exists(live_folder):
        sys.path.insert(0, live_folder)
    # Try "Historical Artifact" folder
    historical_folder = os.path.join(script_dir, "Historical Artifact")
    if os.path.exists(historical_folder):
        sys.path.insert(0, historical_folder)
    import sf_config

# ==========================================================
# CONFIGURATION
# ==========================================================
OUTPUT_DIR = Path.home() / "Desktop" / "Final Python Scripts"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

LOOKBACK_DAYS = 90

# ==========================================================
# SALESFORCE AUTHENTICATION
# ==========================================================
def get_salesforce_token():
    """Get Salesforce access token using JWT"""
    try:
        with open(sf_config.PRIVATE_KEY_FILE, 'r') as f:
            private_key = f.read()
        
        now = int(time.time())
        payload = {
            'iss': sf_config.SF_CONSUMER_KEY,
            'sub': sf_config.SF_USERNAME,
            'aud': f"https://{sf_config.SF_DOMAIN}.salesforce.com",
            'exp': now + 300,
            'iat': now
        }
        
        token = jwt.encode(payload, private_key, algorithm='RS256')
        
        response = requests.post(
            f"https://{sf_config.SF_DOMAIN}.salesforce.com/services/oauth2/token",
            data={
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': token
            }
        )
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data['access_token'], token_data['instance_url']
        else:
            print(f"❌ Authentication failed: {response.status_code} - {response.text}")
            return None, None
            
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None, None

def soql_query(token, instance_url, query):
    """Execute SOQL query against Salesforce"""
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Use API version from config if available, otherwise default to v61.0
        api_version = getattr(sf_config, 'SF_API_VERSION', 'v61.0')
        
        response = requests.get(
            f"{instance_url}/services/data/{api_version}/query",
            headers=headers,
            params={'q': query}
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('records', [])
        else:
            print(f"❌ Query failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Query error: {e}")
        return []

# ==========================================================
# DATA COLLECTION
# ==========================================================
def get_opportunities_without_alerts(token, instance_url):
    """Get opportunities from last 90 days where Ghost_Pipeline_Alert_Sent_Date__c is blank"""
    print("\n📊 Querying opportunities WITHOUT alerts (last 90 days)...")
    
    ninety_days_ago = (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    
    # Query for opportunities without alerts
    # Matching Salesforce report filters:
    # - CloseDate in last 90 days
    # - Only closed opportunities with specific stages
    # - Exclude Test Account1 and ACME Corporation
    # Using Reason_for_Closed_Lost__c for loss reasons (auto close reason)
    # Note: CloseDate must be date format (YYYY-MM-DD), CreatedDate can be datetime
    query = f"""
        SELECT Id, Name, StageName, CreatedDate, CloseDate, 
               Amount, Professional_Services_Amount__c,
               IsWon, IsClosed, IsDeleted,
               AccountId, Account.Name,
               OwnerId, Owner.Name, Owner.IsActive,
               Reason_for_Closed_Lost__c,
               Ghost_Pipeline_Alert_Sent_Date__c,
               Ghost_Pipeline_Manager_Alerted__c
        FROM Opportunity
        WHERE CloseDate >= {ninety_days_ago}
        AND IsClosed = true
        AND StageName IN ('Closed Won - Pending', 'Closed Won', 'Closed Lost', 'Disqualified', 'Closed Won - Later Cancelled')
        AND Ghost_Pipeline_Alert_Sent_Date__c = NULL
        AND (Amount != NULL OR Professional_Services_Amount__c != NULL)
        AND IsDeleted = false
        ORDER BY CloseDate DESC NULLS LAST, CreatedDate DESC
    """
    
    opps = soql_query(token, instance_url, query)
    
    # Filter out Test Account1 and ACME Corporation (SOQL doesn't support NOT LIKE on relationship fields)
    # Also exclude opportunities without accounts (matching Salesforce report behavior)
    # Account.Name is returned as a nested object in the query results
    filtered_opps = []
    for o in opps:
        account = o.get('Account')
        if not account or not isinstance(account, dict):
            continue  # Skip opportunities without accounts
        account_name = account.get('Name', '')
        if not account_name:
            continue  # Skip opportunities without account names
        # Exclude test accounts
        if 'Test Account1' not in account_name and 'ACME Corporation' not in account_name:
            filtered_opps.append(o)
    opps = filtered_opps
    
    print(f"✅ Found {len(opps)} opportunities WITHOUT alerts")
    return opps

def get_opportunities_with_alerts(token, instance_url):
    """Get opportunities from last 90 days where Ghost_Pipeline_Alert_Sent_Date__c is NOT blank"""
    print("\n📊 Querying opportunities WITH alerts (last 90 days)...")
    
    ninety_days_ago = (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    
    # Query for opportunities with alerts
    # Matching Salesforce report filters:
    # - CloseDate in last 90 days
    # - Only closed opportunities with specific stages
    # - Exclude Test Account1 and ACME Corporation
    # Using Reason_for_Closed_Lost__c for loss reasons (auto close reason)
    # Note: CloseDate must be date format (YYYY-MM-DD), CreatedDate can be datetime
    query = f"""
        SELECT Id, Name, StageName, CreatedDate, CloseDate, 
               Amount, Professional_Services_Amount__c,
               IsWon, IsClosed, IsDeleted,
               AccountId, Account.Name,
               OwnerId, Owner.Name, Owner.IsActive,
               Reason_for_Closed_Lost__c,
               Ghost_Pipeline_Alert_Sent_Date__c,
               Ghost_Pipeline_Manager_Alerted__c
        FROM Opportunity
        WHERE CloseDate >= {ninety_days_ago}
        AND IsClosed = true
        AND StageName IN ('Closed Won - Pending', 'Closed Won', 'Closed Lost', 'Disqualified', 'Closed Won - Later Cancelled')
        AND Ghost_Pipeline_Alert_Sent_Date__c != NULL
        AND (Amount != NULL OR Professional_Services_Amount__c != NULL)
        AND IsDeleted = false
        ORDER BY CloseDate DESC NULLS LAST, CreatedDate DESC
    """
    
    opps = soql_query(token, instance_url, query)
    
    # Filter out Test Account1 and ACME Corporation (SOQL doesn't support NOT LIKE on relationship fields)
    # Also exclude opportunities without accounts (matching Salesforce report behavior)
    # Account.Name is returned as a nested object in the query results
    filtered_opps = []
    for o in opps:
        account = o.get('Account')
        if not account or not isinstance(account, dict):
            continue  # Skip opportunities without accounts
        account_name = account.get('Name', '')
        if not account_name:
            continue  # Skip opportunities without account names
        # Exclude test accounts
        if 'Test Account1' not in account_name and 'ACME Corporation' not in account_name:
            filtered_opps.append(o)
    opps = filtered_opps
    
    print(f"✅ Found {len(opps)} opportunities WITH alerts")
    return opps

# ==========================================================
# ANALYSIS FUNCTIONS
# ==========================================================
def analyze_opportunities(opps, group_name):
    """Analyze a group of opportunities"""
    print(f"\n📈 Analyzing {group_name}...")
    
    # Filter closed opportunities
    closed_opps = [o for o in opps if o.get('IsClosed', False)]
    won_opps = [o for o in closed_opps if o.get('IsWon', False)]
    lost_opps = [o for o in closed_opps if not o.get('IsWon', False)]
    
    # Calculate values
    def get_value(opp):
        """Get opportunity value, preferring Professional_Services_Amount__c"""
        val = opp.get('Professional_Services_Amount__c')
        if val is None or val == 0:
            val = opp.get('Amount', 0)
        return float(val or 0)
    
    total_value = sum(get_value(o) for o in opps)
    won_value = sum(get_value(o) for o in won_opps)
    lost_value = sum(get_value(o) for o in lost_opps)
    closed_value = won_value + lost_value
    
    # Calculate win rate
    total_closed = len(closed_opps)
    total_won = len(won_opps)
    total_lost = len(lost_opps)
    win_rate = (total_won / total_closed * 100) if total_closed > 0 else 0
    
    # Calculate sales cycle (days from creation to close)
    cycles = []
    debug_count = 0
    for opp in closed_opps:
        try:
            created_raw = opp.get('CreatedDate', '')
            close_raw = opp.get('CloseDate', '')
            
            if not created_raw or not close_raw:
                continue
            
            # Parse CreatedDate - comes as ISO datetime string from Salesforce like "2025-08-06T12:34:56.000Z" or "2025-08-06T12:34:56.000+0000"
            if isinstance(created_raw, str):
                # Handle ISO format with timezone
                # Salesforce returns formats like: "2025-10-30T16:54:37.000+0000" (no colon in timezone)
                # Convert timezone formats to ISO format that fromisoformat can parse
                created_str = created_raw
                if created_str.endswith('Z'):
                    created_str = created_str[:-1] + '+00:00'
                else:
                    # Replace timezone offsets like +0000, -0500, +0530 with +00:00, -05:00, +05:30
                    # Pattern matches: +HHMM or -HHMM at end of string
                    tz_pattern = r'([+-])(\d{2})(\d{2})$'
                    if re.search(tz_pattern, created_str) and ':' not in created_str[-6:]:
                        # Replace +HHMM with +HH:MM
                        created_str = re.sub(tz_pattern, r'\1\2:\3', created_str)
                created = datetime.fromisoformat(created_str)
            elif isinstance(created_raw, datetime):
                created = created_raw
            elif isinstance(created_raw, date):
                created = datetime.combine(created_raw, datetime.min.time())
            else:
                if debug_count < 3:
                    print(f"    ⚠️  CreatedDate unexpected type: {type(created_raw)}, value: {created_raw}")
                    debug_count += 1
                continue
            
            # Parse CloseDate - comes as date string (YYYY-MM-DD) or date object from Salesforce
            if isinstance(close_raw, str):
                # CloseDate is typically just YYYY-MM-DD format (no time component)
                if 'T' in close_raw:
                    # Has time component (unusual but handle it)
                    if close_raw.endswith('Z'):
                        close = datetime.fromisoformat(close_raw[:-1] + '+00:00')
                    else:
                        close = datetime.fromisoformat(close_raw)
                else:
                    # Just date (YYYY-MM-DD), parse and convert to datetime at midnight
                    try:
                        # Parse as YYYY-MM-DD
                        close = datetime.strptime(close_raw, '%Y-%m-%d')
                    except ValueError:
                        # Try other date formats
                        try:
                            close = datetime.strptime(close_raw, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            # Last resort: try fromisoformat
                            close = datetime.fromisoformat(close_raw)
            elif isinstance(close_raw, datetime):
                close = close_raw
            elif isinstance(close_raw, date):
                # It's a date object, convert to datetime at midnight
                close = datetime.combine(close_raw, datetime.min.time())
            else:
                if debug_count < 3:
                    print(f"    ⚠️  CloseDate unexpected type: {type(close_raw)}, value: {close_raw}")
                    debug_count += 1
                continue
            
            # Remove timezone for calculation (convert to naive datetime)
            if hasattr(created, 'tzinfo') and created.tzinfo is not None:
                created = created.replace(tzinfo=None)
            if hasattr(close, 'tzinfo') and close.tzinfo is not None:
                close = close.replace(tzinfo=None)
            
            # Calculate difference in days
            if isinstance(created, datetime) and isinstance(close, datetime):
                cycle_days = (close.date() - created.date()).days
                if cycle_days >= 0:  # Valid cycle (close >= created)
                    cycles.append(cycle_days)
                elif debug_count < 3:
                    print(f"    ⚠️  Negative cycle days ({cycle_days}) for opp: {opp.get('Name', 'N/A')[:50]}")
                    print(f"       Created: {created.date()}, Closed: {close.date()}")
                    debug_count += 1
        except Exception as e:
            # Debug: print the error for first few failures to help diagnose
            if debug_count < 3:
                print(f"    ⚠️  Sales cycle calculation error: {e}")
                print(f"       Opp: {opp.get('Name', 'N/A')[:50]}")
                print(f"       CreatedDate: {opp.get('CreatedDate', '')}, Type: {type(opp.get('CreatedDate', ''))}")
                print(f"       CloseDate: {opp.get('CloseDate', '')}, Type: {type(opp.get('CloseDate', ''))}")
                debug_count += 1
            continue
    
    if len(cycles) == 0 and len(closed_opps) > 0:
        print(f"    ⚠️  WARNING: No valid sales cycles calculated from {len(closed_opps)} closed opportunities")
        # Show sample of what we're getting
        if closed_opps:
            sample = closed_opps[0]
            print(f"    Sample CreatedDate: {sample.get('CreatedDate')} (type: {type(sample.get('CreatedDate'))})")
            print(f"    Sample CloseDate: {sample.get('CloseDate')} (type: {type(sample.get('CloseDate'))})")
    
    avg_cycle = sum(cycles) / len(cycles) if cycles else 0
    median_cycle = sorted(cycles)[len(cycles)//2] if cycles else 0
    
    # Analyze Reason for Loss (auto close reason)
    # Using Reason_for_Closed_Lost__c field
    loss_reasons = defaultdict(int)
    win_reasons = defaultdict(int)  # Keep empty - no Reason for Win field exists
    
    for opp in lost_opps:
        # Use Reason_for_Closed_Lost__c for auto close reason
        reason = opp.get('Reason_for_Closed_Lost__c') or None
        if reason:
            loss_reasons[str(reason)] += 1
    
    return {
        'group_name': group_name,
        'total_opportunities': len(opps),
        'closed_opportunities': total_closed,
        'won_opportunities': total_won,
        'lost_opportunities': total_lost,
        'win_rate': round(win_rate, 1),
        'total_value': total_value,
        'closed_value': closed_value,
        'won_value': won_value,
        'lost_value': lost_value,
        'avg_sales_cycle_days': round(avg_cycle, 1),
        'median_sales_cycle_days': round(median_cycle, 1),
        'sales_cycles': cycles,
        'loss_reasons': dict(loss_reasons),
        'win_reasons': dict(win_reasons),
        'opportunities': opps,
        'closed_opportunities_list': closed_opps,
        'won_opportunities_list': won_opps,
        'lost_opportunities_list': lost_opps
    }

# ==========================================================
# HTML DASHBOARD GENERATION
# ==========================================================
def format_currency(value):
    """Format currency value"""
    if value >= 1000000:
        return f"${value/1000000:.2f}M"
    elif value >= 1000:
        return f"${value/1000:.0f}K"
    else:
        return f"${value:,.2f}"

def format_date(date_str):
    """Format date string"""
    try:
        if isinstance(date_str, str):
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        return str(date_str)
    except:
        return str(date_str)

def generate_html_dashboard(without_alerts, with_alerts):
    """Generate HTML dashboard comparing opportunities with and without alerts - matching exact Ghost Pipeline styling"""
    
    # Calculate comparison metrics
    velocity_diff = without_alerts['avg_sales_cycle_days'] - with_alerts['avg_sales_cycle_days']
    win_rate_diff = without_alerts['win_rate'] - with_alerts['win_rate']
    
    # Validate against Salesforce report (should total 563 closed opportunities)
    total_closed = without_alerts['closed_opportunities'] + with_alerts['closed_opportunities']
    expected_total = 563
    validation_passed = total_closed == expected_total
    
    # Get Salesforce instance URL for links
    sf_instance_base = 'https://innovativesolutions.lightning.force.com'
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ghost Pipeline Comparison - With vs Without Alerts</title>
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
        
        .kicker {{
            letter-spacing: .22em;
            text-transform: uppercase;
            color: var(--muted);
            font-weight: 700;
            font-size: 12px;
        }}
        
        .title {{
            font-size: 28px;
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
        
        .comparison-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
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
        
        .comparison-box {{
            background: linear-gradient(135deg, #f6f9ff, #f0f4ff);
            border: 2px solid var(--brand);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
        }}
        
        .comparison-box h4 {{
            color: var(--brand);
            font-size: 16px;
            font-weight: 800;
            margin-bottom: 12px;
        }}
        
        .stat-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
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
        
        .positive {{
            color: var(--success);
        }}
        
        .negative {{
            color: var(--error);
        }}
        
        .opp-list {{
            max-height: 400px;
            overflow-y: auto;
            margin-top: 12px;
        }}
        
        .opp-item {{
            padding: 12px;
            background: #fff;
            border: 1px solid var(--border);
            border-left: 4px solid var(--brand);
            border-radius: 8px;
            margin-bottom: 8px;
        }}
        
        .opp-item.won {{
            border-left-color: var(--success);
        }}
        
        .opp-item.lost {{
            border-left-color: var(--warning);
        }}
        
        .opp-name {{
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 6px;
        }}
        
        .opp-details {{
            font-size: 12px;
            color: var(--muted);
            margin-bottom: 4px;
        }}
        
        .reason {{
            font-size: 12px;
            color: var(--ink);
            font-style: italic;
            margin-top: 4px;
            padding: 6px;
            background: var(--accent);
            border-radius: 4px;
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
        
        .count-up {{
            font-variant-numeric: tabular-nums;
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
            .comparison-grid {{
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
                
                // Skip animation for currency values with M or K suffixes (they're already formatted correctly)
                if (originalText.includes('M') || originalText.includes('K')) {{
                    return; // Don't animate pre-formatted values
                }}
                
                // Extract numbers from text
                let match = originalText.match(/[\\$]?([\\d,]+\.?\\d*)/);
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
        <div class="wrap">
            <div class="kicker">Sales Ops • Ghost Pipeline Analysis</div>
            <div class="title">Ghost Pipeline Comparison</div>
            <div class="subtitle">Last 90 Days: Opportunities WITH vs WITHOUT Alerts - Win Rate, Sales Cycle Velocity, and Reason Analysis</div>
        </div>
    </div>
    
    <div class="wrap">
        <!-- Key Comparison -->
        <div class="comparison-box">
            <h4>📊 Key Comparison Metrics</h4>
            <div class="stat-row">
                <span class="stat-label">Sales Cycle Velocity Difference:</span>
                <span class="stat-value {'positive' if velocity_diff > 0 else 'negative'}">
                    {abs(velocity_diff):.1f} days {'faster' if velocity_diff > 0 else 'slower'} with alerts
                </span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Win Rate Difference:</span>
                <span class="stat-value {'positive' if win_rate_diff < 0 else 'negative'}">
                    {abs(win_rate_diff):.1f}% {'higher' if win_rate_diff < 0 else 'lower'} with alerts
                </span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Closed Opportunities:</span>
                <span class="stat-value">
                    {without_alerts['closed_opportunities']} (no alerts) vs {with_alerts['closed_opportunities']} (with alerts)
                </span>
            </div>
            <div class="stat-row" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line);">
                <span class="stat-label">✅ Validation (vs SF Report):</span>
                <span class="stat-value" style="color: {'var(--success)' if validation_passed else 'var(--warning)'};">
                    Total: {total_closed} / Expected: {expected_total} {'✅ Match' if validation_passed else '⚠️ Mismatch'}
                </span>
            </div>
        </div>
        
        <!-- Side-by-Side Comparison -->
        <div class="comparison-grid">
            <!-- Without Alerts -->
            <div class="panel">
                <div class="metric-section">
                    <h3>❌ Opportunities WITHOUT Alerts (Last 90 Days)</h3>
                    <div class="metric-grid">
                        <div class="metric-box">
                            <div class="metric-label">Total Opportunities</div>
                            <div class="metric-value">{without_alerts['total_opportunities']}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Closed</div>
                            <div class="metric-value">{without_alerts['closed_opportunities']}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Win Rate</div>
                            <div class="metric-value">{without_alerts['win_rate']}%</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Avg Sales Cycle</div>
                            <div class="metric-value">{without_alerts['avg_sales_cycle_days']} days</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Total Value</div>
                            <div class="metric-value">{format_currency(without_alerts['total_value'])}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Closed Value</div>
                            <div class="metric-value">{format_currency(without_alerts['closed_value'])}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Won Value</div>
                            <div class="metric-value" style="color: var(--success);">{format_currency(without_alerts['won_value'])}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Lost Value</div>
                            <div class="metric-value" style="color: var(--warning);">{format_currency(without_alerts['lost_value'])}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- With Alerts -->
            <div class="panel">
                <div class="metric-section">
                    <h3>✅ Opportunities WITH Alerts (Last 90 Days)</h3>
                    <div class="metric-grid">
                        <div class="metric-box">
                            <div class="metric-label">Total Opportunities</div>
                            <div class="metric-value">{with_alerts['total_opportunities']}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Closed</div>
                            <div class="metric-value">{with_alerts['closed_opportunities']}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Win Rate</div>
                            <div class="metric-value">{with_alerts['win_rate']}%</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Avg Sales Cycle</div>
                            <div class="metric-value">{with_alerts['avg_sales_cycle_days']} days</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Total Value</div>
                            <div class="metric-value">{format_currency(with_alerts['total_value'])}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Closed Value</div>
                            <div class="metric-value">{format_currency(with_alerts['closed_value'])}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Won Value</div>
                            <div class="metric-value" style="color: var(--success);">{format_currency(with_alerts['won_value'])}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Lost Value</div>
                            <div class="metric-value" style="color: var(--warning);">{format_currency(with_alerts['lost_value'])}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Reason for Closed Lost (Auto Close Reason) -->
        <div class="panel">
            <div class="metric-section">
                <h3>❌ Reason for Closed Lost (Auto Close Reason)</h3>
                <div class="comparison-grid">
                    <div>
                        <h4 style="font-size: 13px; margin-bottom: 8px; color: var(--muted);">Without Alerts</h4>
                        <div style="max-height: 300px; overflow-y: auto;">
"""
    
    # Add loss reasons for without alerts
    if without_alerts['loss_reasons']:
        for reason, count in sorted(without_alerts['loss_reasons'].items(), key=lambda x: x[1], reverse=True):
            html += f"""
                            <div class="stat-row">
                                <span class="stat-label">{reason}</span>
                                <span class="stat-value">{count}</span>
                            </div>"""
    else:
        html += '<div class="stat-row"><span class="stat-label">No loss reasons recorded</span></div>'
    
    html += """
                        </div>
                    </div>
                    <div>
                        <h4 style="font-size: 13px; margin-bottom: 8px; color: var(--muted);">With Alerts</h4>
                        <div style="max-height: 300px; overflow-y: auto;">
"""
    
    # Add loss reasons for with alerts
    if with_alerts['loss_reasons']:
        for reason, count in sorted(with_alerts['loss_reasons'].items(), key=lambda x: x[1], reverse=True):
            html += f"""
                            <div class="stat-row">
                                <span class="stat-label">{reason}</span>
                                <span class="stat-value">{count}</span>
                            </div>"""
    else:
        html += '<div class="stat-row"><span class="stat-label">No loss reasons recorded</span></div>'
    
    html += """
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Closed Opportunities Details -->
        <div class="panel">
            <div class="metric-section">
                <h3>📋 Closed Opportunities Details</h3>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; cursor: pointer;" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'; this.querySelector('.toggle-icon').textContent = this.nextElementSibling.style.display === 'none' ? '▶' : '▼';">
                    <h4 style="color: var(--ink); margin: 0; font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em;">❌ Without Alerts - Closed Opportunities ({without_alerts['closed_opportunities']} total)</h4>
                    <span class="toggle-icon" style="font-size: 12px; color: var(--muted);">▼</span>
                </div>
                <div class="opp-list" style="display: block;">
"""
    
    # Add closed opportunities without alerts - using exact Ghost Pipeline styling
    for idx, opp in enumerate(without_alerts['closed_opportunities_list'][:50], 1):  # Limit to 50 for performance
        is_won = opp.get('IsWon', False)
        border_color = '#30d158' if is_won else '#ff9500'
        status_text = '✅ WON' if is_won else '❌ Lost'
        status_color = '#30d158' if is_won else '#ff9500'
        value = float(opp.get('Professional_Services_Amount__c') or opp.get('Amount', 0))
        account_name = opp.get('Account', {}).get('Name', 'N/A') if isinstance(opp.get('Account'), dict) else (opp.get('AccountName', 'N/A') if opp.get('AccountName') else 'N/A')
        stage = opp.get('StageName', 'N/A')
        close_date = format_date(opp.get('CloseDate', ''))
        opp_id = opp.get('Id', '')
        # Get Reason for Closed Lost (auto close reason) - only for lost opportunities
        reason = opp.get('Reason_for_Closed_Lost__c') if not is_won else None
        
        html += f"""
                        <div style="margin-bottom: 12px; padding: 12px; background: #fff; border: 1px solid var(--border); border-left: 4px solid {border_color}; border-radius: 10px; transition: transform .2s, box-shadow .2s;" onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,.10)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                                <div style="flex: 1;">
                                    <div style="font-weight: 700; font-size: 14px; color: var(--ink); margin-bottom: 6px;">
                                        {idx}. {opp.get('Name', 'N/A')}
                                    </div>
                                    <div style="font-size: 13px; color: var(--muted); margin-bottom: 4px;">
                                        <span style="font-weight: 600;">Account:</span> {account_name} | 
                                        <span style="font-weight: 600;">Stage:</span> {stage} | 
                                        <span style="color: {status_color}; font-weight: 700;">{status_text}</span>
                                    </div>
                                    <div style="font-size: 13px; color: var(--muted);">
                                        <span style="font-weight: 600;">Value:</span> <span style="font-variant-numeric: tabular-nums;">${value:,.2f}</span> | 
                                        <span style="font-weight: 600;">Closed:</span> {close_date}
"""
        if reason:
            html += f""" | 
                                        <span style="font-weight: 600;">Reason for Closed Lost:</span> {reason}"""
        html += f"""
                                    </div>
"""
        if opp_id:
            html += f"""                                </div>

                                <a href="{sf_instance_base}/lightning/r/Opportunity/{opp_id}/view" target="_blank" style="background: var(--brand); color: white; padding: 8px 14px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: 700; white-space: nowrap; margin-left: 10px; display: inline-block; transition: transform .2s, box-shadow .2s;" onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,.15)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
                                    🔗 View in Salesforce
                                </a>
"""
        else:
            html += """                                </div>
"""
        html += """
                            </div>
                        </div>"""
    
    html += f"""
                </div>
                
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px; margin-bottom: 15px; cursor: pointer;" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'; this.querySelector('.toggle-icon').textContent = this.nextElementSibling.style.display === 'none' ? '▶' : '▼';">
                    <h4 style="color: var(--ink); margin: 0; font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em;">✅ With Alerts - Closed Opportunities ({with_alerts['closed_opportunities']} total)</h4>
                    <span class="toggle-icon" style="font-size: 12px; color: var(--muted);">▼</span>
                </div>
                <div class="opp-list" style="display: block;">
"""
    
    # Add closed opportunities with alerts - using exact Ghost Pipeline styling
    for idx, opp in enumerate(with_alerts['closed_opportunities_list'][:50], 1):  # Limit to 50 for performance
        is_won = opp.get('IsWon', False)
        border_color = '#30d158' if is_won else '#ff9500'
        status_text = '✅ WON' if is_won else '❌ Lost'
        status_color = '#30d158' if is_won else '#ff9500'
        value = float(opp.get('Professional_Services_Amount__c') or opp.get('Amount', 0))
        account_name = opp.get('Account', {}).get('Name', 'N/A') if isinstance(opp.get('Account'), dict) else (opp.get('AccountName', 'N/A') if opp.get('AccountName') else 'N/A')
        stage = opp.get('StageName', 'N/A')
        alert_date = format_date(opp.get('Ghost_Pipeline_Alert_Sent_Date__c', ''))
        close_date = format_date(opp.get('CloseDate', ''))
        opp_id = opp.get('Id', '')
        # Get Reason for Closed Lost (auto close reason) - only for lost opportunities
        reason = opp.get('Reason_for_Closed_Lost__c') if not is_won else None
        
        html += f"""
                        <div style="margin-bottom: 12px; padding: 12px; background: #fff; border: 1px solid var(--border); border-left: 4px solid {border_color}; border-radius: 10px; transition: transform .2s, box-shadow .2s;" onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,.10)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                                <div style="flex: 1;">
                                    <div style="font-weight: 700; font-size: 14px; color: var(--ink); margin-bottom: 6px;">
                                        {idx}. {opp.get('Name', 'N/A')}
                                    </div>
                                    <div style="font-size: 13px; color: var(--muted); margin-bottom: 4px;">
                                        <span style="font-weight: 600;">Account:</span> {account_name} | 
                                        <span style="font-weight: 600;">Stage:</span> {stage} | 
                                        <span style="color: {status_color}; font-weight: 700;">{status_text}</span>
                                    </div>
                                    <div style="font-size: 13px; color: var(--muted);">
                                        <span style="font-weight: 600;">Value:</span> <span style="font-variant-numeric: tabular-nums;">${value:,.2f}</span> | 
                                        <span style="font-weight: 600;">📅 Alert Sent:</span> {alert_date} | 
                                        <span style="font-weight: 600;">Closed:</span> {close_date}
"""
        if reason:
            html += f""" | 
                                        <span style="font-weight: 600;">Reason for Closed Lost:</span> {reason}"""
        html += f"""
                                    </div>
"""
        if opp_id:
            html += f"""                                </div>

                                <a href="{sf_instance_base}/lightning/r/Opportunity/{opp_id}/view" target="_blank" style="background: var(--brand); color: white; padding: 8px 14px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: 700; white-space: nowrap; margin-left: 10px; display: inline-block; transition: transform .2s, box-shadow .2s;" onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,.15)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
                                    🔗 View in Salesforce
                                </a>
"""
        else:
            html += """                                </div>
"""
        html += """
                            </div>
                        </div>"""
    
    html += f"""
                </div>
            </div>
        </div>
        
        <div class="foot">
            <div class="note">Report generated automatically • Refresh page to update metrics</div>
            <div class="brandmark">INNOVATIVE • FLOW METRICS</div>
        </div>
    </div>
</body>
</html>"""
    
    return html

# ==========================================================
# MAIN EXECUTION
# ==========================================================
def main():
    """Main execution function"""
    print("=" * 80)
    print("GHOST PIPELINE COMPARISON - WITH vs WITHOUT ALERTS")
    print("=" * 80)
    print(f"Executed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Analysis Period: Last {LOOKBACK_DAYS} days")
    print()
    
    # Authenticate with Salesforce
    print("🔐 Authenticating with Salesforce via JWT...")
    token, instance_url = get_salesforce_token()
    if not token:
        print("❌ Authentication failed")
        return
    
    print("✅ Connected successfully")
    print()
    
    # Get opportunities
    without_alerts_opps = get_opportunities_without_alerts(token, instance_url)
    with_alerts_opps = get_opportunities_with_alerts(token, instance_url)
    
    # Analyze both groups
    print("\n" + "=" * 80)
    print("ANALYZING OPPORTUNITIES")
    print("=" * 80)
    
    without_alerts_analysis = analyze_opportunities(without_alerts_opps, "Opportunities WITHOUT Alerts")
    with_alerts_analysis = analyze_opportunities(with_alerts_opps, "Opportunities WITH Alerts")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n📊 OPPORTUNITIES WITHOUT ALERTS:")
    print(f"   Total: {without_alerts_analysis['total_opportunities']}")
    print(f"   Closed: {without_alerts_analysis['closed_opportunities']}")
    print(f"   Win Rate: {without_alerts_analysis['win_rate']}%")
    print(f"   Avg Sales Cycle: {without_alerts_analysis['avg_sales_cycle_days']} days")
    print(f"   Total Value: {format_currency(without_alerts_analysis['total_value'])}")
    print(f"   Closed Value: {format_currency(without_alerts_analysis['closed_value'])}")
    
    print(f"\n📊 OPPORTUNITIES WITH ALERTS:")
    print(f"   Total: {with_alerts_analysis['total_opportunities']}")
    print(f"   Closed: {with_alerts_analysis['closed_opportunities']}")
    print(f"   Win Rate: {with_alerts_analysis['win_rate']}%")
    print(f"   Avg Sales Cycle: {with_alerts_analysis['avg_sales_cycle_days']} days")
    print(f"   Total Value: {format_currency(with_alerts_analysis['total_value'])}")
    print(f"   Closed Value: {format_currency(with_alerts_analysis['closed_value'])}")
    
    # Calculate comparison
    velocity_diff = without_alerts_analysis['avg_sales_cycle_days'] - with_alerts_analysis['avg_sales_cycle_days']
    win_rate_diff = without_alerts_analysis['win_rate'] - with_alerts_analysis['win_rate']
    
    # Validate against Salesforce report (should total 563 closed opportunities)
    total_closed = without_alerts_analysis['closed_opportunities'] + with_alerts_analysis['closed_opportunities']
    expected_total = 563
    
    print(f"\n📈 COMPARISON:")
    print(f"   Sales Cycle Difference: {abs(velocity_diff):.1f} days {'faster' if velocity_diff > 0 else 'slower'} with alerts")
    print(f"   Win Rate Difference: {abs(win_rate_diff):.1f}% {'higher' if win_rate_diff < 0 else 'lower'} with alerts")
    
    print(f"\n✅ VALIDATION (vs Salesforce Report):")
    print(f"   Closed Opportunities WITHOUT alerts: {without_alerts_analysis['closed_opportunities']}")
    print(f"   Closed Opportunities WITH alerts: {with_alerts_analysis['closed_opportunities']}")
    print(f"   Total Closed Opportunities: {total_closed}")
    print(f"   Expected Total (from SF Report): {expected_total}")
    if total_closed == expected_total:
        print(f"   ✅ VALIDATION PASSED: Total matches Salesforce report!")
    else:
        print(f"   ⚠️  VALIDATION WARNING: Total ({total_closed}) does not match expected ({expected_total})")
        print(f"      Difference: {abs(total_closed - expected_total)} opportunities")
    
    # Save data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_file = OUTPUT_DIR / f"ghost_pipeline_comparison_{timestamp}.json"
    
    comparison_data = {
        'timestamp': datetime.now().isoformat(),
        'analysis_period_days': LOOKBACK_DAYS,
        'without_alerts': without_alerts_analysis,
        'with_alerts': with_alerts_analysis,
        'comparison': {
            'velocity_difference_days': velocity_diff,
            'win_rate_difference_percent': win_rate_diff,
            'velocity_with_alerts_faster_days': abs(velocity_diff) if velocity_diff > 0 else 0,
            'win_rate_with_alerts_higher_percent': abs(win_rate_diff) if win_rate_diff < 0 else 0
        },
        'validation': {
            'total_closed_opportunities': total_closed,
            'expected_total_from_sf_report': expected_total,
            'validation_passed': total_closed == expected_total,
            'difference': abs(total_closed - expected_total)
        }
    }
    
    with open(data_file, 'w') as f:
        json.dump(comparison_data, f, indent=2, default=str)
    
    print(f"\n✅ Data saved: {data_file}")
    
    # Generate HTML dashboard
    print("\n📄 Generating HTML Dashboard...")
    html_content = generate_html_dashboard(without_alerts_analysis, with_alerts_analysis)
    
    html_file = OUTPUT_DIR / f"ghost_pipeline_comparison_{timestamp}.html"
    with open(html_file, 'w') as f:
        f.write(html_content)
    
    print(f"✅ HTML Dashboard: {html_file}")
    
    # Also create a _latest.html file for GitHub Pages
    latest_html_file = OUTPUT_DIR / "ghost_pipeline_comparison_latest.html"
    with open(latest_html_file, 'w') as f:
        f.write(html_content)
    
    print(f"✅ Latest HTML Dashboard: {latest_html_file}")
    print()
    print("=" * 80)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\n🌐 To view dashboard: open {html_file}")

if __name__ == "__main__":
    main()

