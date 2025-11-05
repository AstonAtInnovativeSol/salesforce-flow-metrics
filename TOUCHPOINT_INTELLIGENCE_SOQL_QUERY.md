# Touchpoint Intelligence Report - SOQL Query & Validation

## 🎯 Purpose
Build a Salesforce report to validate the Touchpoint Intelligence Report logic before implementing the full pipeline.

## 📊 Core Requirements

### Business Logic:
1. **Early Signal Detection**: Accounts with multiple active touchpoints + recent engagement
2. **Before Opportunities Created**: No existing open opportunities
3. **High Signal Accounts**: Min 4 active touchpoints (configurable)
4. **Recent Engagement**: Activities within rolling window (default: 90 days)

### Data Sources:
- ✅ **Salesforce**: Owners, account age, hygiene, activities
- ✅ **Outreach**: Series, replies, steps (synced to Salesforce)
- ✅ **Orum**: Connects, outcomes (synced via Outreach to Salesforce)
- ❌ **Microsoft Outlook**: Removed (not authorized)

---

## 🔍 SOQL Query for Salesforce Report Validation

### Base Query Structure

```sql
SELECT
    Id,
    Name,
    Industry,
    Type,  -- OR Segment__c (if custom field exists)
    CreatedDate,
    OwnerId,
    Owner.Name,
    Owner.Email,
    Owner.IsActive,
    -- Custom fields for ZoomInfo data
    ZoomInfo_AER__c,  -- ZI AER $ (Annual Estimated Revenue)
    ZoomInfo_FTE__c,  -- ZI FTE Employees
    -- Assigned DGR (if custom field exists)
    Assigned_DGR__c,  -- OR Assigned_DGR__r.Name if lookup
    -- Account hygiene fields
    BillingCountry,
    BillingState,
    BillingCity,
    -- Subqueries for activities
    (
        SELECT Id, Subject, ActivityDate, CreatedDate, Type, Status, 
               WhoId, WhatId, Description, OwnerId, Owner.Name
        FROM Tasks 
        WHERE ActivityDate = LAST_N_DAYS:90
           OR CreatedDate = LAST_N_DAYS:90
        ORDER BY ActivityDate DESC NULLS LAST, CreatedDate DESC
    ),
    (
        SELECT Id, Subject, ActivityDateTime, CreatedDate, Type,
               WhoId, WhatId, Description, OwnerId, Owner.Name
        FROM Events 
        WHERE ActivityDateTime = LAST_N_DAYS:90
           OR CreatedDate = LAST_N_DAYS:90
        ORDER BY ActivityDateTime DESC NULLS LAST, CreatedDate DESC
    ),
    -- Check for open opportunities
    (
        SELECT Id, Name, StageName, Amount, CloseDate, IsWon, IsClosed
        FROM Opportunities
        WHERE IsClosed = FALSE
        LIMIT 1
    )
FROM
    Account
WHERE
    -- Exclude accounts with open opportunities (early signal = before opps created)
    Id NOT IN (
        SELECT AccountId 
        FROM Opportunity 
        WHERE IsClosed = FALSE 
          AND StageName NOT IN ('Closed Won', 'Closed Lost', 'Disqualified')
    )
    -- Exclude test/internal accounts
    AND Name != 'Innovative Solutions'
    AND Name NOT LIKE '%AWS Sellers%'
    -- Ensure account has recent activities (touchpoints)
    AND Id IN (
        SELECT WhatId 
        FROM Task 
        WHERE ActivityDate = LAST_N_DAYS:90 
           OR CreatedDate = LAST_N_DAYS:90
    )
    -- Account created in last 12 months (configurable filter)
    AND CreatedDate = LAST_N_DAYS:365
    -- Active owner
    AND Owner.IsActive = TRUE
ORDER BY
    CreatedDate DESC
LIMIT 500
```

---

## 📋 Field Mappings & Calculations

### Metrics to Calculate in Python:

1. **ACTIVE TPS COUNT**:
   ```python
   # Count recent Tasks + Events (within rolling window)
   active_tps = len(tasks) + len(events)
   # Filter by date range (default: 90 days)
   ```

2. **LAST TOUCH DAYS**:
   ```python
   # Most recent ActivityDate or ActivityDateTime
   last_touch = max(
       max([t.ActivityDate for t in tasks if t.ActivityDate]),
       max([e.ActivityDateTime.date() for e in events if e.ActivityDateTime])
   )
   last_touch_days = (date.today() - last_touch).days
   ```

3. **ACCT AGE DAYS**:
   ```python
   acct_age_days = (date.today() - account.CreatedDate.date()).days
   ```

4. **AVG RECIPS PER SERIES** & **AVG INTERNAL PER SERIES**:
   - These require Outreach API data or custom fields
   - If Outreach syncs to Salesforce, check for:
     - Custom fields on Task/Event: `Outreach_Series_ID__c`, `Outreach_Recipients__c`
     - Or query Outreach API directly for series metadata

---

## 🎯 Recommended Salesforce Report Configuration

### Report Type:
**Accounts with Activities** (or custom report type if available)

### Filters:
1. **Show**: All accounts
2. **Account Created Date**: Last 12 months
3. **Owner Active**: Equals TRUE
4. **Account Name**: Does not contain "Innovative Solutions", "AWS Sellers"
5. **Opportunities**: No open opportunities (custom filter or formula)
6. **Activities**: Has activities in last 90 days

### Columns:
- Account Name
- Industry
- Type (or Segment)
- Owner Name
- Created Date
- # of Tasks (last 90 days)
- # of Events (last 90 days)
- Most Recent Activity Date
- Account Age (formula field: `TODAY() - CreatedDate`)

### Grouping:
- By Owner (optional)
- By Industry (optional)

---

## 🔧 Implementation Strategy

### Phase 1: Validate with Salesforce Report
1. ✅ Build the report above in Salesforce
2. ✅ Manually verify 5-10 accounts match expected logic
3. ✅ Document any discrepancies

### Phase 2: Build Python Script
1. ✅ Use SOQL query above as base
2. ✅ Implement activity counting logic
3. ✅ Calculate metrics (Active TPs, Last Touch, Acct Age)
4. ✅ Filter by min touchpoints (default: 4)

### Phase 3: Integrate Outreach Data
1. ✅ Query Outreach API for series metadata
2. ✅ Calculate "Avg Recips Per Series" and "Avg Internal Per Series"
3. ✅ Match Outreach activities to Salesforce Tasks/Events

### Phase 4: Handle Orum Data
1. ✅ Since Orum connects via Outreach, data should flow through Outreach sync
2. ✅ Verify Orum outcomes are captured in Outreach → Salesforce sync
3. ✅ If needed, query Orum API directly for connect rates

---

## 📝 Notes on Data Sources

### Outreach → Salesforce Integration:
- **Standard Integration**: Outreach syncs activities to Salesforce as `Task` or `Event` records
- **Custom Fields**: May sync series metadata to custom fields
- **API Access**: If standard sync doesn't include all needed fields, use Outreach API:
  ```python
  # Outreach API endpoints you may need:
  # - GET /api/v2/sequences/{id}/steps
  # - GET /api/v2/prospects/{id}/activities
  ```

### Orum → Outreach → Salesforce:
- **Integration Path**: Orum → Outreach → Salesforce
- **Recommendation**: Verify Orum call outcomes are captured in Outreach
- **If Not**: Query Orum API directly for:
  - Call connects
  - Call outcomes
  - Connect rates

### Microsoft Outlook:
- ❌ **Removed**: Not authorized
- **Impact**: Email thread data unavailable
- **Mitigation**: Rely on Outreach email activities (synced to Salesforce)

---

## ✅ Validation Checklist

Before building the full script, validate:

- [ ] Salesforce report returns expected accounts
- [ ] Activity counting matches expected "Active TPs"
- [ ] "No open opportunities" filter works correctly
- [ ] Account exclusions (Innovative Solutions, AWS Sellers) work
- [ ] Owner filtering (IsActive) works
- [ ] Outreach activities are present in Salesforce Tasks/Events
- [ ] Orum outcomes are captured via Outreach sync
- [ ] ZoomInfo fields are populated (if available)
- [ ] Assigned DGR field exists and is populated

---

## 🚀 Next Steps

1. **Build Salesforce Report** using the SOQL query above
2. **Validate** with sample accounts
3. **Share Report** with me for Python script alignment
4. **Build Python Script** to match report logic exactly
5. **Integrate Outreach API** for series metadata (if needed)
6. **Test End-to-End** with real data

---

**Last Updated**: 2025-11-05
**Status**: Ready for Salesforce Report Validation

