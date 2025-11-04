# JWT Authentication Setup Guide

This guide explains how to set up JWT (JSON Web Token) Bearer authentication for Salesforce API access in your Python scripts.

## Why JWT Authentication?

- ✅ **More Secure**: No passwords stored in code
- ✅ **Automated**: No interactive login required
- ✅ **Production-Ready**: Perfect for scheduled scripts and automation
- ✅ **Token-Based**: Access tokens expire automatically

---

## Prerequisites

- Salesforce org with admin access
- Python 3.x with `PyJWT` and `cryptography` packages installed
- OpenSSL installed (for key generation)

---

## Step-by-Step Setup

### Step 1: Generate RSA Key Pair

Open a terminal and run:

```bash
# Generate a 2048-bit RSA private key
openssl genrsa -out salesforce_private_key.pem 2048

# Generate the corresponding public certificate
openssl req -new -x509 -key salesforce_private_key.pem -out salesforce_public.crt -days 365

# (Optional) Verify the key was created
ls -la salesforce_private_key.pem salesforce_public.crt
```

**Important:**
- Keep `salesforce_private_key.pem` **SECURE** - never commit to GitHub
- Store it in a safe location (e.g., `~/Desktop/Salesforce_Reports/`)
- You'll upload `salesforce_public.crt` to Salesforce

---

### Step 2: Create Connected App in Salesforce

1. **Navigate to Setup:**
   - In Salesforce, go to **Setup** (gear icon → Setup)
   - Search for "App Manager" in Quick Find
   - Click **App Manager**

2. **Create New Connected App:**
   - Click **New Connected App** (top right)
   - Fill in basic information:
     - **Connected App Name**: e.g., "Python Analytics App"
     - **API Name**: Auto-filled
     - **Contact Email**: Your email

3. **Enable OAuth Settings:**
   - Check **Enable OAuth Settings**
   - **Callback URL**: `https://localhost` (required but not used for JWT)
   - **Selected OAuth Scopes**: Add:
     - `Access and manage your data (api)`
     - `Perform requests on your behalf at any time (refresh_token, offline_access)`
     - `Access your basic information (id, profile, email, address, phone)`

4. **Enable Digital Signatures:**
   - Check **Use digital signatures**
   - Click **Choose File** and upload your `salesforce_public.crt` file
   - Click **Save**

5. **Get Your Consumer Key:**
   - After saving, you'll see a **Consumer Key** (long string)
   - Copy this - you'll need it for `sf_config.py`
   - **Note:** The Consumer Secret is NOT needed for JWT authentication

6. **Manage Connected App Policies:**
   - Click **Manage Connected App** (if not auto-managed)
   - Set **IP Relaxation** to "Relax IP restrictions" (or configure specific IPs)
   - Set **Permitted Users** to "Admin approved users are pre-authorized" or "All users may self-authorize"
   - Click **Save**

---

### Step 3: Authorize Your Connected App

1. **Go to User Profile:**
   - Setup → Users → Users
   - Click on your user
   - Scroll to **Connected App Access** section
   - Click **Edit**

2. **Enable App Access:**
   - Find your Connected App in the list
   - Check the box to enable it
   - Click **Save**

---

### Step 4: Configure sf_config.py

1. **Copy the template:**
   ```bash
   cp sf_config.py.example sf_config.py
   ```

2. **Edit sf_config.py** with your values:
   ```python
   SF_USERNAME = 'your-email@example.com'  # Your Salesforce username
   SF_CONSUMER_KEY = '3MVG9...'  # Consumer Key from Step 2
   SF_DOMAIN = 'login'  # 'login' for production, 'test' for sandbox
   PRIVATE_KEY_FILE = '/Users/yourname/Desktop/Salesforce_Reports/salesforce_private_key.pem'
   ```

3. **Verify the private key path:**
   - Make sure the path to your private key file is correct
   - The script will read this file to generate JWT tokens

---

### Step 5: Test the Connection

Run one of your scripts to test:

```bash
python3 salesforce_flow_slack_metrics.py
```

You should see:
```
Authenticating with Salesforce via JWT...
✅ Connected successfully!
```

If you see an error, check:
- ✅ Private key file path is correct
- ✅ Private key matches the certificate in Connected App
- ✅ Consumer Key is correct
- ✅ Username is correct
- ✅ Connected App is authorized for your user
- ✅ Connected App has correct OAuth scopes

---

## Security Best Practices

### ✅ DO:
- Keep `sf_config.py` in `.gitignore` (already configured)
- Store private keys in secure locations
- Use environment variables in production (optional)
- Rotate keys periodically
- Use separate Connected Apps for different environments

### ❌ DON'T:
- Commit `sf_config.py` to GitHub
- Commit private key files (`.pem`, `.key`)
- Share private keys via email or chat
- Use production keys in development
- Leave keys in unsecured locations

---

## Troubleshooting

### Error: "Authentication failed: invalid_grant"
- **Cause**: Consumer Key or username mismatch
- **Fix**: Verify Consumer Key and username in `sf_config.py`

### Error: "File not found" for private key
- **Cause**: Incorrect path to private key file
- **Fix**: Check `PRIVATE_KEY_FILE` path in `sf_config.py`

### Error: "invalid_client_id"
- **Cause**: Connected App not properly configured
- **Fix**: Verify Connected App settings, especially OAuth scopes

### Error: "Token expired" or timeout
- **Cause**: Network issues or Salesforce unavailability
- **Fix**: Check internet connection and Salesforce status

### Error: "insufficient access rights"
- **Cause**: Connected App not authorized for your user
- **Fix**: Enable Connected App access in your user profile (Step 3)

---

## How It Works (Technical Details)

1. **JWT Token Generation:**
   - Script reads your private key
   - Creates a JWT claim with:
     - `iss` (issuer): Your Consumer Key
     - `sub` (subject): Your Salesforce username
     - `aud` (audience): Salesforce login URL
     - `exp` (expiration): 5 minutes from now
   - Signs the token using RS256 algorithm

2. **Token Exchange:**
   - Script sends JWT to Salesforce OAuth endpoint
   - Salesforce validates the signature using your public certificate
   - If valid, Salesforce returns an access token

3. **API Access:**
   - Script uses access token for Salesforce API calls
   - Token expires after session (typically 2 hours)
   - Script automatically re-authenticates when needed

---

## Additional Resources

- [Salesforce JWT Bearer Token Flow Documentation](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_jwt_flow.htm)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [simple-salesforce Documentation](https://github.com/simple-salesforce/simple-salesforce)

---

**Remember:** Keep your private key secure and never commit it to version control!

