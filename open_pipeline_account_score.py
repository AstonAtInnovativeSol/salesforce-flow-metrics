#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open Pipeline Account Score Analysis
Built with world-class architecture patterns from Innovative Solutions

Purpose:
- Analyze 2-year Closed Won historical data (Jan 2024 - present)
- Build predictive scoring models for Opportunity Score and Account Score
- Apply scores to open pipeline opportunities
- Generate HTML output (NO Salesforce fields - analysis only until stakeholder feedback)

Methodology:
- Speed to Close: Historical average days to close
- Largest Deal Size: Maximum deal value per account
- Product Mix: Diversity of products/services purchased
- Upsell Instances: Accounts with multiple purchases
- Win Rate: Historical win rate per account
- Recency Weighting: More recent wins weighted higher

Run with: python open_pipeline_account_score.py
"""

import os
import sys
import time
import jwt
import requests
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import json
import statistics

# =========================
# SALESFORCE CONFIG
# =========================
# Add "Live and migrated to GitHub" folder to path to find sf_config
github_folder = Path(__file__).parent / "Live and migrated to GitHub"
if github_folder.exists():
    sys.path.insert(0, str(github_folder))

# Try to import sf_config module, fall back to environment variables
try:
    import sf_config
    SF_USERNAME = sf_config.SF_USERNAME
    SF_CONSUMER_KEY = sf_config.SF_CONSUMER_KEY
    SF_DOMAIN = sf_config.SF_DOMAIN
    PRIVATE_KEY_FILE = Path(sf_config.PRIVATE_KEY_FILE)
except ImportError:
    # Fall back to environment variables
    SF_USERNAME = os.getenv("SF_USERNAME")
    SF_CONSUMER_KEY = os.getenv("SF_CONSUMER_KEY")
    SF_DOMAIN = os.getenv("SF_DOMAIN", "login")
    private_key_path = os.getenv("PRIVATE_KEY_FILE")
    if private_key_path:
        PRIVATE_KEY_FILE = Path(private_key_path)
    else:
        # Default location
        PRIVATE_KEY_FILE = Path.home() / ".sf" / "private_key.pem"
    
    # Validate required config
    if not SF_USERNAME or not SF_CONSUMER_KEY:
        raise ValueError(
            "Missing Salesforce configuration. Either:\n"
            "1. Create sf_config.py with SF_USERNAME, SF_CONSUMER_KEY, SF_DOMAIN, PRIVATE_KEY_FILE, OR\n"
            "2. Set environment variables: SF_USERNAME, SF_CONSUMER_KEY, SF_DOMAIN, PRIVATE_KEY_FILE"
        )
    
    if not PRIVATE_KEY_FILE.exists():
        raise FileNotFoundError(
            f"Private key file not found: {PRIVATE_KEY_FILE}\n"
            "Please set PRIVATE_KEY_FILE environment variable or create sf_config.py"
        )

def get_jwt_token():
    """Generate JWT token for Salesforce authentication"""
    with open(PRIVATE_KEY_FILE, "r") as f:
        private_key = f.read()
    
    claim = {
        "iss": SF_CONSUMER_KEY,
        "sub": SF_USERNAME,
        "aud": f"https://{SF_DOMAIN}.salesforce.com",
        "exp": int(time.time()) + 300,
    }
    
    assertion = jwt.encode(claim, private_key, algorithm="RS256")
    token_url = f"https://{SF_DOMAIN}.salesforce.com/services/oauth2/token"
    resp = requests.post(token_url, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    })
    resp.raise_for_status()
    return resp.json()

def api_base(token, version="v61.0"):
    return f"{token['instance_url']}/services/data/{version}"

def sf_headers(token):
    return {"Authorization": f"Bearer {token['access_token']}", "Content-Type": "application/json"}

def soql_query(token, soql):
    """Execute SOQL query with pagination"""
    url = f"{api_base(token)}/query"
    out = []
    r = requests.get(url, headers=sf_headers(token), params={"q": soql})
    if r.status_code != 200:
        error_msg = r.text
        try:
            error_json = r.json()
            if isinstance(error_json, list) and len(error_json) > 0:
                error_msg = error_json[0].get("message", error_msg)
            elif isinstance(error_json, dict):
                error_msg = error_json.get("message", error_msg)
        except:
            pass
        print(f"\n[ERROR] SOQL Query failed:")
        print(f"Query: {soql[:200]}...")
        print(f"Error: {error_msg}")
        r.raise_for_status()
    data = r.json()
    out.extend(data.get("records", []))
    while not data.get("done", True) and data.get("nextRecordsUrl"):
        r = requests.get(token["instance_url"] + data["nextRecordsUrl"], headers=sf_headers(token))
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("records", []))
    return out

# =========================
# DATA MODELS
# =========================

@dataclass
class AccountScoringProfile:
    """Historical scoring profile for an account"""
    account_id: str
    account_name: str
    # Historical metrics
    total_closed_won: int = 0
    total_closed_lost: int = 0
    win_rate: float = 0.0
    avg_days_to_close: float = 0.0
    median_days_to_close: float = 0.0
    largest_deal_amount: float = 0.0
    avg_deal_amount: float = 0.0
    total_deal_amount: float = 0.0
    # Product mix analysis
    unique_products: set = field(default_factory=set)
    product_count: int = 0
    # Upsell analysis
    purchase_count: int = 0
    has_upsell: bool = False
    # Recency weighting
    most_recent_close_date: Optional[date] = None
    days_since_last_close: Optional[int] = None
    # Opportunity details
    closed_opportunities: List[Dict] = field(default_factory=list)
    
    def calculate_win_rate(self):
        """Calculate win rate from closed won vs closed lost"""
        total = self.total_closed_won + self.total_closed_lost
        if total > 0:
            self.win_rate = (self.total_closed_won / total) * 100
        return self.win_rate
    
    def calculate_product_diversity_score(self):
        """Score based on product mix diversity (0-100)"""
        if self.product_count == 0:
            return 0
        # More unique products = higher score (capped at 100)
        diversity = min(self.product_count * 20, 100)
        return diversity
    
    def calculate_upsell_score(self):
        """Score based on upsell history (0-100)"""
        if self.purchase_count >= 3:
            return 100  # Multiple purchases = high upsell potential
        elif self.purchase_count == 2:
            return 70   # Two purchases = medium upsell potential
        elif self.purchase_count == 1:
            return 30   # Single purchase = low upsell potential
        return 0

@dataclass
class OpportunityScore:
    """Calculated score for an open opportunity"""
    opportunity_id: str
    opportunity_name: str
    account_id: str
    account_name: str
    amount: float
    stage: str
    close_date: date
    owner_name: str
    commit: Optional[str] = None
    # Scores (0-100)
    account_score: float = 0.0
    opportunity_score: float = 0.0
    # Component scores
    speed_score: float = 0.0
    deal_size_score: float = 0.0
    product_mix_score: float = 0.0
    upsell_score: float = 0.0
    win_rate_score: float = 0.0
    recency_score: float = 0.0
    # Confidence
    confidence_level: str = "Medium"  # High, Medium, Low
    # Explanation
    score_explanation: str = ""

# =========================
# DATA COLLECTION
# =========================

def query_closed_won_opportunities(token, start_date: date = date(2024, 1, 1)) -> List[Dict]:
    """
    Query all Closed Won opportunities from start_date to present.
    Includes account details, product info, and dates for scoring.
    """
    # Use date literal format: YYYY-MM-DD
    start_str = start_date.strftime("%Y-%m-%d")
    
    soql = f"""
        SELECT 
            Id,
            Name,
            Account.Id,
            Account.Name,
            Account.Industry,
            Account.Type,
            Professional_Services_Amount__c,
            StageName,
            CloseDate,
            CreatedDate,
            Owner.Name,
            Owner.IsActive,
            IsWon,
            IsClosed,
            (SELECT Id, Product2.Name, Product2.Family, Quantity, UnitPrice, TotalPrice
             FROM OpportunityLineItems
             LIMIT 200)
        FROM Opportunity
        WHERE IsWon = TRUE
            AND IsClosed = TRUE
            AND CloseDate >= {start_str}
            AND Professional_Services_Amount__c != NULL
            AND Professional_Services_Amount__c > 0
        ORDER BY CloseDate DESC
    """
    
    print(f"\n[INFO] Querying Closed Won opportunities from {start_str} to present...")
    opportunities = soql_query(token, soql)
    print(f"[INFO] Found {len(opportunities)} Closed Won opportunities")
    
    return opportunities

def query_closed_lost_opportunities(token, start_date: date = date(2024, 1, 1)) -> List[Dict]:
    """
    Query Closed Lost opportunities for win rate calculation.
    """
    start_str = start_date.strftime("%Y-%m-%d")
    
    soql = f"""
        SELECT 
            Id,
            Account.Id,
            Account.Name,
            StageName,
            CloseDate,
            IsWon,
            IsClosed
        FROM Opportunity
        WHERE IsWon = FALSE
            AND IsClosed = TRUE
            AND StageName = 'Closed Lost'
            AND CloseDate >= {start_str}
        ORDER BY CloseDate DESC
    """
    
    print(f"[INFO] Querying Closed Lost opportunities from {start_str} to present...")
    opportunities = soql_query(token, soql)
    print(f"[INFO] Found {len(opportunities)} Closed Lost opportunities")
    
    return opportunities

def query_open_pipeline_opportunities(token) -> List[Dict]:
    """
    Query all open pipeline opportunities to score.
    """
    soql = f"""
        SELECT 
            Id,
            Name,
            Account.Id,
            Account.Name,
            Account.Industry,
            Account.Type,
            Professional_Services_Amount__c,
            StageName,
            Sales_Commit__c,
            CloseDate,
            CreatedDate,
            Owner.Name,
            Owner.IsActive,
            (SELECT Id, Product2.Name, Product2.Family, Quantity, UnitPrice, TotalPrice
             FROM OpportunityLineItems
             LIMIT 200)
        FROM Opportunity
        WHERE IsClosed = FALSE
            AND StageName NOT IN ('Closed Won', 'Closed Lost', 'Disqualified')
            AND Professional_Services_Amount__c != NULL
            AND Professional_Services_Amount__c > 0
        ORDER BY Professional_Services_Amount__c DESC NULLS LAST
    """
    
    print(f"\n[INFO] Querying open pipeline opportunities...")
    opportunities = soql_query(token, soql)
    print(f"[INFO] Found {len(opportunities)} open pipeline opportunities")
    
    return opportunities

# =========================
# SCORING LOGIC
# =========================

def build_account_profiles(closed_won: List[Dict], closed_lost: List[Dict]) -> Dict[str, AccountScoringProfile]:
    """
    Build historical scoring profiles for each account.
    Analyzes speed to close, deal sizes, product mix, and upsell patterns.
    """
    profiles: Dict[str, AccountScoringProfile] = {}
    
    # Process Closed Won opportunities
    for opp in closed_won:
        account_id = (opp.get("Account") or {}).get("Id")
        account_name = (opp.get("Account") or {}).get("Name", "Unknown")
        
        if not account_id:
            continue
        
        if account_id not in profiles:
            profiles[account_id] = AccountScoringProfile(
                account_id=account_id,
                account_name=account_name
            )
        
        profile = profiles[account_id]
        
        # Parse dates
        close_date_str = opp.get("CloseDate")
        created_date_str = opp.get("CreatedDate")
        
        if close_date_str and created_date_str:
            try:
                close_date = datetime.strptime(close_date_str[:10], "%Y-%m-%d").date()
                created_date = datetime.strptime(created_date_str[:10], "%Y-%m-%d").date()
                days_to_close = (close_date - created_date).days
                
                if days_to_close > 0:
                    profile.closed_opportunities.append({
                        "days_to_close": days_to_close,
                        "amount": float(opp.get("Professional_Services_Amount__c") or 0),
                        "close_date": close_date
                    })
            except:
                pass
        
        # Deal amount - ONLY use Professional_Services_Amount__c
        amount = float(opp.get("Professional_Services_Amount__c") or 0)
        profile.total_closed_won += 1
        profile.total_deal_amount += amount
        
        if amount > profile.largest_deal_amount:
            profile.largest_deal_amount = amount
        
        # Product mix
        line_items_data = opp.get("OpportunityLineItems")
        if line_items_data:
            line_items = line_items_data.get("records", []) if isinstance(line_items_data, dict) else []
            for item in line_items:
                product_name = (item.get("Product2") or {}).get("Name")
                if product_name:
                    profile.unique_products.add(product_name)
        
        # Track most recent close
        if close_date_str:
            try:
                close_date = datetime.strptime(close_date_str[:10], "%Y-%m-%d").date()
                if profile.most_recent_close_date is None or close_date > profile.most_recent_close_date:
                    profile.most_recent_close_date = close_date
            except:
                pass
    
    # Process Closed Lost opportunities
    for opp in closed_lost:
        account_id = (opp.get("Account") or {}).get("Id")
        if account_id and account_id in profiles:
            profiles[account_id].total_closed_lost += 1
    
    # Calculate aggregated metrics
    today = date.today()
    for profile in profiles.values():
        # Win rate
        profile.calculate_win_rate()
        
        # Days to close metrics
        if profile.closed_opportunities:
            days_list = [o["days_to_close"] for o in profile.closed_opportunities]
            profile.avg_days_to_close = statistics.mean(days_list)
            profile.median_days_to_close = statistics.median(days_list)
            profile.avg_deal_amount = profile.total_deal_amount / profile.total_closed_won
            profile.purchase_count = profile.total_closed_won
            profile.product_count = len(profile.unique_products)
            profile.has_upsell = profile.purchase_count > 1
        
        # Recency
        if profile.most_recent_close_date:
            profile.days_since_last_close = (today - profile.most_recent_close_date).days
    
    print(f"\n[INFO] Built scoring profiles for {len(profiles)} accounts")
    print(f"[INFO] Accounts with multiple purchases (upsell): {sum(1 for p in profiles.values() if p.has_upsell)}")
    
    return profiles

def calculate_normalized_scores(profiles: Dict[str, AccountScoringProfile]) -> Dict[str, Tuple[float, float, float, float, float]]:
    """
    Calculate normalized scoring ranges (0-100) for each metric.
    Returns: {metric_name: (min, max, median, mean, std_dev)}
    """
    # Collect all values
    win_rates = [p.win_rate for p in profiles.values() if p.total_closed_won > 0]
    days_to_close = [p.avg_days_to_close for p in profiles.values() if p.avg_days_to_close > 0]
    largest_deals = [p.largest_deal_amount for p in profiles.values() if p.largest_deal_amount > 0]
    product_counts = [p.product_count for p in profiles.values()]
    
    stats = {
        "win_rate": (
            min(win_rates) if win_rates else 0,
            max(win_rates) if win_rates else 100,
            statistics.median(win_rates) if win_rates else 50,
            statistics.mean(win_rates) if win_rates else 50,
            statistics.stdev(win_rates) if len(win_rates) > 1 else 0
        ),
        "days_to_close": (
            min(days_to_close) if days_to_close else 0,
            max(days_to_close) if days_to_close else 365,
            statistics.median(days_to_close) if days_to_close else 90,
            statistics.mean(days_to_close) if days_to_close else 90,
            statistics.stdev(days_to_close) if len(days_to_close) > 1 else 0
        ),
        "largest_deal": (
            min(largest_deals) if largest_deals else 0,
            max(largest_deals) if largest_deals else 1000000,
            statistics.median(largest_deals) if largest_deals else 50000,
            statistics.mean(largest_deals) if largest_deals else 50000,
            statistics.stdev(largest_deals) if len(largest_deals) > 1 else 0
        ),
        "product_count": (
            min(product_counts) if product_counts else 0,
            max(product_counts) if product_counts else 10,
            statistics.median(product_counts) if product_counts else 1,
            statistics.mean(product_counts) if product_counts else 1,
            statistics.stdev(product_counts) if len(product_counts) > 1 else 0
        )
    }
    
    return stats

def score_open_opportunities(
    open_opps: List[Dict],
    profiles: Dict[str, AccountScoringProfile],
    stats: Dict[str, Tuple[float, float, float, float, float]]
) -> List[OpportunityScore]:
    """
    Score each open opportunity based on account historical profile.
    """
    scored_opps = []
    
    for opp in open_opps:
        account_id = (opp.get("Account") or {}).get("Id")
        account_name = (opp.get("Account") or {}).get("Name", "Unknown")
        
        if not account_id:
            continue
        
        score = OpportunityScore(
            opportunity_id=opp.get("Id", ""),
            opportunity_name=opp.get("Name", "Unknown"),
            account_id=account_id,
            account_name=account_name,
            amount=float(opp.get("Professional_Services_Amount__c") or 0),
            stage=opp.get("StageName", ""),
            commit=opp.get("Sales_Commit__c") or None,
            close_date=datetime.strptime(opp.get("CloseDate", "")[:10], "%Y-%m-%d").date() if opp.get("CloseDate") else date.today(),
            owner_name=(opp.get("Owner") or {}).get("Name", "Unknown")
        )
        
        # Get account profile
        profile = profiles.get(account_id)
        
        if profile and profile.total_closed_won > 0:
            # Account has historical data - calculate scores
            
            # 1. Speed to Close Score (0-100) - FASTER = HIGHER SCORE
            if profile.avg_days_to_close > 0:
                # Inverse relationship: faster close = higher score
                max_days = stats["days_to_close"][1] if stats["days_to_close"][1] > 0 else 365
                # Normalize: 0 days = 100, max_days = 0
                speed_normalized = max(0, 100 - (profile.avg_days_to_close / max_days) * 100)
                score.speed_score = min(100, max(0, speed_normalized))
            else:
                score.speed_score = 50  # Neutral if no data
            
            # 2. Deal Size Score (0-100) - LARGER = HIGHER SCORE
            if profile.largest_deal_amount > 0:
                max_deal = stats["largest_deal"][1] if stats["largest_deal"][1] > 0 else 1000000
                # Normalize: largest deal relative to max
                deal_normalized = (profile.largest_deal_amount / max_deal) * 100
                score.deal_size_score = min(100, max(0, deal_normalized))
            else:
                score.deal_size_score = 25  # Low score if no data
            
            # 3. Product Mix Score (0-100) - MORE PRODUCTS = HIGHER SCORE
            score.product_mix_score = profile.calculate_product_diversity_score()
            
            # 4. Upsell Score (0-100) - MORE PURCHASES = HIGHER SCORE
            score.upsell_score = profile.calculate_upsell_score()
            
            # 5. Win Rate Score (0-100) - HIGHER WIN RATE = HIGHER SCORE
            score.win_rate_score = min(100, profile.win_rate)
            
            # 6. Recency Score (0-100) - MORE RECENT = HIGHER SCORE
            if profile.days_since_last_close is not None:
                # Recent (0-90 days) = 100, older = lower
                if profile.days_since_last_close <= 90:
                    score.recency_score = 100
                elif profile.days_since_last_close <= 180:
                    score.recency_score = 75
                elif profile.days_since_last_close <= 365:
                    score.recency_score = 50
                else:
                    score.recency_score = 25
            else:
                score.recency_score = 50  # Neutral
            
            # Weighted composite scores
            # Account Score: Historical account performance
            account_weights = {
                "speed": 0.15,
                "deal_size": 0.20,
                "product_mix": 0.15,
                "upsell": 0.25,
                "win_rate": 0.20,
                "recency": 0.05
            }
            
            score.account_score = (
                score.speed_score * account_weights["speed"] +
                score.deal_size_score * account_weights["deal_size"] +
                score.product_mix_score * account_weights["product_mix"] +
                score.upsell_score * account_weights["upsell"] +
                score.win_rate_score * account_weights["win_rate"] +
                score.recency_score * account_weights["recency"]
            )
            
            # Opportunity Score: Account score + current opportunity factors
            # Current opportunity amount vs historical average
            opp_amount_score = 0
            if profile.avg_deal_amount > 0:
                opp_amount_ratio = score.amount / profile.avg_deal_amount
                if opp_amount_ratio >= 1.5:
                    opp_amount_score = 100  # Much larger than average
                elif opp_amount_ratio >= 1.0:
                    opp_amount_score = 75   # Larger than average
                elif opp_amount_ratio >= 0.75:
                    opp_amount_score = 50   # Similar to average
                else:
                    opp_amount_score = 25   # Smaller than average
            
            # Opportunity Score = Account Score (70%) + Current Opportunity (30%)
            score.opportunity_score = (score.account_score * 0.70) + (opp_amount_score * 0.30)
            
            # Confidence level
            if profile.total_closed_won >= 3:
                score.confidence_level = "High"
            elif profile.total_closed_won >= 2:
                score.confidence_level = "Medium"
            else:
                score.confidence_level = "Low"
            
            # Explanation
            score.score_explanation = f"Account has {profile.total_closed_won} closed won deal(s). "
            score.score_explanation += f"Avg {profile.avg_days_to_close:.0f} days to close. "
            score.score_explanation += f"Largest deal: ${profile.largest_deal_amount:,.0f}. "
            if profile.has_upsell:
                score.score_explanation += f"Has {profile.purchase_count} purchase(s) (upsell potential). "
        
        else:
            # New account - no historical data
            score.account_score = 50  # Neutral score
            score.opportunity_score = 50
            score.confidence_level = "Low"
            score.score_explanation = "New account - no historical data available."
        
        scored_opps.append(score)
    
    return scored_opps

# =========================
# HTML GENERATION
# =========================

def generate_html_dashboard(scored_opps: List[OpportunityScore], profiles: Dict[str, AccountScoringProfile], stats: Dict) -> str:
    """Generate HTML dashboard with scoring analysis"""
    
    # Sort by opportunity score (highest first) - already sorted, but ensure it
    scored_opps_sorted = sorted(scored_opps, key=lambda x: x.opportunity_score, reverse=True)
    
    # Summary statistics
    total_opportunities = len(scored_opps)
    high_score_count = sum(1 for s in scored_opps if s.opportunity_score >= 75)
    medium_score_count = sum(1 for s in scored_opps if 50 <= s.opportunity_score < 75)
    low_score_count = sum(1 for s in scored_opps if s.opportunity_score < 50)
    
    total_pipeline_value = sum(s.amount for s in scored_opps)
    high_score_value = sum(s.amount for s in scored_opps if s.opportunity_score >= 75)
    
    # Prepare all opportunities data for JavaScript (for Top 10/50/100 filtering)
    opportunities_json = json.dumps([
        {
            "opportunity_name": opp.opportunity_name,
            "account_name": opp.account_name,
            "amount": opp.amount,
            "stage": opp.stage,
            "commit": opp.commit or "",
            "opportunity_score": round(opp.opportunity_score, 1),
            "account_score": round(opp.account_score, 1),
            "confidence_level": opp.confidence_level,
            "score_explanation": opp.score_explanation,
            "owner_name": opp.owner_name,
            "close_date": opp.close_date.strftime("%Y-%m-%d") if opp.close_date else ""
        }
        for opp in scored_opps_sorted
    ], default=str)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Open Pipeline Account Score</title>
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
            font: 15px/1.4 -apple-system, BlinkMacSystemFont, Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        
        .wrap {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }}
        
        .hdr {{
            position: sticky;
            top: 0;
            z-index: 20;
            backdrop-filter: saturate(180%) blur(8px);
            background: linear-gradient(180deg, rgba(255,255,255,.92), rgba(255,255,255,.86));
            border-bottom: 1px solid var(--line);
            padding: 20px 24px;
            margin: -24px -24px 24px -24px;
        }}
        
        .back-btn {{
            position: absolute;
            left: 24px;
            top: 50%;
            transform: translateY(-50%);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--ink);
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s ease;
            z-index: 10;
        }}
        
        .back-btn:hover {{
            background: var(--brand);
            color: white;
            border-color: var(--brand);
            transform: translateY(-50%) translateX(-2px);
            box-shadow: 0 2px 8px rgba(75, 123, 236, 0.3);
        }}
        
        .back-btn svg {{
            width: 16px;
            height: 16px;
        }}
        
        .hdr-content {{
            display: flex;
            justify-content: flex-end;
            align-items: flex-start;
            flex-direction: column;
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
        }}
        
        .title {{
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 6px;
            color: var(--ink);
            letter-spacing: -0.01em;
            text-align: right;
        }}
        
        .subtitle {{
            color: var(--muted);
            font-size: 13px;
            line-height: 1.5;
            margin: 0;
            text-align: right;
        }}
        
        .panel {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,.05);
        }}
        
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        
        .metric-box {{
            background: #fff;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            border-left: 4px solid var(--brand);
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
        
        .score-bar {{
            width: 100%;
            height: 8px;
            background: var(--line);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }}
        
        .score-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--success), var(--brand));
            transition: width 0.3s ease;
        }}
        
        .table-container {{
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        th {{
            background: var(--accent);
            padding: 12px;
            text-align: left;
            font-weight: 700;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: .05em;
            color: var(--muted);
            border-bottom: 2px solid var(--border);
            position: sticky;
            top: 0;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid var(--line);
        }}
        
        tr:hover {{
            background: var(--accent);
        }}
        
        .score-cell {{
            font-weight: 700;
            font-variant-numeric: tabular-nums;
        }}
        
        .score-high {{ color: var(--success); }}
        .score-medium {{ color: var(--warning); }}
        .score-low {{ color: var(--error); }}
        
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        
        .badge-high {{ background: #d1fae5; color: #065f46; }}
        .badge-medium {{ background: #fef3c7; color: #92400e; }}
        .badge-low {{ background: #fee2e2; color: #991b1b; }}
        
        .methodology {{
            background: linear-gradient(135deg, #f6f9ff, #f0f4ff);
            border: 2px solid var(--brand);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        
        .methodology h3 {{
            color: var(--brand);
            font-size: 16px;
            font-weight: 800;
            margin-bottom: 12px;
        }}
        
        .methodology ul {{
            margin-left: 20px;
            color: var(--muted);
            line-height: 1.8;
        }}
        
        .filter-btn {{
            padding: 8px 16px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--bg);
            color: var(--ink);
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .filter-btn:hover {{
            background: var(--accent);
            border-color: var(--brand);
            transform: translateY(-1px);
        }}
        
        .filter-btn.active {{
            background: var(--brand);
            color: white;
            border-color: var(--brand);
            box-shadow: 0 2px 4px rgba(75, 123, 236, 0.2);
        }}
        
        .foot {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--line);
            color: var(--muted);
            font-size: 11px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="hdr">
        <a href="index.html" class="back-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back to Dashboard
        </a>
        <div class="hdr-content">
            <div class="title">Open Pipeline Account Score</div>
            <div class="subtitle">Predictive scoring based on 2-year historical Closed Won data (Jan 2024 - Present)</div>
        </div>
    </div>
    
    <div class="wrap">
        <div class="methodology">
            <h3>📊 Methodology</h3>
            <ul>
                <li><strong>Speed to Close (15%):</strong> Historical average days from creation to close (faster = higher score)</li>
                <li><strong>Largest Deal Size (20%):</strong> Maximum deal value per account (larger = higher score)</li>
                <li><strong>Product Mix (15%):</strong> Diversity of products/services purchased (more products = higher score)</li>
                <li><strong>Upsell Instances (25%):</strong> Accounts with multiple purchases (more purchases = higher score)</li>
                <li><strong>Win Rate (20%):</strong> Historical win rate percentage (higher = higher score)</li>
                <li><strong>Recency (5%):</strong> Days since last close (more recent = higher score)</li>
            </ul>
            <p style="margin-top: 12px; font-size: 12px; color: var(--muted);">
                <strong>Note:</strong> Scores are calculated in this analysis only (not in Salesforce). 
                Custom fields will be added after stakeholder review and feedback.
            </p>
        </div>
        
        <div class="panel">
            <h3 style="margin-bottom: 16px; font-size: 16px; font-weight: 800;">Summary Statistics</h3>
            <div class="metric-grid">
                <div class="metric-box">
                    <div class="metric-label">Total Opportunities</div>
                    <div class="metric-value">{total_opportunities:,}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Total Pipeline Value</div>
                    <div class="metric-value">${total_pipeline_value:,.0f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">High Score (≥75)</div>
                    <div class="metric-value">{high_score_count:,}</div>
                    <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">
                        ${sum(s.amount for s in scored_opps if s.opportunity_score >= 75):,.0f} value
                    </div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Medium Score (50-74)</div>
                    <div class="metric-value">{medium_score_count:,}</div>
                    <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">
                        ${sum(s.amount for s in scored_opps if 50 <= s.opportunity_score < 75):,.0f} value
                    </div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Low Score (<50)</div>
                    <div class="metric-value">{low_score_count:,}</div>
                    <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">
                        ${sum(s.amount for s in scored_opps if s.opportunity_score < 50):,.0f} value
                    </div>
                </div>
            </div>
        </div>
        
        <div class="panel">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3 style="margin: 0; font-size: 16px; font-weight: 800;">Opportunities by Score</h3>
                <div style="display: flex; gap: 8px;">
                    <button class="filter-btn active" data-limit="10" onclick="showTopOpportunities(10)">Top 10</button>
                    <button class="filter-btn" data-limit="50" onclick="showTopOpportunities(50)">Top 50</button>
                    <button class="filter-btn" data-limit="100" onclick="showTopOpportunities(100)">Top 100</button>
                    <button class="filter-btn" data-limit="all" onclick="showTopOpportunities(9999)">All {total_opportunities}</button>
                </div>
            </div>
            <div class="table-container">
                <table id="opportunitiesTable">
                    <thead>
                        <tr>
                            <th>Opportunity</th>
                            <th>Account</th>
                            <th>Professional Services Amount</th>
                            <th>Stage</th>
                            <th>Sales Commit</th>
                            <th>Close Date</th>
                            <th>Opportunity Owner</th>
                            <th>Opportunity Score</th>
                            <th>Account Score</th>
                            <th>Confidence</th>
                            <th>Explanation</th>
                        </tr>
                    </thead>
                    <tbody id="opportunitiesTableBody">
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            // Embed opportunities data for client-side filtering
            const allOpportunities = {opportunities_json};
            
            function showTopOpportunities(limit) {{
                // Update active button
                document.querySelectorAll('.filter-btn').forEach(btn => {{
                    btn.classList.remove('active');
                    const btnLimit = btn.dataset.limit;
                    if ((btnLimit === 'all' && limit >= 9999) || (btnLimit !== 'all' && parseInt(btnLimit) === limit)) {{
                        btn.classList.add('active');
                    }}
                }});
                
                // Get opportunities to display
                const opportunities = limit >= 9999 ? allOpportunities : allOpportunities.slice(0, limit);
                
                // Generate table rows
                const tbody = document.getElementById('opportunitiesTableBody');
                tbody.innerHTML = opportunities.map(opp => {{
                    const scoreClass = opp.opportunity_score >= 75 ? 'score-high' : (opp.opportunity_score >= 50 ? 'score-medium' : 'score-low');
                    const badgeClass = opp.confidence_level === 'High' ? 'badge-high' : (opp.confidence_level === 'Medium' ? 'badge-medium' : 'badge-low');
                    let closeDate = 'N/A';
                    if (opp.close_date) {{
                        const date = new Date(opp.close_date);
                        closeDate = date.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric', year: 'numeric' }});
                    }}
                    
                    const oppName = opp.opportunity_name.length > 50 ? opp.opportunity_name.substring(0, 50) + '...' : opp.opportunity_name;
                    const acctName = opp.account_name.length > 40 ? opp.account_name.substring(0, 40) + '...' : opp.account_name;
                    const explanation = opp.score_explanation.length > 100 ? opp.score_explanation.substring(0, 100) + '...' : opp.score_explanation;
                    const amount = opp.amount.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                    
                    const commit = opp.commit || '';
                    
                    return '<tr>' +
                        '<td><strong>' + oppName + '</strong></td>' +
                        '<td>' + acctName + '</td>' +
                        '<td>$' + amount + '</td>' +
                        '<td>' + opp.stage + '</td>' +
                        '<td>' + commit + '</td>' +
                        '<td>' + closeDate + '</td>' +
                        '<td>' + opp.owner_name + '</td>' +
                        '<td class="score-cell ' + scoreClass + '">' + opp.opportunity_score + '</td>' +
                        '<td class="score-cell ' + scoreClass + '">' + opp.account_score + '</td>' +
                        '<td><span class="badge ' + badgeClass + '">' + opp.confidence_level + '</span></td>' +
                        '<td style="font-size: 11px; color: var(--muted); max-width: 300px;">' + explanation + '</td>' +
                        '</tr>';
                }}).join('');
            }}
            
            // Initialize with Top 10 when DOM is ready
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', function() {{
                    showTopOpportunities(10);
                }});
            }} else {{
                showTopOpportunities(10);
            }}
        </script>
        </div>
        
        <div class="foot">
            <div>INNOVATIVE • SALES OPS</div>
            <div style="margin-top: 8px; font-size: 10px;">
                Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    return html

# =========================
# MAIN EXECUTION
# =========================

def main():
    """Main execution function"""
    print("=" * 80)
    print("Open Pipeline Account Score Analysis")
    print("=" * 80)
    
    # Authenticate
    print("\n[1/5] Authenticating with Salesforce...")
    token = get_jwt_token()
    print("[✓] Authentication successful")
    
    # Query historical data
    print("\n[2/5] Querying historical Closed Won opportunities...")
    closed_won = query_closed_won_opportunities(token, start_date=date(2024, 1, 1))
    
    # Validate Last 2 Years cohort totals
    total_prof_services = sum(float(opp.get("Professional_Services_Amount__c") or 0) for opp in closed_won)
    total_deals = len(closed_won)
    expected_total = 39212436.75
    expected_deals = 1635
    print(f"\n[VALIDATION] Last 2 Years Cohort:")
    print(f"  Found: {total_deals:,} deals, ${total_prof_services:,.2f} total")
    print(f"  Expected: {expected_deals:,} deals, ${expected_total:,.2f} total")
    if abs(total_prof_services - expected_total) < 0.01 and total_deals == expected_deals:
        print(f"  ✓ VALIDATION PASSED")
    else:
        print(f"  ⚠ VALIDATION WARNING: Totals don't match exactly")
    
    print("\n[3/5] Querying historical Closed Lost opportunities...")
    closed_lost = query_closed_lost_opportunities(token, start_date=date(2024, 1, 1))
    
    # Build account profiles
    print("\n[4/5] Building account scoring profiles...")
    profiles = build_account_profiles(closed_won, closed_lost)
    stats = calculate_normalized_scores(profiles)
    
    # Query open pipeline
    print("\n[5/5] Querying and scoring open pipeline opportunities...")
    open_opps = query_open_pipeline_opportunities(token)
    
    # Validate Open Pipeline totals
    total_open_prof_services = sum(float(opp.get("Professional_Services_Amount__c") or 0) for opp in open_opps)
    total_open_deals = len(open_opps)
    expected_open_total = 13465043.00
    expected_open_deals = 370
    print(f"\n[VALIDATION] Open Pipeline (Nov 5, 2025):")
    print(f"  Found: {total_open_deals:,} deals, ${total_open_prof_services:,.2f} total")
    print(f"  Expected: {expected_open_deals:,} deals, ${expected_open_total:,.2f} total")
    if abs(total_open_prof_services - expected_open_total) < 0.01 and total_open_deals == expected_open_deals:
        print(f"  ✓ VALIDATION PASSED")
    else:
        print(f"  ⚠ VALIDATION WARNING: Totals don't match exactly")
    
    scored_opps = score_open_opportunities(open_opps, profiles, stats)
    
    # Generate HTML
    print("\n[✓] Generating HTML dashboard...")
    html = generate_html_dashboard(scored_opps, profiles, stats)
    
    # Save output
    output_dir = Path.home() / "Desktop" / "Final Python Scripts"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save timestamped version
    timestamped_file = output_dir / f"open_pipeline_account_score_{timestamp}.html"
    with open(timestamped_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    # Save "latest" version for landing page link
    latest_file = output_dir / "open_pipeline_account_score_latest.html"
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"\n[✓] Analysis complete!")
    print(f"[✓] Output saved to: {timestamped_file}")
    print(f"[✓] Latest version saved to: {latest_file}")
    print(f"[✓] Scored {len(scored_opps)} opportunities")
    print(f"[✓] Based on {len(profiles)} account profiles from {len(closed_won)} Closed Won deals")
    
    # Also save JSON for future reference
    json_file = output_dir / f"open_pipeline_account_score_{timestamp}.json"
    json_data = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_opportunities": len(scored_opps),
            "total_accounts_profiled": len(profiles),
            "total_closed_won": len(closed_won),
            "total_closed_lost": len(closed_lost)
        },
        "opportunities": [
            {
                "opportunity_id": s.opportunity_id,
                "opportunity_name": s.opportunity_name,
                "account_id": s.account_id,
                "account_name": s.account_name,
                "amount": s.amount,
                "opportunity_score": round(s.opportunity_score, 2),
                "account_score": round(s.account_score, 2),
                "confidence_level": s.confidence_level,
                "component_scores": {
                    "speed": round(s.speed_score, 2),
                    "deal_size": round(s.deal_size_score, 2),
                    "product_mix": round(s.product_mix_score, 2),
                    "upsell": round(s.upsell_score, 2),
                    "win_rate": round(s.win_rate_score, 2),
                    "recency": round(s.recency_score, 2)
                }
            }
            for s in scored_opps
        ]
    }
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str)
    
    print(f"[✓] JSON data saved to: {json_file}")

if __name__ == "__main__":
    main()

